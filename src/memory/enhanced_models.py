"""
개선된 기억 데이터 모델 정의 - Step 4.2

AI의 장기기억을 위한 체계적인 데이터 구조를 정의합니다.
행동-이유 페어, 메타데이터 스키마, 중요도 점수 체계를 완성합니다.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Tuple
import json
import uuid
from pathlib import Path


class MemoryType(Enum):
    """기억 타입 - 확장된 분류"""
    ACTION = "action"              # 행동 기록 (행동-이유 페어)
    CONVERSATION = "conversation"   # 대화 기록 (사용자-AI 상호작용)
    PROJECT = "project"            # 프로젝트 관련 맥락
    PREFERENCE = "preference"      # 사용자 선호도 (학습된 패턴)
    SYSTEM = "system"              # 시스템 상태 및 설정
    LEARNING = "learning"          # AI 학습 패턴 및 개선사항
    CONTEXT = "context"            # 환경적 맥락 (시간, 장소, 상황)
    RELATIONSHIP = "relationship"   # 인간관계 및 소셜 컨텍스트


class ImportanceLevel(Enum):
    """중요도 레벨 - 수치화된 체계"""
    CRITICAL = 5    # 절대 삭제 안됨 (핵심 선호도, 중요한 결정)
    HIGH = 4        # 높은 중요도 (성공한 행동 패턴, 주요 프로젝트)
    MEDIUM = 3      # 보통 중요도 (일반적인 대화, 루틴 작업)
    LOW = 2         # 낮은 중요도 (간단한 질문, 일시적 작업)
    MINIMAL = 1     # 자동 삭제 대상 (로그 수준 기록)
    TRIVIAL = 0     # 매우 낮은 중요도 (즉시 삭제 대상)
    
    @property
    def retention_days(self) -> int:
        """중요도별 보존 기간 (일)"""
        retention_map = {
            ImportanceLevel.CRITICAL: -1,      # 영구 보존
            ImportanceLevel.HIGH: 365,         # 1년
            ImportanceLevel.MEDIUM: 90,        # 3개월
            ImportanceLevel.LOW: 30,           # 1개월
            ImportanceLevel.MINIMAL: 7,        # 1주일
            ImportanceLevel.TRIVIAL: 1         # 1일
        }
        return retention_map[self]
    
    @property
    def auto_archive_days(self) -> int:
        """자동 아카이빙 기간 (일)"""
        return self.retention_days // 2 if self.retention_days > 0 else -1


class ActionType(Enum):
    """행동 타입 분류"""
    SCHEDULE = "schedule"          # 일정 관리
    INFORMATION = "information"    # 정보 검색/처리
    COMMUNICATION = "communication" # 커뮤니케이션
    FILE_MANAGEMENT = "file_management" # 파일 관리
    SYSTEM_CONTROL = "system_control"   # 시스템 제어
    AUTOMATION = "automation"      # 자동화 작업
    LEARNING = "learning"          # 학습 및 연구
    CREATIVE = "creative"          # 창작 활동
    ANALYSIS = "analysis"          # 분석 및 보고


class ContextType(Enum):
    """컨텍스트 타입"""
    TEMPORAL = "temporal"          # 시간적 맥락 (시간대, 요일, 계절)
    SPATIAL = "spatial"            # 공간적 맥락 (위치, 환경)
    EMOTIONAL = "emotional"        # 감정적 맥락 (기분, 상태)
    SOCIAL = "social"              # 사회적 맥락 (사람, 관계)
    TECHNICAL = "technical"        # 기술적 맥락 (도구, 환경)
    SITUATIONAL = "situational"    # 상황적 맥락 (이벤트, 상황)


class MemoryStatus(Enum):
    """기억 상태"""
    ACTIVE = "active"              # 활성 상태
    ARCHIVED = "archived"          # 아카이브됨
    DELETED = "deleted"            # 삭제됨
    COMPRESSED = "compressed"      # 압축됨


@dataclass
class MetadataSchema:
    """메타데이터 표준 스키마"""
    
    # 공통 메타데이터
    version: str = "1.0"           # 스키마 버전
    source: str = ""               # 데이터 출처 (discord, system, api)
    session_id: Optional[str] = None # 세션 식별자
    
    # 품질 정보
    confidence: float = 1.0        # 데이터 신뢰도 (0.0-1.0)
    completeness: float = 1.0      # 데이터 완성도 (0.0-1.0)
    accuracy: float = 1.0          # 데이터 정확도 (0.0-1.0)
    
    # 중요도 정보
    importance_score: float = 0.0  # 중요도 점수 (0.0-1.0)
    importance_level: ImportanceLevel = ImportanceLevel.MEDIUM
    
    # 접근 통계
    access_count: int = 0          # 접근 횟수
    last_accessed: datetime = field(default_factory=datetime.now)
    
    # 압축 정보
    is_compressed: bool = False    # 압축 여부
    compression_ratio: float = 1.0 # 압축 비율
    
    # 상태 정보
    status: MemoryStatus = MemoryStatus.ACTIVE
    
    # 분류 정보
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # 처리 정보
    processed_at: datetime = field(default_factory=datetime.now)
    processing_time: float = 0.0   # 처리 시간 (초)
    ai_model: str = ""             # 사용된 AI 모델
    
    # 관계 정보
    parent_ids: List[str] = field(default_factory=list)  # 부모 기억 ID들
    child_ids: List[str] = field(default_factory=list)   # 자식 기억 ID들
    related_ids: List[str] = field(default_factory=list) # 관련 기억 ID들
    
    # 컨텍스트 정보
    context_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "version": self.version,
            "source": self.source,
            "session_id": self.session_id,
            "confidence": self.confidence,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "processed_at": self.processed_at.isoformat(),
            "processing_time": self.processing_time,
            "ai_model": self.ai_model,
            "parent_ids": self.parent_ids,
            "child_ids": self.child_ids,
            "related_ids": self.related_ids,
            "context_data": self.context_data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetadataSchema':
        """딕셔너리로부터 객체 생성"""
        return cls(
            version=data.get("version", "1.0"),
            source=data.get("source", ""),
            session_id=data.get("session_id"),
            confidence=data.get("confidence", 1.0),
            completeness=data.get("completeness", 1.0),
            accuracy=data.get("accuracy", 1.0),
            processed_at=datetime.fromisoformat(data.get("processed_at", datetime.now().isoformat())),
            processing_time=data.get("processing_time", 0.0),
            ai_model=data.get("ai_model", ""),
            parent_ids=data.get("parent_ids", []),
            child_ids=data.get("child_ids", []),
            related_ids=data.get("related_ids", []),
            context_data=data.get("context_data", {})
        )


@dataclass
class BaseMemory:
    """기본 기억 클래스 - 개선된 버전"""
    id: str
    user_id: str
    memory_type: MemoryType
    content: str
    importance: ImportanceLevel
    source: str = "system"  # 추가: 데이터 출처
    
    # 확장된 메타데이터
    metadata: MetadataSchema = field(default_factory=MetadataSchema)
    
    # 시간 정보
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    accessed_count: int = 0
    
    # 분류 및 검색
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    
    # 품질 및 상태
    status: MemoryStatus = MemoryStatus.ACTIVE
    is_archived: bool = False
    is_validated: bool = False
    validation_score: float = 0.0
    
    def __post_init__(self):
        """초기화 후 처리"""
        if not self.id:
            self.id = self.generate_id()
        
        # 태그 자동 생성
        if not self.tags:
            self.tags = self.extract_tags()
        
        # 키워드 자동 생성
        if not self.keywords:
            self.keywords = self.extract_keywords()
    
    def generate_id(self) -> str:
        """고유 ID 생성"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"{self.memory_type.value}_{self.user_id}_{timestamp}_{unique_id}"
    
    def extract_tags(self) -> List[str]:
        """내용에서 태그 자동 추출"""
        tags = []
        content_lower = self.content.lower()
        
        # 메모리 타입별 기본 태그
        type_tags = {
            MemoryType.ACTION: ['행동', 'action'],
            MemoryType.CONVERSATION: ['대화', 'conversation'],
            MemoryType.PROJECT: ['프로젝트', 'project'],
            MemoryType.PREFERENCE: ['선호도', 'preference'],
            MemoryType.SYSTEM: ['시스템', 'system'],
            MemoryType.LEARNING: ['학습', 'learning'],
            MemoryType.CONTEXT: ['맥락', 'context'],
            MemoryType.RELATIONSHIP: ['관계', 'relationship']
        }
        
        tags.extend(type_tags.get(self.memory_type, []))
        
        # 공통 키워드 태그
        common_keywords = {
            '일정': 'schedule', '할일': 'todo', '회의': 'meeting',
            '검색': 'search', '파일': 'file', '이메일': 'email',
            '노션': 'notion', '웹': 'web', '알림': 'notification',
            '중요': 'important', '긴급': 'urgent', '완료': 'completed'
        }
        
        for korean, english in common_keywords.items():
            if korean in content_lower:
                tags.extend([korean, english])
        
        return list(set(tags))  # 중복 제거
    
    def extract_keywords(self) -> List[str]:
        """내용에서 키워드 자동 추출"""
        # 간단한 키워드 추출 (향후 NLP 라이브러리로 개선 가능)
        import re
        
        # 한글, 영문 단어 추출
        korean_words = re.findall(r'[가-힣]{2,}', self.content)
        english_words = re.findall(r'[a-zA-Z]{3,}', self.content)
        
        # 중요한 단어들 필터링
        important_korean = [word for word in korean_words if len(word) >= 2]
        important_english = [word.lower() for word in english_words if len(word) >= 3]
        
        return list(set(important_korean + important_english))[:10]  # 상위 10개
    
    def update_access(self):
        """접근 정보 업데이트"""
        self.last_accessed = datetime.now()
        self.accessed_count += 1
        self.updated_at = datetime.now()
    
    def should_archive(self) -> bool:
        """아카이빙 필요 여부 판단"""
        if self.importance == ImportanceLevel.CRITICAL:
            return False
        
        archive_days = self.importance.auto_archive_days
        if archive_days <= 0:
            return False
        
        days_since_access = (datetime.now() - self.last_accessed).days
        return days_since_access >= archive_days
    
    def should_delete(self) -> bool:
        """삭제 필요 여부 판단"""
        if self.importance == ImportanceLevel.CRITICAL:
            return False
        
        retention_days = self.importance.retention_days
        if retention_days <= 0:
            return False
        
        days_since_created = (datetime.now() - self.created_at).days
        return days_since_created >= retention_days
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "importance": self.importance.value,
            "metadata": self.metadata.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "accessed_count": self.accessed_count,
            "tags": self.tags,
            "keywords": self.keywords,
            "categories": self.categories,
            "is_archived": self.is_archived,
            "is_validated": self.is_validated,
            "validation_score": self.validation_score
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseMemory':
        """딕셔너리로부터 객체 생성"""
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            metadata=MetadataSchema.from_dict(data.get("metadata", {})),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            accessed_count=data.get("accessed_count", 0),
            tags=data.get("tags", []),
            keywords=data.get("keywords", []),
            categories=data.get("categories", []),
            is_archived=data.get("is_archived", False),
            is_validated=data.get("is_validated", False),
            validation_score=data.get("validation_score", 0.0)
        )


@dataclass
class ActionReasoningPair:
    """행동-이유 페어 핵심 구조"""
    action: str                    # 수행한 행동
    reasoning: str                 # 행동을 선택한 이유
    context: str                   # 행동 당시의 상황/맥락
    outcome: str                   # 행동의 결과
    
    # 행동 분석 정보
    action_type: ActionType
    confidence_score: float        # 행동 선택 시 신뢰도
    success_rate: float           # 행동 성공률
    
    # 실행 정보
    tools_used: List[str] = field(default_factory=list)
    execution_time: float = 0.0    # 실행 시간 (초)
    error_messages: List[str] = field(default_factory=list)
    
    # 학습 정보
    learning_points: List[str] = field(default_factory=list)  # 학습한 점들
    improvement_suggestions: List[str] = field(default_factory=list)  # 개선 제안
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "context": self.context,
            "outcome": self.outcome,
            "action_type": self.action_type.value,
            "confidence_score": self.confidence_score,
            "success_rate": self.success_rate,
            "tools_used": self.tools_used,
            "execution_time": self.execution_time,
            "error_messages": self.error_messages,
            "learning_points": self.learning_points,
            "improvement_suggestions": self.improvement_suggestions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionReasoningPair':
        """딕셔너리로부터 객체 생성"""
        return cls(
            action=data["action"],
            reasoning=data["reasoning"],
            context=data["context"],
            outcome=data["outcome"],
            action_type=ActionType(data["action_type"]),
            confidence_score=data["confidence_score"],
            success_rate=data["success_rate"],
            tools_used=data.get("tools_used", []),
            execution_time=data.get("execution_time", 0.0),
            error_messages=data.get("error_messages", []),
            learning_points=data.get("learning_points", []),
            improvement_suggestions=data.get("improvement_suggestions", [])
        )


@dataclass
class ActionMemory(BaseMemory):
    """행동 기록 메모리 - 행동-이유 페어 기반"""
    action_reasoning_pair: Optional[ActionReasoningPair] = None
    
    # 추가 행동 정보
    user_request: str = ""         # 원본 사용자 요청
    ai_interpretation: str = ""    # AI의 요청 해석
    decision_process: str = ""     # 의사결정 과정
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.ACTION
        
        # content 자동 생성
        if self.action_reasoning_pair and not self.content:
            self.content = self._generate_content()
    
    def _generate_content(self) -> str:
        """행동-이유 페어로부터 content 생성"""
        pair = self.action_reasoning_pair
        if not pair:
            return "행동 정보 없음"
            
        return f"""
행동: {pair.action}
이유: {pair.reasoning}
상황: {pair.context}
결과: {pair.outcome}
사용 도구: {', '.join(pair.tools_used)}
성공률: {pair.success_rate:.2%}
        """.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "action_reasoning_pair": self.action_reasoning_pair.to_dict() if self.action_reasoning_pair else None,
            "user_request": self.user_request,
            "ai_interpretation": self.ai_interpretation,
            "decision_process": self.decision_process
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionMemory':
        """딕셔너리로부터 객체 생성"""
        base_memory = super().from_dict(data)
        
        action_reasoning_data = data.get("action_reasoning_pair")
        action_reasoning_pair = ActionReasoningPair.from_dict(action_reasoning_data) if action_reasoning_data else None
        
        return cls(
            id=base_memory.id,
            user_id=base_memory.user_id,
            memory_type=base_memory.memory_type,
            content=base_memory.content,
            importance=base_memory.importance,
            metadata=base_memory.metadata,
            created_at=base_memory.created_at,
            updated_at=base_memory.updated_at,
            last_accessed=base_memory.last_accessed,
            accessed_count=base_memory.accessed_count,
            tags=base_memory.tags,
            keywords=base_memory.keywords,
            categories=base_memory.categories,
            is_archived=base_memory.is_archived,
            is_validated=base_memory.is_validated,
            validation_score=base_memory.validation_score,
            action_reasoning_pair=action_reasoning_pair,
            user_request=data.get("user_request", ""),
            ai_interpretation=data.get("ai_interpretation", ""),
            decision_process=data.get("decision_process", "")
        )


@dataclass
class ConversationMemory(BaseMemory):
    """대화 기록 메모리"""
    user_message: str = ""
    ai_response: str = ""
    response_type: str = ""        # 응답 타입 (ACKNOWLEDGMENT, CLARIFICATION 등)
    tone_used: str = ""           # 사용된 톤 (전문적, 친근한 등)
    session_id: str = ""
    conversation_turn: int = 0     # 대화 순서
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.CONVERSATION
        
        # content 자동 생성
        if not self.content and self.user_message and self.ai_response:
            self.content = f"사용자: {self.user_message}\nAI: {self.ai_response}"


@dataclass 
class PreferenceMemory(BaseMemory):
    """사용자 선호도 메모리"""
    preference_category: str = ""  # 카테고리 (tone, schedule, communication 등)
    preference_value: Any = None   # 선호도 값
    confidence: float = 0.0       # 선호도 신뢰도
    learning_source: str = ""     # 학습 출처 (explicit, implicit, inferred)
    frequency: int = 0            # 관찰 빈도
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.PREFERENCE
        self.importance = ImportanceLevel.CRITICAL  # 선호도는 기본적으로 중요


# 중요도 자동 판단 시스템
class ImportanceCalculator:
    """중요도 자동 계산기"""
    
    @staticmethod
    def calculate_importance(memory: BaseMemory, 
                           context: Optional[Dict[str, Any]] = None) -> ImportanceLevel:
        """기억의 중요도를 자동 계산"""
        score = 0.0
        
        # 메모리 타입별 기본 점수
        type_scores = {
            MemoryType.ACTION: 3.0,
            MemoryType.CONVERSATION: 2.0,
            MemoryType.PROJECT: 4.0,
            MemoryType.PREFERENCE: 5.0,
            MemoryType.SYSTEM: 1.0,
            MemoryType.LEARNING: 4.0,
            MemoryType.CONTEXT: 2.0,
            MemoryType.RELATIONSHIP: 3.0
        }
        
        score += type_scores.get(memory.memory_type, 2.0)
        
        # 내용 길이에 따른 가중치
        content_length = len(memory.content)
        if content_length > 500:
            score += 1.0
        elif content_length > 200:
            score += 0.5
        
        # 메타데이터 품질에 따른 가중치
        if memory.metadata:
            score += memory.metadata.confidence * 0.5
            score += memory.metadata.completeness * 0.3
        
        # ActionMemory 특별 처리
        if isinstance(memory, ActionMemory) and memory.action_reasoning_pair:
            pair = memory.action_reasoning_pair
            # 성공률에 따른 가중치
            score += pair.success_rate * 1.0
            # 에러가 있으면 감점
            if pair.error_messages:
                score -= 0.5
            # 학습 포인트가 있으면 가점
            if pair.learning_points:
                score += len(pair.learning_points) * 0.2
        
        # 컨텍스트 정보 활용
        if context:
            # 사용자 명시적 중요도
            if context.get("user_marked_important"):
                score += 2.0
            # 반복 패턴
            if context.get("is_recurring_pattern"):
                score += 1.0
            # 시간 민감성
            if context.get("time_sensitive"):
                score += 0.5
        
        # 점수를 ImportanceLevel로 변환
        if score >= 5.0:
            return ImportanceLevel.CRITICAL
        elif score >= 4.0:
            return ImportanceLevel.HIGH
        elif score >= 3.0:
            return ImportanceLevel.MEDIUM
        elif score >= 2.0:
            return ImportanceLevel.LOW
        else:
            return ImportanceLevel.MINIMAL


# 유틸리티 함수들
def create_action_memory(user_id: str,
                        action: str,
                        reasoning: str,
                        context: str,
                        outcome: str,
                        action_type: ActionType,
                        confidence_score: float,
                        tools_used: Optional[List[str]] = None,
                        user_request: str = "",
                        **kwargs) -> ActionMemory:
    """ActionMemory 생성 헬퍼 함수"""
    
    action_reasoning_pair = ActionReasoningPair(
        action=action,
        reasoning=reasoning,
        context=context,
        outcome=outcome,
        action_type=action_type,
        confidence_score=confidence_score,
        success_rate=1.0 if "성공" in outcome.lower() else 0.5,
        tools_used=tools_used or [],
        **kwargs
    )
    
    memory = ActionMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.ACTION,
        content="",  # 자동 생성됨
        importance=ImportanceLevel.MEDIUM,  # 계산됨
        action_reasoning_pair=action_reasoning_pair,
        user_request=user_request
    )
    
    # 중요도 자동 계산
    memory.importance = ImportanceCalculator.calculate_importance(memory)
    
    return memory


def create_conversation_memory(user_id: str,
                             user_message: str,
                             ai_response: str,
                             response_type: str = "",
                             tone_used: str = "",
                             session_id: str = "") -> ConversationMemory:
    """ConversationMemory 생성 헬퍼 함수"""
    
    memory = ConversationMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.CONVERSATION,
        content="",  # 자동 생성됨
        importance=ImportanceLevel.MEDIUM,  # 계산됨
        user_message=user_message,
        ai_response=ai_response,
        response_type=response_type,
        tone_used=tone_used,
        session_id=session_id
    )
    
    # 중요도 자동 계산
    memory.importance = ImportanceCalculator.calculate_importance(memory)
    
    return memory


def create_preference_memory(user_id: str,
                           category: str,
                           value: Any,
                           confidence: float,
                           learning_source: str = "implicit") -> PreferenceMemory:
    """PreferenceMemory 생성 헬퍼 함수"""
    
    memory = PreferenceMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.PREFERENCE,
        content=f"선호도: {category} = {value}",
        importance=ImportanceLevel.CRITICAL,  # 선호도는 항상 중요
        preference_category=category,
        preference_value=value,
        confidence=confidence,
        learning_source=learning_source
    )
    
    return memory


# 스키마 버전 정보
SCHEMA_VERSION = "2.0"
COMPATIBLE_VERSIONS = ["1.0", "2.0"]


def validate_memory_schema(memory_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """메모리 데이터 스키마 유효성 검증"""
    errors = []
    
    # 필수 필드 확인
    required_fields = ["id", "user_id", "memory_type", "content", "importance"]
    for field in required_fields:
        if field not in memory_data:
            errors.append(f"필수 필드 누락: {field}")
    
    # 타입 확인
    if "memory_type" in memory_data:
        try:
            MemoryType(memory_data["memory_type"])
        except ValueError:
            errors.append(f"잘못된 memory_type: {memory_data['memory_type']}")
    
    if "importance" in memory_data:
        try:
            ImportanceLevel(memory_data["importance"])
        except ValueError:
            errors.append(f"잘못된 importance: {memory_data['importance']}")
    
    return len(errors) == 0, errors
