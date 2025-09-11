"""
적응 모듈 (AdaptationManager)

ReAct 엔진의 동적 적응 부분을 담당하는 모듈
"""

import asyncio
from typing import Optional, Dict, Any
from ..agent_state import AgentContext
from ..planning_engine import ExecutionPlan
from ..goal_manager import GoalHierarchy
from ..dynamic_adapter import DynamicPlanAdapter, AdaptationEvent
from ...utils.logger import get_logger

logger = get_logger(__name__)


class AdaptationManager:
    """적응 관리자 - 동적 계획 적응"""
    
    def __init__(self, dynamic_adapter: DynamicPlanAdapter):
        self.dynamic_adapter = dynamic_adapter
    
    async def analyze_and_adapt(
        self,
        plan: ExecutionPlan,
        current_step: Any,
        execution_result: Dict[str, Any],
        hierarchy: Optional[GoalHierarchy],
        context: AgentContext
    ) -> Optional[ExecutionPlan]:
        """상황 분석 후 필요시 계획 적응"""
        
        try:
            # 적응 필요성 분석
            adaptation_event = await self.dynamic_adapter.analyze_situation(
                plan, current_step, execution_result, context
            )
            
            if adaptation_event:
                # 적응 전략 생성 및 적용
                adaptation_action = await self.dynamic_adapter.generate_adaptation_strategy(
                    adaptation_event, plan, hierarchy, context
                )
                
                adapted_plan = await self.dynamic_adapter.apply_adaptation(
                    adaptation_action, plan, hierarchy
                )
                
                logger.info(f"계획 적응 완료: {adaptation_action.strategy.value}")
                return adapted_plan
            
            return plan  # 적응이 필요 없으면 기존 계획 반환
            
        except Exception as e:
            logger.error(f"계획 적응 중 오류: {e}")
            return plan  # 오류 시 기존 계획 유지
    
    def should_trigger_adaptation(self, execution_result: Dict[str, Any]) -> bool:
        """적응 트리거 조건 확인"""
        if execution_result.get("status") == "failed":
            return True
        
        # 실행 시간이 예상보다 크게 초과된 경우
        actual_time = execution_result.get("execution_time", 0)
        expected_time = execution_result.get("expected_duration", 30)
        
        if actual_time > expected_time * 2:  # 2배 이상 초과
            return True
        
        return False
