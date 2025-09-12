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
        """Generate a simple thought and record it in the scratchpad.

        Returns the ThoughtRecord added to the scratchpad.
        """
        content = f"사용자 목표 분석: {context.goal[:80]}"
        thought = scratchpad.add_thought(content=content, reasoning_depth=1, confidence=0.8)
        logger.debug("Thought generated (stub)")
        return thought

