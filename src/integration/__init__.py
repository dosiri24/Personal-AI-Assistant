"""
Integration Layer

시스템 컴포넌트들 간의 통합과 연결을 담당하는 레이어입니다.
- 에이전틱 AI 컨트롤러
- 이벤트 버스 시스템
- 의존성 주입 컨테이너
- 레거시 시스템 어댑터
"""

from .agentic_controller import AgenticController
from .event_bus import EventBus, EventType
from .container import DIContainer, ServiceScope
from .interfaces import BaseComponent, ComponentStatus, HealthStatus
from .legacy_adapter import LegacyMCPAdapter

__all__ = [
    "AgenticController",
    "EventBus",
    "EventType", 
    "DIContainer",
    "ServiceScope",
    "BaseComponent",
    "ComponentStatus",
    "HealthStatus",
    "LegacyMCPAdapter"
]
