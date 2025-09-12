from __future__ import annotations

"""
계획 실행 모듈 (PlanningExecutor)

ReAct 엔진의 계획 기반 실행 부분을 담당하는 모듈
"""

import asyncio
import ast
import json
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime
from ..agent_state import (
    AgentScratchpad, AgentContext, AgentResult, ActionRecord, ObservationRecord, ActionType
)
from ..planning_engine import ExecutionPlan, PlanStep, TaskStatus as PlanTaskStatus, TaskStatus
from ..placeholder_resolver import placeholder_resolver
from ..goal_manager import GoalHierarchy
from ..dynamic_adapter import DynamicPlanAdapter
from ..llm_provider import LLMProvider
from typing import TYPE_CHECKING
from ...utils.logger import get_logger

if TYPE_CHECKING:
    # 타입 체크 전용 임포트로 순환 의존성 회피
    from ...mcp.executor import ToolExecutor

logger = get_logger(__name__)


class PlanningExecutor:
    """계획 실행기 - 고급 계획 기반 실행"""
    
    def __init__(self, tool_executor: ToolExecutor, dynamic_adapter: DynamicPlanAdapter, llm_provider: LLMProvider):
        self.tool_executor = tool_executor
        self.dynamic_adapter = dynamic_adapter
        self.llm_provider = llm_provider
    
    async def execute_plan_with_adaptation(
        self, 
        plan: ExecutionPlan,
        hierarchy: Optional[GoalHierarchy],
        context: AgentContext, 
        start_time: float
    ) -> AgentResult:
        """적응형 계획 실행"""
        
        scratchpad = AgentScratchpad(
            goal=context.goal,
            max_steps=context.max_iterations
        )
        
        current_plan = plan
        if not current_plan:
            raise ValueError("실행할 계획이 없습니다")
        
        # 무한 루프 방지: 동일 단계 연속 실패 추적
        step_failure_count = {}
        max_step_failures = 3  # 동일 단계 최대 3회 실패 허용
        
        for iteration in range(context.max_iterations):
            logger.debug(f"계획 실행 반복 {iteration + 1}/{context.max_iterations}")
            
            # 타임아웃 체크
            if time.time() - start_time > context.timeout_seconds:
                logger.warning("계획 실행 타임아웃")
                scratchpad.finalize("실행 시간이 초과되었습니다.", success=False)
                return AgentResult.failure_result(
                    "TIMEOUT_EXCEEDED",
                    scratchpad,
                    {"timeout_seconds": context.timeout_seconds}
                )
            
            # 다음 실행 가능한 단계 선택
            next_steps = current_plan.get_next_steps()
            if not next_steps:
                # 모든 단계 완료 확인
                if current_plan.is_completed():
                    final_result = await self._generate_final_answer(scratchpad, context)
                    scratchpad.finalize(final_result, success=True)
                    
                    logger.info(f"계획 실행 완료 (반복 {iteration + 1}회)")
                    return AgentResult.success_result(
                        final_result,
                        scratchpad,
                        {
                            "iterations": iteration + 1,
                            "execution_time": time.time() - start_time,
                            "plan_id": current_plan.plan_id
                        }
                    )
                else:
                    # 실행할 단계가 없지만 완료되지 않은 상태
                    logger.warning("실행 가능한 단계가 없음 - 계획 재검토 필요")
                    break
            
            # 첫 번째 단계 실행
            current_step = next_steps[0]
            current_step.status = PlanTaskStatus.IN_PROGRESS
            
            # 무한 루프 방지: 동일 단계 연속 실패 체크
            step_id = current_step.step_id
            if step_id in step_failure_count and step_failure_count[step_id] >= max_step_failures:
                logger.warning(f"단계 {step_id} 최대 실패 횟수 초과 - 건너뛰기")
                current_step.status = PlanTaskStatus.SKIPPED
                current_step.error = f"최대 재시도 횟수 초과 ({max_step_failures}회)"
                continue
            
            step_start_time = time.time()
            
            # 단계 실행
            execution_result = await self._execute_plan_step(
                current_step, plan, scratchpad
            )
            
            execution_result["execution_time"] = time.time() - step_start_time
            execution_result["total_elapsed"] = time.time() - start_time
            
            # 실패 카운트 업데이트
            if execution_result.get("status") == "failed":
                step_failure_count[step_id] = step_failure_count.get(step_id, 0) + 1
                logger.warning(f"단계 {step_id} 실패 (총 {step_failure_count[step_id]}회)")
            else:
                # 성공시 검증 결과 확인
                verification = execution_result.get("verification", {})
                if not verification.get("verified", True):  # 검증이 없으면 기본 성공으로 간주
                    logger.warning(f"단계 {step_id} 성공 보고되었으나 검증 실패: {verification.get('warning', '알 수 없음')}")
                    # 검증 실패를 로그에 기록하지만 실행은 계속 진행
                
                # 성공시 카운트 리셋
                step_failure_count.pop(step_id, None)
            
            # 적응 필요성 분석
            adaptation_event = await self.dynamic_adapter.analyze_situation(
                current_plan, current_step, execution_result, context
            )
            
            if adaptation_event:
                # 적응 전략 생성 및 적용
                adaptation_action = await self.dynamic_adapter.generate_adaptation_strategy(
                    adaptation_event, current_plan, hierarchy, context
                )
                
                current_plan = await self.dynamic_adapter.apply_adaptation(
                    adaptation_action, current_plan, hierarchy
                )
                
                logger.info(f"계획 적응 완료: {adaptation_action.strategy.value}")
        
        # 최대 반복 도달
        logger.warning(f"최대 반복 횟수 도달: {context.max_iterations}")
        partial_result = await self._generate_partial_result(scratchpad, context)
        scratchpad.finalize(partial_result, success=False)
        
        return AgentResult.max_iterations_result(
            scratchpad,
            {
                "iterations": context.max_iterations,
                "execution_time": time.time() - start_time,
                "partial_result": partial_result,
                "plan_id": current_plan.plan_id if current_plan else None
            }
        )
    
    async def _execute_plan_step(
        self, 
        step: PlanStep, 
        plan: ExecutionPlan,  # plan 매개변수 추가
        scratchpad: AgentScratchpad  # 올바른 타입으로 수정
    ) -> Dict[str, Any]:
        """계획 단계 실행"""
        
        try:
            if step.action_type == "tool_call" and step.tool_name:
                # 의존성 결과를 매개변수에 주입
                resolved_params = self._resolve_dependencies(step, plan)
                
                # 매개변수 검증 및 보정
                validated_params = self._validate_and_fix_tool_params(step.tool_name, resolved_params)
                
                if validated_params is None:
                    step.status = PlanTaskStatus.FAILED
                    error_msg = f"매개변수 검증 실패: {step.tool_name} 도구의 필수 매개변수가 누락되었습니다"
                    step.error = error_msg
                    logger.error(f"계획 단계 실행 실패: {error_msg}")
                    
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "expected_duration": step.estimated_duration
                    }
                
                # 도구 실행
                result = await self.tool_executor.execute_tool(
                    step.tool_name, 
                    validated_params
                )
                
                if result.result.is_success:
                    step.status = PlanTaskStatus.COMPLETED
                    step.result = result.result
                    
                    # Scratchpad에 기록 (올바른 방법)
                    action_record = scratchpad.add_action(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=step.tool_name,
                        parameters=validated_params
                    )
                    
                    observation_record = scratchpad.add_observation(
                        content=str(step.result.data),
                        success=True,
                        data=step.result.data
                    )
                    
                    # 🔍 실제 작업 완료 검증
                    verification_result = await self._verify_step_completion(step, scratchpad)
                    
                    if not verification_result.get("verified", False):
                        logger.warning(f"검증 실패: {step.step_id} - {verification_result.get('warning', '알 수 없는 문제')}")
                    
                    logger.info(f"계획 단계 성공: {step.step_id}")
                    
                    return {
                        "status": "success",
                        "result": step.result.data,
                        "expected_duration": step.estimated_duration,
                        "verification": verification_result
                    }
                    
                else:
                    step.status = PlanTaskStatus.FAILED
                    step.error = result.result.error_message
                    
                    logger.error(f"계획 단계 실패: {step.step_id} - {result.result.error_message}")
                    
                    return {
                        "status": "failed",
                        "error": result.result.error_message,
                        "expected_duration": step.estimated_duration
                    }
            
            else:
                # 추론이나 최종 답변 단계
                step.status = PlanTaskStatus.COMPLETED
                logger.info(f"추론 단계 완료: {step.step_id}")
                
                # 🔍 추론 단계의 경우 실제 작업이 수행되었는지 검증
                verification_result = await self._verify_step_completion(step, scratchpad)
                
                return {
                    "status": "success",
                    "result": step.description,
                    "expected_duration": step.estimated_duration,
                    "verification": verification_result
                }
                
        except Exception as e:
            step.status = PlanTaskStatus.FAILED
            step.error = str(e)
            logger.error(f"계획 단계 실행 중 예외: {step.step_id} - {e}")
            
            return {
                "status": "failed",
                "error": str(e),
                "expected_duration": step.estimated_duration
            }
    
    def _resolve_dependencies(self, step: PlanStep, plan: ExecutionPlan) -> Dict[str, Any]:
        """단계 의존성을 해결하여 실제 매개변수 생성"""
        if not step.tool_params:
            return {}
        
        # 의존성 결과 수집 (완료된 단계들의 결과)
        dependency_results = {}
        for dep_step_id in step.dependencies:
            dep_step = next((s for s in plan.steps if s.step_id == dep_step_id), None)
            if dep_step and dep_step.status == TaskStatus.COMPLETED:
                # 실행 결과는 plan 레벨에서 추적되어야 함
                # 임시로 빈 결과 사용 (실제 구현에서는 plan.execution_results 등에서 가져와야 함)
                dependency_results[dep_step_id] = {}
        
        # 새로운 PlaceholderResolver 사용
        resolved_params = placeholder_resolver.resolve_placeholders(
            step.tool_params, 
            dependency_results
        )
        
        logger.debug(f"의존성 해결 완료: {step.step_id} - {len(dependency_results)}개 의존성")
        return resolved_params
    
    def _substitute_placeholders(self, params: Dict[str, Any], dependency_results: Dict[str, Any]) -> Dict[str, Any]:
        """매개변수의 플레이스홀더를 실제 결과로 치환"""
        import re
        
        def substitute_value(value):
            if isinstance(value, str):
                # 1. "<바탕화면_경로>" 같은 대괄호 플레이스홀더 처리
                angle_pattern = r'<([^>]+)>'
                angle_matches = re.finditer(angle_pattern, value)
                
                for match in angle_matches:
                    placeholder = match.group(1)
                    logger.debug(f"각도 괄호 플레이스홀더 발견: {placeholder}")
                    
                    # 바탕화면 경로 특별 처리
                    if "바탕화면" in placeholder or "desktop" in placeholder.lower():
                        import os
                        desktop_path = os.path.expanduser("~/Desktop")
                        value = value.replace(match.group(0), desktop_path)
                        logger.info(f"바탕화면 경로 치환: {match.group(0)} → {desktop_path}")
                        continue
                    
                    # 다른 플레이스홀더 처리
                    if placeholder in dependency_results:
                        result_data = dependency_results[placeholder]
                        if isinstance(result_data, list) and result_data:
                            if isinstance(result_data[0], dict) and 'path' in result_data[0]:
                                replacement = result_data[0]['path']
                            else:
                                replacement = str(result_data[0])
                        elif isinstance(result_data, dict) and 'path' in result_data:
                            replacement = result_data['path']
                        else:
                            replacement = str(result_data)
                        value = value.replace(match.group(0), replacement)
                        logger.info(f"플레이스홀더 치환: {match.group(0)} → {replacement}")
                
                # 2. "[step_X 결과: ...]" 패턴 찾기
                pattern = r'\[([^]]+) 결과:[^]]+\]'
                matches = re.finditer(pattern, value)
                
                for match in matches:
                    step_ref = match.group(1)
                    if step_ref in dependency_results:
                        # 결과가 리스트인 경우 첫 번째 항목 사용
                        result_data = dependency_results[step_ref]
                        if isinstance(result_data, list) and result_data:
                            if isinstance(result_data[0], dict) and 'path' in result_data[0]:
                                # 파일 경로 리스트인 경우
                                value = result_data[0]['path']
                            else:
                                value = str(result_data[0])
                        elif isinstance(result_data, dict) and 'path' in result_data:
                            value = result_data['path']
                        else:
                            value = str(result_data)
                        break
                
                # 3. "탐색_결과_기반" 같은 플레이스홀더도 처리
                if value == "탐색_결과_기반" and dependency_results:
                    # 가장 최근 의존성 결과 사용
                    latest_result = list(dependency_results.values())[-1]
                    if isinstance(latest_result, list) and latest_result:
                        if isinstance(latest_result[0], dict) and 'path' in latest_result[0]:
                            value = latest_result[0]['path']
                        else:
                            value = str(latest_result[0])
                    elif isinstance(latest_result, dict) and 'path' in latest_result:
                        value = latest_result['path']
                    else:
                        value = str(latest_result)
            
            return value
        
        resolved = {}
        for key, value in params.items():
            if isinstance(value, dict):
                resolved[key] = self._substitute_placeholders(value, dependency_results)
            elif isinstance(value, list):
                resolved[key] = [substitute_value(item) for item in value]
            else:
                resolved[key] = substitute_value(value)
        
        return resolved
    
    def _validate_and_fix_tool_params(self, tool_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """도구 매개변수 검증 및 보정"""
        try:
            # 기본적인 매개변수 검증
            if not isinstance(params, dict):
                logger.warning(f"도구 '{tool_name}' 매개변수가 딕셔너리가 아님")
                return {}
            
            # 도구별 필수 매개변수 검증
            validated_params = params.copy()
            
            return validated_params
            
        except Exception as e:
            logger.error(f"매개변수 검증 중 오류: {e}")
            return None
    
    async def _generate_final_answer(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """최종 답변 생성"""
        try:
            # LLM에게 자연어로 최종 답변 생성 요청
            return await self._generate_natural_response(scratchpad, context)
            
        except Exception as e:
            logger.error(f"최종 답변 생성 실패: {e}")
            return "작업이 완료되었습니다."
    
    async def _generate_natural_response(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """LLM을 통해 자연어 답변 생성"""
        
        # 전체 실행 과정을 LLM에게 제공
        history = []
        history.append(f"사용자 요청: {context.goal}")
        
        for i, step in enumerate(scratchpad.steps, 1):
            if step.action:
                action_desc = f"도구 '{step.action.tool_name}' 실행"
                if step.action.parameters:
                    params = ", ".join([f"{k}={v}" for k, v in step.action.parameters.items()])
                    action_desc += f" (매개변수: {params})"
                history.append(f"{i}. {action_desc}")
                
            if step.observation:
                if step.observation.success:
                    history.append(f"   결과: {step.observation.content}")
                else:
                    history.append(f"   오류: {step.observation.content}")
        
        execution_summary = "\n".join(history)
        
        prompt = f"""당신은 개인 AI 비서입니다. 사용자의 요청에 대해 수행한 작업 결과를 자연스럽게 보고해주세요.

실행 과정:
{execution_summary}

다음 가이드라인을 따라 답변해주세요:
1. 자연스러운 비서 말투로 답변
2. 수행한 작업의 핵심 결과만 간결하게 요약
3. 사용자가 요청한 정보를 명확하게 전달
4. 불필요한 기술적 세부사항은 생략
5. 형식적이지 않고 대화하듯 자연스럽게

예시:
- "할일 목록을 확인해봤는데, 현재 2개 있습니다. 공부노트 자료구조 파트 작업이 진행 중이고, 부산 기행문 작성이 예정되어 있네요."
- "계산해보니 결과는 42입니다."
- "메모를 저장했습니다."

답변:"""

        try:
            from ..llm_provider import ChatMessage
            
            messages = [
                ChatMessage(role="user", content=prompt)
            ]
            
            llm_response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.7,
                max_tokens=2048  # 응답 생성 토큰 수 증가 (512→2048)
            )
            
            if llm_response and llm_response.content and llm_response.content.strip():
                return llm_response.content.strip()
            else:
                return "요청하신 작업을 완료했습니다."
                
        except Exception as e:
            logger.error(f"자연어 답변 생성 실패: {e}")
            return "작업이 완료되었습니다."
    
    async def _generate_partial_result(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """부분 결과 생성 - 자연어로 요약"""
        try:
            # 부분 결과도 자연어로 생성
            completed_count = 0
            for step in scratchpad.steps:
                if step.observation and step.observation.success:
                    completed_count += 1
                
            if completed_count == 0:
                return "요청하신 작업을 시작했지만 아직 완료되지 않았습니다."
            
            return f"{completed_count}개 작업을 완료했지만 전체 요청은 아직 진행 중입니다."
            
        except Exception as e:
            logger.error(f"부분 결과 생성 실패: {e}")
            return "작업이 부분적으로 완료되었습니다."
    
    async def _verify_step_completion(self, step, scratchpad) -> Dict[str, Any]:
        """
        단계 완료 검증 - 실제로 작업이 수행되었는지 확인
        
        Args:
            step: 실행된 단계
            scratchpad: 실행 기록
            
        Returns:
            Dict: 검증 결과
        """
        try:
            verification = {
                "verified": False,
                "actual_actions_performed": 0,
                "reasoning_only": True,
                "warning": None
            }
            
            # Scratchpad에서 실제 도구 호출이 있었는지 확인
            tool_actions = []
            for action_record in scratchpad.actions:
                if action_record.action_type == "tool_call":
                    tool_actions.append({
                        "tool": action_record.tool_name,
                        "params": action_record.parameters
                    })
            
            verification["actual_actions_performed"] = len(tool_actions)
            verification["tool_actions"] = tool_actions
            
            # 실제 도구 호출이 있었다면 검증됨
            if len(tool_actions) > 0:
                verification["verified"] = True
                verification["reasoning_only"] = False
            else:
                # 도구 호출이 없으면 추론만 한 것으로 간주
                verification["warning"] = "실제 도구 실행 없이 추론만 수행됨"
                logger.warning(f"단계 {step.step_id}: 실제 작업 없이 추론만 완료")
            
            return verification
            
        except Exception as e:
            logger.error(f"단계 검증 실패: {e}")
            return {
                "verified": False,
                "error": str(e),
                "actual_actions_performed": 0,
                "reasoning_only": True
            }
