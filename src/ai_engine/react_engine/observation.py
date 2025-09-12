"""
Observation management stub for ReactEngine.
"""

from __future__ import annotations

from ..agent_state import AgentScratchpad
from ...utils.logger import get_logger


logger = get_logger(__name__)


class ObservationManager:
    async def handle_timeout(self, scratchpad: AgentScratchpad, context) -> str:
        logger.warning("Timeout observed (stub)")
        return "실행 시간이 초과되었습니다."

    def detect_repetitive_actions(self, scratchpad: AgentScratchpad) -> bool:
        # Very simple heuristic placeholder
        return False

