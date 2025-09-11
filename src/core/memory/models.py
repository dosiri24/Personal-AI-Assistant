"""
기억 데이터 모델 정의

AI의 장기기억을 위한 데이터 구조를 정의합니다.
행동 기록, 대화 기록, 프로젝트 맥락 등을 체계적으로 관리합니다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Union
import json


class MemoryType(Enum):
    """기억 타입"""
    ACTION = "action"              # 행동 기록
    CONVERSATION = "conversation"   # 대화 기록
    PROJECT = "project"            # 프로젝트 관련
    PREFERENCE = "preference"      # 사용자 선호도
    SYSTEM = "system"              # 시스템 상태
    LEARNING = "learning"          # 학습된 패턴


class ImportanceLevel(Enum):
    """중요도 레벨"""
    CRITICAL = "critical"     # 5 - 매우 중요 (절대 삭제 안됨)
    HIGH = "high"            # 4 - 높음
    MEDIUM = "medium"        # 3 - 보통
    LOW = "low"              # 2 - 낮음
    MINIMAL = "minimal"      # 1 - 최소 (자동 삭제 대상)


@dataclass
class Memory:
    """기본 기억 클래스"""
    id: str
    user_id: str
    memory_type: MemoryType
    content: str
    importance: ImportanceLevel
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "importance": self.importance.value,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", [])
        )
    
    def update_access(self):
        """접근 정보 업데이트"""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class ActionMemory(Memory):
    """행동 기록 전용 클래스"""
    action: str = ""
    reasoning: str = ""
    result: str = ""
    confidence_score: float = 0.0
    execution_time: int = 0  # 초
    tools_used: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.memory_type = MemoryType.ACTION
        if not self.content:
            self.content = f"행동: {self.action}\n이유: {self.reasoning}\n결과: {self.result}"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "action": self.action,
            "reasoning": self.reasoning,
            "result": self.result,
            "confidence_score": self.confidence_score,
            "execution_time": self.execution_time,
            "tools_used": self.tools_used
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionMemory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType.ACTION,
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", []),
            action=data.get("action", ""),
            reasoning=data.get("reasoning", ""),
            result=data.get("result", ""),
            confidence_score=data.get("confidence_score", 0.0),
            execution_time=data.get("execution_time", 0),
            tools_used=data.get("tools_used", [])
        )


@dataclass
class ConversationMemory(Memory):
    """대화 기록 전용 클래스"""
    user_message: str = ""
    ai_response: str = ""
    session_id: str = ""
    response_type: str = ""
    tone_used: str = ""
    
    def __post_init__(self):
        self.memory_type = MemoryType.CONVERSATION
        if not self.content:
            self.content = f"사용자: {self.user_message}\nAI: {self.ai_response}"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "user_message": self.user_message,
            "ai_response": self.ai_response,
            "session_id": self.session_id,
            "response_type": self.response_type,
            "tone_used": self.tone_used
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType.CONVERSATION,
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", []),
            user_message=data.get("user_message", ""),
            ai_response=data.get("ai_response", ""),
            session_id=data.get("session_id", ""),
            response_type=data.get("response_type", ""),
            tone_used=data.get("tone_used", "")
        )


@dataclass
class ProjectMemory(Memory):
    """프로젝트 맥락 전용 클래스"""
    project_name: str = ""
    phase: str = ""
    status: str = ""
    key_decisions: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.memory_type = MemoryType.PROJECT
        if not self.content:
            self.content = f"프로젝트: {self.project_name}\n단계: {self.phase}\n상태: {self.status}"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "project_name": self.project_name,
            "phase": self.phase,
            "status": self.status,
            "key_decisions": self.key_decisions,
            "lessons_learned": self.lessons_learned
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectMemory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType.PROJECT,
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", []),
            project_name=data.get("project_name", ""),
            phase=data.get("phase", ""),
            status=data.get("status", ""),
            key_decisions=data.get("key_decisions", []),
            lessons_learned=data.get("lessons_learned", [])
        )


@dataclass
class UserPreferenceMemory(Memory):
    """사용자 선호도 전용 클래스"""
    preference_category: str = ""
    preference_value: Any = None
    confidence: float = 0.0
    learning_source: str = ""  # "explicit", "implicit", "inferred"
    
    def __post_init__(self):
        self.memory_type = MemoryType.PREFERENCE
        if not self.content:
            self.content = f"선호도: {self.preference_category} = {self.preference_value}"
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "preference_category": self.preference_category,
            "preference_value": self.preference_value,
            "confidence": self.confidence,
            "learning_source": self.learning_source
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserPreferenceMemory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType.PREFERENCE,
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            access_count=data.get("access_count", 0),
            tags=data.get("tags", []),
            preference_category=data.get("preference_category", ""),
            preference_value=data.get("preference_value"),
            confidence=data.get("confidence", 0.0),
            learning_source=data.get("learning_source", "")
        )


# 유틸리티 함수들
def create_memory_id(memory_type: MemoryType, user_id: str, timestamp: Optional[datetime] = None) -> str:
    """기억 ID 생성"""
    if timestamp is None:
        timestamp = datetime.now()
    
    timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 밀리초까지
    return f"{memory_type.value}_{user_id}_{timestamp_str}"


def determine_importance(memory_type: MemoryType, 
                        content_length: int,
                        has_specific_data: bool = False,
                        user_explicit: bool = False) -> ImportanceLevel:
    """중요도 자동 판단"""
    
    # 사용자가 명시적으로 중요하다고 한 경우
    if user_explicit:
        return ImportanceLevel.CRITICAL
    
    # 메모리 타입별 기본 중요도
    base_importance = {
        MemoryType.ACTION: ImportanceLevel.HIGH,
        MemoryType.CONVERSATION: ImportanceLevel.MEDIUM,
        MemoryType.PROJECT: ImportanceLevel.HIGH,
        MemoryType.PREFERENCE: ImportanceLevel.CRITICAL,
        MemoryType.SYSTEM: ImportanceLevel.LOW,
        MemoryType.LEARNING: ImportanceLevel.HIGH
    }
    
    importance = base_importance.get(memory_type, ImportanceLevel.MEDIUM)
    
    # 구체적인 데이터가 있으면 중요도 상승
    if has_specific_data:
        if importance == ImportanceLevel.LOW:
            importance = ImportanceLevel.MEDIUM
        elif importance == ImportanceLevel.MEDIUM:
            importance = ImportanceLevel.HIGH
    
    # 내용이 매우 짧으면 중요도 하락
    if content_length < 50:
        if importance == ImportanceLevel.HIGH:
            importance = ImportanceLevel.MEDIUM
        elif importance == ImportanceLevel.MEDIUM:
            importance = ImportanceLevel.LOW
    
    return importance


def extract_tags_from_content(content: str, memory_type: MemoryType) -> List[str]:
    """내용에서 태그 자동 추출"""
    tags = []
    content_lower = content.lower()
    
    # 메모리 타입별 키워드
    keywords = {
        MemoryType.ACTION: ['실행', '완료', '실패', '성공', '오류', '도구'],
        MemoryType.CONVERSATION: ['질문', '답변', '요청', '확인', '설명'],
        MemoryType.PROJECT: ['개발', '구현', '테스트', '배포', '버그', '기능'],
        MemoryType.PREFERENCE: ['선호', '좋아함', '싫어함', '설정', '톤'],
        MemoryType.SYSTEM: ['설정', '상태', '연결', '오류', '성능'],
        MemoryType.LEARNING: ['학습', '패턴', '개선', '분석', '피드백']
    }
    
    # 해당 타입의 키워드 확인
    for keyword in keywords.get(memory_type, []):
        if keyword in content_lower:
            tags.append(keyword)
    
    # 일반적인 태그들
    general_keywords = ['긴급', '중요', '일정', '알림', '파일', '검색', '노션', '이메일']
    for keyword in general_keywords:
        if keyword in content_lower:
            tags.append(keyword)
    
    return tags
