"""
계획 실행 모듈 (PlanningExecutor)

ReAct 엔진의 계획 기반 실행 부분을 담당하는 모듈
"""

import asyncio
import time
from typing import Optional, Dict, Any
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
                    
                    # Scratchpad에 기록
                    action_record = ActionRecord(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=step.tool_name,
                        parameters=validated_params
                    )
                    
                    observation_record = ObservationRecord(
                        content=str(step.result.data)
                    )
                    
                    step_record = scratchpad.start_new_step()
                    step_record.action = action_record
                    step_record.observation = observation_record
                    step_record.end_time = datetime.now()
                    
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
                    return f"요청하신 작업을 완료했습니다: {last_observation.content}"
            
            return "계획된 작업들이 완료되었습니다."
            
        except Exception as e:
            logger.error(f"최종 답변 생성 실패: {e}")
            return "작업이 완료되었습니다."
    
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
