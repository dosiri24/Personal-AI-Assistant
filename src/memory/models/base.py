"""
Base Memory Models

기본 메모리 데이터 구조와 열거형들을 정의합니다.
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
    
    # 처리 정보
    processing_time: float = 0.0   # 처리 시간 (초)
    compression_ratio: float = 1.0 # 압축 비율
    
    # 중요도 점수
    importance_score: float = 0.0  # 계산된 중요도 점수
    access_count: int = 0          # 접근 횟수
    last_modified: datetime = field(default_factory=datetime.now)
    
    # 맥락 정보
    context_type: Optional[ContextType] = None
    related_memory_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "version": self.version,
            "source": self.source,
            "session_id": self.session_id,
            "confidence": self.confidence,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "processing_time": self.processing_time,
            "compression_ratio": self.compression_ratio,
            "importance_score": self.importance_score,
            "access_count": self.access_count,
            "last_modified": self.last_modified.isoformat(),
            "context_type": self.context_type.value if self.context_type else None,
            "related_memory_ids": self.related_memory_ids,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetadataSchema':
        """딕셔너리로부터 객체 생성"""
        context_type = None
        if data.get("context_type"):
            context_type = ContextType(data["context_type"])
        
        return cls(
            version=data.get("version", "1.0"),
            source=data.get("source", ""),
            session_id=data.get("session_id"),
            confidence=data.get("confidence", 1.0),
            completeness=data.get("completeness", 1.0),
            accuracy=data.get("accuracy", 1.0),
            processing_time=data.get("processing_time", 0.0),
            compression_ratio=data.get("compression_ratio", 1.0),
            importance_score=data.get("importance_score", 0.0),
            access_count=data.get("access_count", 0),
            last_modified=datetime.fromisoformat(data.get("last_modified", datetime.now().isoformat())),
            context_type=context_type,
            related_memory_ids=data.get("related_memory_ids", []),
            tags=data.get("tags", [])
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
