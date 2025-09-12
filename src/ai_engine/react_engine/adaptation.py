"""
Adaptation manager stub for ReactEngine.
"""

from __future__ import annotations

from ...utils.logger import get_logger


logger = get_logger(__name__)


class AdaptationManager:
    def __init__(self, dynamic_adapter) -> None:
        self.dynamic_adapter = dynamic_adapter
        logger.debug("AdaptationManager initialized (stub)")

