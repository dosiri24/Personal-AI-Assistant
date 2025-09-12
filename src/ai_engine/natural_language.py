"""
자연어 처리 엔진 (경량 스텁)

리팩토링 과정에서 사용처가 기대하는 인터페이스를 제공하기 위한 최소 구현입니다.
테스트/데모 목적에 충분한 기본 동작을 제공하고, 추후 고도화가 가능합니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger


logger = get_logger(__name__)


class IntentType(Enum):
    task_management = "task_management"
    general_query = "general_query"
    calculation = "calculation"
    schedule = "schedule"


class UrgencyType(Enum):
    low = "low"
    normal = "normal"
    high = "high"


@dataclass
class ParsedCommand:
    intent: IntentType
    requires_tools: List[str] = field(default_factory=list)
    confidence: float = 0.9
    entities: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    urgency: UrgencyType = UrgencyType.normal
    clarification_needed: List[str] = field(default_factory=list)


class NaturalLanguageProcessor:
    """경량 자연어 처리기 스텁.

    CLI 테스트들이 기대하는 API를 제공합니다:
      - initialize() -> bool
      - parse_command(user_command: str, user_id: str) -> ParsedCommand
      - generate_personalized_response(user_id: str, message: str, context: dict) -> str
    """

    def __init__(self, settings: Optional[Any] = None) -> None:
        self.settings = settings
        self._initialized = False

    async def initialize(self) -> bool:
        """간단한 초기화 루틴."""
        try:
            # 추후: LLM, 메모리 등 초기화 훅 추가 가능
            self._initialized = True
            logger.info("NaturalLanguageProcessor initialized (stub)")
            return True
        except Exception as e:
            logger.error(f"NLP 초기화 실패: {e}")
            return False

    async def parse_command(self, user_command: str, user_id: str) -> ParsedCommand:
        """아주 단순한 규칙 기반 파싱.

        고도화 전까지는 키워드 기반으로 intent과 필요 도구를 대략 추정합니다.
        """
        text = (user_command or "").strip().lower()

        intent = IntentType.general_query
        requires: List[str] = []
        entities: Dict[str, Any] = {"raw": user_command}
        urgency = UrgencyType.normal
        confidence = 0.9

        # 간단한 힌트 룰들
        if any(k in text for k in ["할일", "todo", "할 일", "해야 할 일", "추가", "등록"]):
            intent = IntentType.task_management
            requires.append("TodoTool")
        if any(k in text for k in ["일정", "캘린더", "calendar", "회의", "약속"]):
            intent = IntentType.schedule
            if "CalendarTool" not in requires:
                requires.append("CalendarTool")
        if any(k in text for k in ["계산", "더해", "빼", "+", "-", "*", "/"]):
            intent = IntentType.calculation
            requires = [r for r in requires if r != "TodoTool"]  # 계산이면 계산 우선
            if "CalculatorTool" not in requires:
                requires.append("CalculatorTool")

        # 엔티티 대략 추출 (날짜/시간, 숫자)
        if any(k in text for k in ["긴급", "급해", "지금", "바로"]):
            urgency = UrgencyType.high
            confidence = 0.85

        # 메타데이터에 간단한 분석 정보 포함
        metadata = {
            "analysis": "rule_based_stub",
            "user_id": user_id,
        }

        return ParsedCommand(
            intent=intent,
            requires_tools=requires or ["GeneralResponder"],
            confidence=confidence,
            entities=entities,
            metadata=metadata,
            urgency=urgency,
            clarification_needed=[],
        )

    async def generate_personalized_response(
        self, *, user_id: str, message: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """아주 간단한 개인화된 응답 생성."""
        ctx = context or {}
        profile = (ctx.get("user_profile") or {}).copy()
        name = profile.get("name") or f"User_{user_id}"
        style = profile.get("style") or "friendly"

        return f"{name}, ({style}) 스타일로 답변합니다: '{message}' 요청을 확인했어요!"


__all__ = [
    "NaturalLanguageProcessor",
    "ParsedCommand",
    "IntentType",
    "UrgencyType",
]

