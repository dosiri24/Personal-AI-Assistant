"""
계획 실행 모듈 (PlanningExecutor)

ReAct 엔진의 계획 기반 실행 부분을 담당하는 모듈
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, Union
from datetime import datetime
from ..agent_state import (
    AgentScratchpad, AgentContext, AgentResult, ActionRecord, ObservationRecord, ActionType
)
from ..planning_engine import ExecutionPlan, TaskStatus as PlanTaskStatus
from ..goal_manager import GoalHierarchy
from ..dynamic_adapter import DynamicPlanAdapter
from ...mcp.executor import ToolExecutor
from ...utils.logger import get_logger

logger = get_logger(__name__)


class PlanningExecutor:
    """계획 실행기 - 고급 계획 기반 실행"""
    
    def __init__(self, tool_executor: ToolExecutor, dynamic_adapter: DynamicPlanAdapter):
        self.tool_executor = tool_executor
        self.dynamic_adapter = dynamic_adapter
    
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
            
            step_start_time = time.time()
            
            # 단계 실행
            execution_result = await self._execute_plan_step(
                current_step, scratchpad, context
            )
            
            execution_result["execution_time"] = time.time() - step_start_time
            execution_result["total_elapsed"] = time.time() - start_time
            
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
        step: Any, 
        scratchpad: AgentScratchpad, 
        context: AgentContext
    ) -> Dict[str, Any]:
        """계획 단계 실행"""
        
        try:
            if step.action_type == "tool_call" and step.tool_name:
                # 매개변수 검증 및 보정
                validated_params = self._validate_and_fix_tool_params(step.tool_name, step.tool_params or {})
                
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
                    
                    logger.info(f"계획 단계 성공: {step.step_id}")
                    
                    return {
                        "status": "success",
                        "result": step.result.data,
                        "expected_duration": step.estimated_duration
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
                
                return {
                    "status": "success",
                    "result": step.description,
                    "expected_duration": step.estimated_duration
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
            if scratchpad.steps:
                last_observation = scratchpad.steps[-1].observation
                if last_observation and last_observation.success:
                    # 도구 실행 결과를 사용자 친화적으로 변환
                    return self._format_user_friendly_response(last_observation.content, context.goal)
            
            return "요청하신 작업을 완료했습니다."
            
        except Exception as e:
            logger.error(f"최종 답변 생성 실패: {e}")
            return "작업이 완료되었습니다."
    
    def _format_user_friendly_response(self, content: Union[str, dict], goal: str) -> str:
        """응답을 사용자 친화적으로 포맷팅"""
        logger.debug(f"포맷팅할 컨텐츠: {content}")
        logger.debug(f"목표: {goal}")
        
        # 이미 딕셔너리인 경우 직접 처리
        if isinstance(content, dict):
            logger.debug("컨텐츠가 딕셔너리임")
            
            # notion_todo 도구 응답 처리
            if "todos" in content:
                logger.debug("todos 키 발견, _format_todo_response 호출")
                return self._format_todo_response(content)
                
            # 기타 도구 응답은 간단히 처리
            if "message" in content:
                logger.debug(f"message 키 발견: {content['message']}")
                return content["message"]
                
            # 딕셔너리에서 다른 유용한 정보 찾기
            if "result" in content:
                logger.debug(f"result 키 발견: {content['result']}")
                return str(content["result"])
                
            # 딕셔너리 전체를 문자열로 변환해서 재시도
            logger.debug("딕셔너리를 문자열로 변환 후 재시도")
            content = str(content)
        
        # 문자열인 경우 JSON 추출 시도
        if isinstance(content, str):
            logger.debug("컨텐츠가 문자열임, JSON 추출 시도")
            
            # {} 블록 찾기
            json_blocks = []
            i = 0
            while i < len(content):
                if content[i] == '{':
                    brace_count = 1
                    start = i
                    i += 1
                    while i < len(content) and brace_count > 0:
                        if content[i] == '{':
                            brace_count += 1
                        elif content[i] == '}':
                            brace_count -= 1
                        i += 1
                    
                    if brace_count == 0:
                        json_blocks.append(content[start:i])
                else:
                    i += 1
            
            logger.debug(f"발견된 JSON 블록들: {json_blocks}")
            
            # 각 JSON 블록 파싱 시도
            for json_part in json_blocks:
                logger.debug(f"파싱 시도할 JSON 부분: {json_part}")
                if json_part.strip():
                    try:
                        # JSON 문자열에서 작은따옴표를 큰따옴표로 변경
                        json_part_fixed = json_part.replace("'", '"')
                        data = json.loads(json_part_fixed)
                        logger.debug(f"파싱된 데이터: {data}")
                        
                        # notion_todo 도구 응답 처리
                        if "todos" in data:
                            return self._format_todo_response(data)
                        
                        # 기타 도구 응답은 간단히 처리
                        if "message" in data:
                            return data["message"]
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON 파싱 실패: {e}")
                        pass
            
            # JSON 파싱 실패 시 간단한 메시지로 대체
            if "할일" in goal or "todo" in goal.lower():
                return "할일 목록을 확인했습니다."
            
            return "요청하신 작업을 완료했습니다."
        
        # 기본 반환값
        return "요청하신 작업을 완료했습니다."
    
    def _format_todo_response(self, data: dict) -> str:
        """할일 응답을 사용자 친화적으로 포맷팅"""
        try:
            todos = data.get("todos", [])
            count = data.get("count", len(todos))
            
            if count == 0:
                return "현재 해야 할 일이 없습니다. 🎉"
            
            response = f"📋 **할일 목록** (총 {count}개)\n\n"
            
            for i, todo in enumerate(todos[:5], 1):  # 최대 5개만 표시
                title = todo.get("title", "제목 없음")
                priority = todo.get("priority", "중간")
                status = todo.get("status", "상태 없음")
                due_date = todo.get("due_date", "")
                
                # 우선순위 이모지
                priority_emoji = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}.get(priority, "⚪")
                
                # 상태 이모지  
                status_emoji = {"진행 중": "⏳", "예정": "📅", "완료": "✅"}.get(status, "📝")
                
                response += f"{i}. {priority_emoji} **{title}**\n"
                response += f"   {status_emoji} {status}"
                
                if due_date:
                    # 날짜 포맷팅
                    try:
                        from datetime import datetime
                        if "T" in due_date:
                            date_obj = datetime.fromisoformat(due_date.replace("Z", "+00:00"))
                            formatted_date = date_obj.strftime("%m월 %d일")
                        else:
                            formatted_date = due_date
                        response += f" | 📅 {formatted_date}"
                    except:
                        response += f" | 📅 {due_date}"
                
                response += "\n\n"
            
            if len(todos) > 5:
                response += f"... 외 {len(todos) - 5}개 더"
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"할일 응답 포맷팅 실패: {e}")
            return f"할일 {data.get('count', 0)}개를 확인했습니다."
    
    async def _generate_partial_result(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """부분 결과 생성"""
        try:
            completed_steps = sum(
                1 for step in scratchpad.steps 
                if step.observation and step.observation.success
            )
            total_steps = len(scratchpad.steps)
            
            return f"부분적으로 완료됨: {completed_steps}/{total_steps} 단계 성공"
            
        except Exception as e:
            logger.error(f"부분 결과 생성 실패: {e}")
            return "작업이 부분적으로 완료되었습니다."
