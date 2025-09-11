"""
자연어 처리 시스템의 기본 타입 및 데이터 클래스
의도 분류, 긴급도, 파싱된 명령, 작업 계획 등의 핵심 데이터 구조 정의
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """의도 분류"""
    TASK_MANAGEMENT = "task_management"  # 할일/일정 관리
    INFORMATION_SEARCH = "information_search"  # 정보 검색
    WEB_SCRAPING = "web_scraping"  # 웹 정보 수집
    SYSTEM_CONTROL = "system_control"  # 시스템 제어
    COMMUNICATION = "communication"  # 소통/메시지
    FILE_MANAGEMENT = "file_management"  # 파일 관리
    AUTOMATION = "automation"  # 자동화 설정
    QUERY = "query"  # 질문/조회
    UNCLEAR = "unclear"  # 불분명


class UrgencyLevel(Enum):
    """긴급도 수준"""
    IMMEDIATE = "immediate"  # 즉시
    HIGH = "high"  # 높음
    MEDIUM = "medium"  # 보통
    LOW = "low"  # 낮음


@dataclass
class ParsedCommand:
    """파싱된 명령 데이터"""
    original_text: str
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    urgency: UrgencyLevel
    requires_tools: List[str]
    clarification_needed: List[str]
    metadata: Dict[str, Any]


@dataclass 
class TaskPlan:
    """작업 계획 데이터"""
    goal: str
    steps: List[Dict[str, Any]]
    required_tools: List[str]
    estimated_duration: Optional[str]
    difficulty: str
    confidence: float
    dependencies: List[str]


@dataclass
class ExecutionResult:
    """명령 실행 결과"""
    status: str  # success, error, clarification_needed, not_implemented
    message: str
    data: Optional[Dict[str, Any]] = None
    clarifications: Optional[List[str]] = None


@dataclass
class PersonalizationContext:
    """개인화 컨텍스트"""
    user_id: str
    communication_style: str = "친근한"
    detail_preference: str = "중간"
    response_tone: str = "도움이 되는"
    expertise_level: str = "중급"
    preferences: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}


@dataclass
class FeedbackData:
    """피드백 분석 데이터"""
    user_id: str
    feedback_type: str  # positive, negative, suggestion
    content: str
    context: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    rating: Optional[float] = None  # 1.0 ~ 5.0


# 유틸리티 함수들
def create_error_result(message: str, error_details: Optional[str] = None) -> ExecutionResult:
    """오류 결과 생성 헬퍼"""
    data = {"error_details": error_details} if error_details else None
    return ExecutionResult(
        status="error",
        message=message,
        data=data
    )


def create_success_result(message: str, data: Optional[Dict[str, Any]] = None) -> ExecutionResult:
    """성공 결과 생성 헬퍼"""
    return ExecutionResult(
        status="success",
        message=message,
        data=data
    )


def create_clarification_result(message: str, clarifications: List[str]) -> ExecutionResult:
    """명확화 요청 결과 생성 헬퍼"""
    return ExecutionResult(
        status="clarification_needed",
        message=message,
        clarifications=clarifications
    )
