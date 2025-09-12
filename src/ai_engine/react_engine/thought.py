"""
Thought generation stub for ReactEngine.
"""

from __future__ import annotations

from ..agent_state import AgentScratchpad
from ...utils.logger import get_logger


logger = get_logger(__name__)


class ThoughtGenerator:
    def __init__(self, llm_provider) -> None:
        self.llm_provider = llm_provider

    async def generate_thought(self, scratchpad: AgentScratchpad, context) -> object:
        """Generate a thought based on previous thinking history and current context.

        Returns the ThoughtRecord added to the scratchpad.
        """
        # 이전 thinking 단계들 수집
        previous_thoughts = []
        thinking_count = 0
        
        for step in scratchpad.steps:
            if hasattr(step, 'action') and step.action:
                if getattr(step.action, 'action_type', None) == 'thinking':
                    previous_thoughts.append(getattr(step.action, 'content', ''))
                    thinking_count += 1
        
        # 연속 thinking 방지
        if thinking_count >= 3:
            content = "충분한 분석을 완료했으므로 이제 구체적인 행동을 수행해야 합니다."
        elif previous_thoughts:
            # 이전 추론을 기반으로 다음 단계 생각
            last_thought = previous_thoughts[-1] if previous_thoughts else ""
            content = f"이전 분석 결과를 토대로 다음 단계: {context.goal[:50]}... [이전: {last_thought[:30]}...]"
        else:
            # 첫 번째 thinking
            content = f"사용자 목표 분석 및 접근 전략 수립: {context.goal[:80]}"
        
        thought = scratchpad.add_thought(
            content=content, 
            reasoning_depth=min(thinking_count + 1, 3), 
            confidence=0.8 - (thinking_count * 0.1)  # thinking이 많을수록 신뢰도 감소
        )
        
        logger.debug(f"Thought generated: {thinking_count}번째 thinking, 내용: {content[:50]}...")
        return thought

