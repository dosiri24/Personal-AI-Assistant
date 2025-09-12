"""
Action execution stub for ReactEngine.
"""

from __future__ import annotations

from ..agent_state import AgentScratchpad, ActionType
from ...utils.logger import get_logger


logger = get_logger(__name__)


class ActionExecutor:
    def __init__(self, tool_registry, tool_executor) -> None:
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor

    async def execute_and_observe(self, action, scratchpad: AgentScratchpad, context):
        """Execute a decided action and record a minimal observation.

        This stub does not actually invoke tools; it records a placeholder observation.
        """
        if action.action_type == ActionType.FINAL_ANSWER:
            obs = scratchpad.add_observation(content=action.parameters.get("answer", ""), success=True)
            logger.info("Recorded final answer observation (stub)")
            return obs

        # TOOL_CALL or others: record a generic success observation
        obs = scratchpad.add_observation(content="도구 호출이 수행되었습니다 (stub)", success=True)
        logger.info("Recorded tool-call observation (stub)")
        return obs

