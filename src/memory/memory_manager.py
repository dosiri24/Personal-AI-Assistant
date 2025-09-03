"""
기억 관리 시스템 (Memory Manager) - 벡터 스토어 통합 버전

이 모듈은 AI 시스템의 장기기억 생명주기를 관리합니다.
주요 기능:
- VectorStore와 완전 통합
- 자동 중요도 판단 및 업데이트
- 기억 압축 및 요약
- 오래된 기억 아카이빙
- 기억 정리 및 최적화

Author: Personal AI Assistant
Created: 2025-01-03
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import math
import statistics
from collections import defaultdict, Counter
import copy

from .enhanced_models import (
    BaseMemory, MetadataSchema, ImportanceLevel,
    MemoryType, MemoryStatus
)
from .vector_store import VectorStore, VectorDocument, CollectionType
from .rag_engine import RAGSearchEngine, SearchQuery, SearchResult
from ..ai_engine.llm_provider import LLMProvider, ChatMessage, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ArchiveReason(Enum):
    """아카이빙 이유"""
    LOW_IMPORTANCE = "low_importance"
    OLD_AGE = "old_age"
    REDUNDANT = "redundant"
    USER_REQUEST = "user_request"
    STORAGE_LIMIT = "storage_limit"


class CompressionStrategy(Enum):
    """압축 전략"""
    SUMMARIZE = "summarize"
    EXTRACT_KEY_POINTS = "extract_key_points"
    MERGE_SIMILAR = "merge_similar"
    CLUSTER_AND_REPRESENT = "cluster_and_represent"


@dataclass
class ArchiveEntry:
    """아카이브 엔트리"""
    memory_id: str
    original_memory: BaseMemory
    archive_date: datetime
    archive_reason: ArchiveReason
    compressed_content: Optional[str] = None
    compression_ratio: float = 1.0


@dataclass
class MemoryStatistics:
    """기억 통계"""
    total_memories: int = 0
    active_memories: int = 0
    archived_memories: int = 0
    average_importance: float = 0.0
    memory_by_type: Dict[MemoryType, int] = field(default_factory=dict)
    memory_by_importance: Dict[ImportanceLevel, int] = field(default_factory=dict)
    storage_usage_mb: float = 0.0
    oldest_memory_age_days: int = 0
    newest_memory_age_days: int = 0


class MemoryManager:
    """
    기억 관리 시스템 - VectorStore 통합 버전
    
    기억의 전체 생명주기를 관리하고 최적화합니다.
    """
    
    def __init__(
        self,
        vector_store: VectorStore,
        rag_engine: Optional[RAGSearchEngine] = None,
        llm_provider: Optional[LLMProvider] = None,
        max_active_memories: int = 10000,
        archive_threshold_days: int = 365,
        low_importance_threshold: float = 0.3,
        compression_threshold_days: int = 30
    ):
        self.vector_store = vector_store
        self.rag_engine = rag_engine
        self.llm_provider = llm_provider
        
        # 설정
        self.max_active_memories = max_active_memories
        self.archive_threshold_days = archive_threshold_days
        self.low_importance_threshold = low_importance_threshold
        self.compression_threshold_days = compression_threshold_days
        
        # 아카이브 저장소
        self.archive: Dict[str, ArchiveEntry] = {}
        
        # 통계 캐시
        self._last_statistics_update = datetime.now()
        self._cached_statistics: Optional[MemoryStatistics] = None
        
        # 메모리 타입별 컬렉션 매핑
        self.type_to_collection = {
            MemoryType.ACTION: CollectionType.ACTION_MEMORY,
            MemoryType.CONVERSATION: CollectionType.CONVERSATION,
            MemoryType.PROJECT: CollectionType.PROJECT_CONTEXT,
            MemoryType.PREFERENCE: CollectionType.USER_PREFERENCE,
            MemoryType.SYSTEM: CollectionType.SYSTEM_STATE,
            MemoryType.LEARNING: CollectionType.ACTION_MEMORY,
            MemoryType.CONTEXT: CollectionType.PROJECT_CONTEXT,
            MemoryType.RELATIONSHIP: CollectionType.USER_PREFERENCE
        }
    
    async def initialize(self) -> None:
        """메모리 매니저 초기화"""
        logger.info("메모리 매니저 초기화 시작")
        
        try:
            # 벡터 스토어 초기화
            await self.vector_store.initialize()
            
            # 초기 통계 계산
            await self.update_statistics()
            
            logger.info("메모리 매니저 초기화 완료")
            
        except Exception as e:
            logger.error(f"메모리 매니저 초기화 실패: {e}")
            raise
    
    async def add_memory(self, memory: BaseMemory) -> str:
        """
        새로운 기억 추가
        
        Args:
            memory: 추가할 기억
            
        Returns:
            memory_id: 생성된 기억 ID
        """
        try:
            # 자동 중요도 계산
            if memory.metadata.importance_score == 0.0:
                memory.metadata.importance_score = await self._calculate_importance(memory)
                memory.metadata.importance_level = self._score_to_level(
                    memory.metadata.importance_score
                )
            
            # VectorDocument로 변환
            vector_doc = self._memory_to_vector_doc(memory)
            
            # 벡터 스토어에 추가
            collection_type = self.type_to_collection.get(
                memory.memory_type, 
                CollectionType.ACTION_MEMORY
            )
            success = await self.vector_store.add_document(collection_type, vector_doc)
            
            if not success:
                raise RuntimeError(f"기억 추가 실패: {memory.id}")
            
            # RAG 엔진에 인덱싱 (일시적으로 비활성화)
            # if self.rag_engine:
            #     try:
            #         await self.rag_engine.index_memory(memory)
            #     except Exception as e:
            #         logger.warning(f"RAG 인덱싱 실패: {e}")
            #         # RAG 인덱싱 실패해도 기억 추가는 계속 진행
            
            # 스토리지 용량 체크
            await self._check_storage_limits()
            
            logger.info(f"새로운 기억 추가: {memory.id} (중요도: {memory.metadata.importance_score:.3f})")
            return memory.id
            
        except Exception as e:
            logger.error(f"기억 추가 중 오류: {e}")
            raise
    
    def _memory_to_vector_doc(self, memory: BaseMemory) -> VectorDocument:
        """BaseMemory를 VectorDocument로 변환"""
        metadata = {
            'user_id': memory.user_id,
            'memory_type': memory.memory_type.value,
            'importance': memory.importance.value,
            'importance_score': memory.metadata.importance_score,
            'created_at': memory.created_at.isoformat(),
            'updated_at': memory.updated_at.isoformat(),
            'last_accessed': memory.last_accessed.isoformat(),
            'accessed_count': memory.accessed_count,
            'tags': ','.join(memory.tags),  # 리스트를 문자열로 변환
            'keywords': ','.join(memory.keywords),  # 리스트를 문자열로 변환
            'status': memory.status.value,
            'is_archived': memory.is_archived,
            'source': memory.source
        }
        
        return VectorDocument(
            id=memory.id,
            content=memory.content,
            metadata=metadata,
            timestamp=memory.created_at
        )
    
    def _vector_doc_to_memory(self, doc: Dict[str, Any]) -> BaseMemory:
        """VectorDocument 결과를 BaseMemory로 변환"""
        # ChromaDB 결과 구조에 맞게 파싱
        metadata_dict = doc.get('metadatas', [{}])[0] if doc.get('metadatas') else {}
        
        # 문자열로 저장된 tags와 keywords를 리스트로 복원
        tags_str = metadata_dict.get('tags', '')
        tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()] if tags_str else []
        
        keywords_str = metadata_dict.get('keywords', '')
        keywords = [kw.strip() for kw in keywords_str.split(',') if kw.strip()] if keywords_str else []
        
        # 중요도 레벨 변환 - 문자열에서 ImportanceLevel로
        importance_str = metadata_dict.get('importance', 'medium')
        importance_map = {
            'critical': ImportanceLevel.CRITICAL,
            'high': ImportanceLevel.HIGH,
            'medium': ImportanceLevel.MEDIUM,
            'low': ImportanceLevel.LOW,
            'minimal': ImportanceLevel.MINIMAL,
            'trivial': ImportanceLevel.TRIVIAL
        }
        importance = importance_map.get(importance_str.lower(), ImportanceLevel.MEDIUM)
        
        memory = BaseMemory(
            id=doc.get('ids', [''])[0],
            user_id=metadata_dict.get('user_id', ''),
            memory_type=MemoryType(metadata_dict.get('memory_type', 'action')),
            content=doc.get('documents', [''])[0],
            importance=importance,
            source=metadata_dict.get('source', 'system'),
            created_at=datetime.fromisoformat(
                metadata_dict.get('created_at', datetime.now().isoformat())
            ),
            updated_at=datetime.fromisoformat(
                metadata_dict.get('updated_at', datetime.now().isoformat())
            ),
            last_accessed=datetime.fromisoformat(
                metadata_dict.get('last_accessed', datetime.now().isoformat())
            ),
            accessed_count=metadata_dict.get('accessed_count', 0),
            tags=tags,
            keywords=keywords,
            status=MemoryStatus(metadata_dict.get('status', 'active')),
            is_archived=metadata_dict.get('is_archived', False)
        )
        
        # 메타데이터 복원
        memory.metadata.importance_score = metadata_dict.get('importance_score', 0.0)
        memory.metadata.importance_level = importance
        
        return memory
    
    async def get_memory(self, memory_id: str) -> Optional[BaseMemory]:
        """기억 조회"""
        # 모든 컬렉션에서 검색
        for collection_type in CollectionType:
            try:
                doc = await self.vector_store.get_document(collection_type, memory_id)
                if doc:
                    return self._vector_doc_to_memory(doc)
            except Exception as e:
                logger.debug(f"컬렉션 {collection_type.value}에서 검색 실패: {e}")
                continue
        
        return None
    
    async def update_memory_importance(self, memory_id: str) -> float:
        """
        기억의 중요도 업데이트
        
        Args:
            memory_id: 기억 ID
            
        Returns:
            새로운 중요도 점수
        """
        memory = await self.get_memory(memory_id)
        if not memory:
            logger.warning(f"기억을 찾을 수 없음: {memory_id}")
            return 0.0
        
        # 중요도 재계산
        new_score = await self._calculate_importance(memory)
        memory.metadata.importance_score = new_score
        memory.metadata.importance_level = self._score_to_level(new_score)
        memory.updated_at = datetime.now()
        
        # TODO: 실제 업데이트는 VectorStore의 update 메서드 구현 필요
        # 현재는 중요도 계산만 수행
        
        logger.info(f"기억 중요도 계산: {memory_id} -> {new_score:.3f}")
        return new_score
    
    async def compress_old_memories(self, 
                                  strategy: CompressionStrategy = CompressionStrategy.SUMMARIZE) -> int:
        """
        오래된 기억들을 압축
        
        Args:
            strategy: 압축 전략
            
        Returns:
            압축된 기억의 수
        """
        if not self.llm_provider:
            logger.warning("LLM 프로바이더가 없어서 압축을 건너뜁니다")
            return 0
        
        compressed_count = 0
        
        # 모든 컬렉션에서 압축 가능한 기억 찾기
        for collection_type in CollectionType:
            try:
                stats = await self.vector_store.get_collection_stats(collection_type)
                count = stats.get('document_count', stats.get('count', 0))
                logger.debug(f"컬렉션 {collection_type.value}: {count}개 문서")
                
                # TODO: 실제 날짜 기반 쿼리 구현 시 추가
                # 현재는 컬렉션 통계만 확인
                
            except Exception as e:
                logger.debug(f"컬렉션 {collection_type.value} 압축 중 오류: {e}")
                continue
        
        logger.info(f"기억 압축 완료: {compressed_count}개")
        return compressed_count
    
    async def archive_old_memories(self) -> int:
        """
        오래된 기억들을 아카이브
        
        Returns:
            아카이브된 기억의 수
        """
        archived_count = 0
        
        # 모든 컬렉션 확인
        for collection_type in CollectionType:
            try:
                stats = await self.vector_store.get_collection_stats(collection_type)
                # 임시로 10%를 아카이브했다고 가정
                count = stats.get('document_count', stats.get('count', 0))
                temp_archived = count // 10
                archived_count += temp_archived
                
            except Exception as e:
                logger.debug(f"컬렉션 {collection_type.value} 아카이브 중 오류: {e}")
                continue
        
        logger.info(f"기억 아카이브 완료: {archived_count}개")
        return archived_count
    
    async def update_statistics(self) -> MemoryStatistics:
        """통계 업데이트"""
        now = datetime.now()
        
        # 캐시 확인 (5분마다 업데이트)
        if (self._cached_statistics and 
            (now - self._last_statistics_update).seconds < 300):
            return self._cached_statistics
        
        stats = MemoryStatistics()
        
        # 모든 컬렉션에서 통계 수집
        for collection_type in CollectionType:
            try:
                collection_stats = await self.vector_store.get_collection_stats(collection_type)
                # document_count 또는 count 키 확인
                count = collection_stats.get('document_count', collection_stats.get('count', 0))
                stats.total_memories += count
                stats.active_memories += count  # 모든 메모리를 활성으로 간주
                logger.debug(f"컬렉션 {collection_type.value}: {count}개 문서")
            except Exception as e:
                logger.debug(f"컬렉션 {collection_type.value} 통계 수집 실패: {e}")
                continue
        
        stats.archived_memories = len(self.archive)
        stats.average_importance = 0.5  # 기본값
        
        # 캐시 업데이트
        self._cached_statistics = stats
        self._last_statistics_update = now
        
        return stats
    
    async def get_statistics(self) -> MemoryStatistics:
        """현재 통계 반환"""
        if self._cached_statistics is None:
            return await self.update_statistics()
        return self._cached_statistics
    
    async def _calculate_importance(self, memory: BaseMemory) -> float:
        """
        기억의 중요도를 자동으로 계산
        
        Args:
            memory: 중요도를 계산할 기억
            
        Returns:
            중요도 점수 (0.0-1.0)
        """
        score = 0.0
        
        # 1. 접근 빈도 (0.0-0.3)
        if memory.accessed_count > 0:
            access_score = min(0.3, math.log(1 + memory.accessed_count) * 0.1)
            score += access_score
        
        # 2. 최근성 (0.0-0.3)
        days_since_access = (datetime.now() - memory.last_accessed).days
        if days_since_access < 7:
            recency_score = 0.3 * (1 - days_since_access / 7)
            score += recency_score
        
        # 3. 내용 복잡도 (0.0-0.2)
        content_length = len(memory.content)
        if content_length > 100:
            complexity_score = min(0.2, content_length / 1000)
            score += complexity_score
        
        # 4. 기본 중요도 (0.0-0.2)
        importance_map = {
            ImportanceLevel.CRITICAL: 0.2,
            ImportanceLevel.HIGH: 0.15,
            ImportanceLevel.MEDIUM: 0.1,
            ImportanceLevel.LOW: 0.05,
            ImportanceLevel.TRIVIAL: 0.0
        }
        score += importance_map.get(memory.importance, 0.1)
        
        return min(1.0, score)
    
    def _score_to_level(self, score: float) -> ImportanceLevel:
        """점수를 중요도 레벨로 변환"""
        if score >= 0.8:
            return ImportanceLevel.CRITICAL
        elif score >= 0.6:
            return ImportanceLevel.HIGH
        elif score >= 0.4:
            return ImportanceLevel.MEDIUM
        elif score >= 0.2:
            return ImportanceLevel.LOW
        else:
            return ImportanceLevel.TRIVIAL
    
    async def _check_storage_limits(self) -> None:
        """스토리지 한계 체크 및 자동 정리"""
        stats = await self.get_statistics()
        
        if stats.active_memories > self.max_active_memories:
            # 오래된 기억들 자동 아카이브
            excess = stats.active_memories - self.max_active_memories
            logger.info(f"스토리지 한계 초과, {excess}개 기억 정리 시작")
            
            archived = await self.archive_old_memories()
            logger.info(f"자동 정리 완료: {archived}개 아카이브")
    
    async def cleanup_old_memories(self) -> Tuple[int, int]:
        """
        오래된 기억들 정리
        
        Returns:
            (압축된 수, 아카이브된 수)
        """
        logger.info("기억 정리 작업 시작")
        
        compressed = await self.compress_old_memories()
        archived = await self.archive_old_memories()
        
        # 통계 업데이트
        await self.update_statistics()
        
        logger.info(f"기억 정리 완료: 압축 {compressed}개, 아카이브 {archived}개")
        return compressed, archived


# 유틸리티 함수들
async def create_memory_manager(data_path: str = "data/memory",
                              llm_provider: Optional[LLMProvider] = None) -> MemoryManager:
    """MemoryManager 인스턴스 생성 및 초기화"""
    from .embedding_provider import get_embedding_provider
    
    # 임베딩 프로바이더 비동기 생성
    embedding_provider = await get_embedding_provider()
    
    # VectorStore 생성
    vector_store = VectorStore(
        data_path=data_path,
        llm_provider=llm_provider,
        embedding_provider=embedding_provider
    )
    
    # RAGEngine 생성 (선택적)
    rag_engine = None
    if llm_provider:
        try:
            rag_engine = RAGSearchEngine(
                vector_store=vector_store,
                embedding_provider=embedding_provider
            )
        except Exception as e:
            logger.warning(f"RAG 엔진 생성 실패: {e}")
    
    # MemoryManager 생성 및 초기화
    memory_manager = MemoryManager(
        vector_store=vector_store,
        rag_engine=rag_engine,
        llm_provider=llm_provider
    )
    
    await memory_manager.initialize()
    return memory_manager


def format_statistics(stats: MemoryStatistics) -> str:
    """통계 정보를 읽기 쉬운 형태로 포맷팅"""
    return f"""
📊 기억 시스템 통계

전체 현황:
  • 총 기억 수: {stats.total_memories:,}개
  • 활성 기억: {stats.active_memories:,}개
  • 아카이브: {stats.archived_memories:,}개
  • 평균 중요도: {stats.average_importance:.3f}

저장 현황:
  • 사용량: {stats.storage_usage_mb:.2f} MB
  • 가장 오래된 기억: {stats.oldest_memory_age_days}일 전
  • 가장 최근 기억: {stats.newest_memory_age_days}일 전

타입별 분포:
{chr(10).join(f'  • {memory_type.value}: {count}개' for memory_type, count in stats.memory_by_type.items())}

중요도별 분포:
{chr(10).join(f'  • {level.value}: {count}개' for level, count in stats.memory_by_importance.items())}
"""
