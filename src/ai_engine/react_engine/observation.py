"""
관찰 모듈 (ObservationManager)

ReAct 엔진의 관찰(Observation) 부분을 담당하는 모듈
"""

import asyncio
from typing import Optional, List, Dict, Any
from ..agent_state import (
    AgentScratchpad, AgentContext, ActionRecord, ObservationRecord
)
from ...utils.logger import get_logger

logger = get_logger(__name__)


class ObservationManager:
    """관찰 관리자 - ReAct의 Observation 부분"""
    
    def __init__(self):
        pass
    
    async def observe_final_answer(self, action: ActionRecord, scratchpad: AgentScratchpad) -> ObservationRecord:
        """최종 답변 관찰"""
        final_answer = action.parameters.get("answer", "")
        
        observation = scratchpad.add_observation(
            content=f"최종 답변 생성: {final_answer}",
            success=True,
            analysis="목표 달성을 위한 최종 답변이 준비되었습니다."
        )
        
        return observation
    
    def detect_repetitive_actions(self, scratchpad: AgentScratchpad) -> bool:
        """반복 행동 감지"""
        if len(scratchpad.steps) < 3:
            return False
            
        # 최근 3개 단계의 액션 확인
        recent_steps = scratchpad.steps[-3:]
        action_signatures = []
        
        for step in recent_steps:
            if step.action:
                signature = f"{step.action.action_type.value}:{step.action.tool_name}:{step.action.description[:50]}"
                action_signatures.append(signature)
        
        # 동일한 액션이 2번 이상 반복되는지 확인
        return len(action_signatures) >= 2 and len(set(action_signatures)) <= 1
    
    async def handle_timeout(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """타임아웃 시 적절한 응답 생성"""
        try:
            # 성공한 액션이 있는지 확인
            successful_actions = []
            for step in scratchpad.steps:
                if step.observation and step.observation.success and step.action:
                    if step.action.tool_name == 'notion_todo':
                        successful_actions.append("할일 생성/수정")
                    elif step.action.tool_name == 'apple_calendar':
                        successful_actions.append("일정 등록")
                    elif step.action.tool_name:
                        successful_actions.append(f"{step.action.tool_name} 실행")
            
            if successful_actions:
                actions_text = ", ".join(set(successful_actions))
                return f"시간이 초과되었지만 {actions_text}은 완료했어요! 😊"
            else:
                return "시간이 초과되어 작업을 완료하지 못했어요. 다시 시도해주세요."
                
        except Exception as e:
            logger.error(f"타임아웃 응답 생성 실패: {e}")
            return "시간이 초과되었어요. 다시 시도해주세요."
    
    def analyze_execution_success(self, scratchpad: AgentScratchpad) -> Dict[str, Any]:
        """실행 성공도 분석"""
        total_steps = len(scratchpad.steps)
        successful_steps = sum(
            1 for step in scratchpad.steps 
            if step.observation and step.observation.success
        )
        
        return {
            "total_steps": total_steps,
            "successful_steps": successful_steps,
            "success_rate": successful_steps / total_steps if total_steps > 0 else 0,
            "completion_status": "완료" if successful_steps == total_steps else "부분완료"
        }
