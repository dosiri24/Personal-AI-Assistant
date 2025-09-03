"""
기억 관리 시스템 (Memory Manager) - 단순화 버전

이 모듈은 AI 시스템의 장기기억 생명주기를 관리합니다.
주요 기능:
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
import statistics
from collections import defaultdict, Counter

from .enhanced_models import (
    BaseMemory, MetadataSchema, ImportanceLevel,
    MemoryType, MemoryStatus
)
from ..ai_engine.llm_provider import LLMProvider
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
    SUMMARIZE = "summarize"  # LLM을 사용한 요약
    EXTRACT_KEY_POINTS = "extract_key_points"  # 핵심 포인트만 추출


@dataclass
class ArchiveEntry:
    """아카이브 엔트리"""
    memory_id: str
    original_memory: BaseMemory
    archive_date: datetime
    archive_reason: ArchiveReason
    compressed_content: Optional[str] = None
    compression_ratio: float = 1.0  # 압축 비율 (0.0-1.0)


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
    기억 관리 시스템
    
    기억의 전체 생명주기를 관리하고 최적화합니다.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        max_active_memories: int = 10000,
        archive_threshold_days: int = 365,
        low_importance_threshold: float = 0.3,
        compression_threshold_days: int = 30
    ):
        self.llm_provider = llm_provider
        
        # 설정
        self.max_active_memories = max_active_memories
        self.archive_threshold_days = archive_threshold_days
        self.low_importance_threshold = low_importance_threshold
        self.compression_threshold_days = compression_threshold_days
        
        # 메모리 저장소 (간단한 딕셔너리)
        self.memories: Dict[str, BaseMemory] = {}
        
        # 아카이브 저장소
        self.archive: Dict[str, ArchiveEntry] = {}
        
        # 통계
        self._last_statistics_update = datetime.now()
        self._cached_statistics: Optional[MemoryStatistics] = None
    
    async def initialize(self) -> None:
        """메모리 매니저 초기화"""
        logger.info("메모리 매니저 초기화 시작")
        
        # 초기 통계 계산
        await self.update_statistics()
        
        logger.info("메모리 매니저 초기화 완료")
    
    async def add_memory(self, memory: BaseMemory) -> str:
        """
        새로운 기억 추가
        
        Args:
            memory: 추가할 기억
            
        Returns:
            memory_id: 생성된 기억 ID
        """
        # 자동 중요도 계산
        if memory.metadata.importance_score == 0.0:
            memory.metadata.importance_score = await self._calculate_importance(memory)
            memory.metadata.importance_level = self._score_to_level(
                memory.metadata.importance_score
            )
        
        # 메모리 저장
        self.memories[memory.id] = memory
        
        # 스토리지 용량 체크 및 정리
        await self._check_storage_limits()
        
        logger.info(f"새로운 기억 추가: {memory.id} (중요도: {memory.metadata.importance_score:.3f})")
        return memory.id
    
    async def update_memory_importance(self, memory_id: str) -> float:
        """
        기억의 중요도 재계산 및 업데이트
        
        Args:
            memory_id: 업데이트할 기억 ID
            
        Returns:
            new_importance_score: 새로운 중요도 점수
        """
        # 기억 조회
        memory = self.memories.get(memory_id)
        if not memory:
            raise ValueError(f"기억을 찾을 수 없습니다: {memory_id}")
        
        # 중요도 재계산
        new_score = await self._calculate_importance(memory)
        
        # 업데이트
        memory.metadata.importance_score = new_score
        memory.metadata.importance_level = self._score_to_level(new_score)
        memory.metadata.last_accessed = datetime.now()
        
        logger.info(f"기억 {memory_id} 중요도 업데이트: {new_score:.3f}")
        return new_score
    
    async def compress_old_memories(
        self,
        strategy: CompressionStrategy = CompressionStrategy.SUMMARIZE,
        days_threshold: Optional[int] = None
    ) -> int:
        """
        오래된 기억들을 압축
        
        Args:
            strategy: 압축 전략
            days_threshold: 압축 대상 일수 임계값
            
        Returns:
            compressed_count: 압축된 기억 수
        """
        if days_threshold is None:
            days_threshold = self.compression_threshold_days
        
        cutoff_date = datetime.now() - timedelta(days=days_threshold)
        
        # 압축 대상 기억들 조회
        target_memories = [
            memory for memory in self.memories.values()
            if (memory.created_at < cutoff_date and 
                memory.metadata.status == MemoryStatus.ACTIVE and
                not memory.metadata.is_compressed)
        ]
        
        compressed_count = 0
        
        for memory in target_memories:
            try:
                compressed_content = await self._compress_memory_content(memory, strategy)
                if compressed_content:
                    # 원본 내용을 압축된 내용으로 대체
                    original_length = len(memory.content)
                    memory.content = compressed_content
                    memory.metadata.is_compressed = True
                    memory.metadata.compression_ratio = len(compressed_content) / original_length
                    memory.metadata.last_accessed = datetime.now()
                    
                    compressed_count += 1
                    
            except Exception as e:
                logger.error(f"기억 {memory.id} 압축 실패: {e}")
        
        logger.info(f"기억 압축 완료: {compressed_count}개 압축됨")
        return compressed_count
    
    async def archive_memories(
        self,
        criteria: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        기억들을 아카이브로 이동
        
        Args:
            criteria: 아카이브 기준
            
        Returns:
            archived_count: 아카이브된 기억 수
        """
        if criteria is None:
            criteria = {
                'max_age_days': self.archive_threshold_days,
                'min_importance': self.low_importance_threshold
            }
        
        # 아카이브 대상 선정
        candidates = await self._find_archive_candidates(criteria)
        
        archived_count = 0
        
        for memory, reason in candidates:
            try:
                # 압축된 버전 생성
                compressed_content = await self._create_compressed_summary(memory)
                
                # 아카이브 엔트리 생성
                archive_entry = ArchiveEntry(
                    memory_id=memory.id,
                    original_memory=memory,
                    archive_date=datetime.now(),
                    archive_reason=reason,
                    compressed_content=compressed_content,
                    compression_ratio=len(compressed_content) / len(memory.content) if compressed_content else 1.0
                )
                
                # 아카이브에 추가
                self.archive[memory.id] = archive_entry
                
                # 메모리에서 상태 업데이트
                memory.metadata.status = MemoryStatus.ARCHIVED
                
                archived_count += 1
                
            except Exception as e:
                logger.error(f"기억 {memory.id} 아카이브 실패: {e}")
        
        logger.info(f"기억 아카이브 완료: {archived_count}개 아카이브됨")
        return archived_count
    
    async def get_memory_statistics(self, force_update: bool = False) -> MemoryStatistics:
        """
        기억 통계 조회
        
        Args:
            force_update: 강제 업데이트 여부
            
        Returns:
            statistics: 기억 통계
        """
        # 캐시된 통계가 있고 최근 것이면 반환
        if (not force_update and 
            self._cached_statistics and 
            (datetime.now() - self._last_statistics_update).seconds < 300):  # 5분 캐시
            return self._cached_statistics
        
        await self.update_statistics()
        return self._cached_statistics or MemoryStatistics()
    
    async def update_statistics(self) -> None:
        """통계 정보 업데이트"""
        logger.debug("기억 통계 업데이트 시작")
        
        # 모든 기억 조회
        all_memories = list(self.memories.values())
        active_memories = [m for m in all_memories if m.metadata.status == MemoryStatus.ACTIVE]
        
        # 기본 통계
        stats = MemoryStatistics()
        stats.total_memories = len(all_memories)
        stats.active_memories = len(active_memories)
        stats.archived_memories = len(self.archive)
        
        if active_memories:
            # 중요도 평균
            importance_scores = [m.metadata.importance_score for m in active_memories]
            stats.average_importance = statistics.mean(importance_scores)
            
            # 타입별 분포
            type_counter = Counter([m.memory_type for m in active_memories])
            stats.memory_by_type = dict(type_counter)
            
            # 중요도 레벨별 분포
            level_counter = Counter([m.importance for m in active_memories])
            stats.memory_by_importance = dict(level_counter)
            
            # 저장 용량 추정 (문자 수 기반)
            total_chars = sum(len(m.content) for m in active_memories)
            stats.storage_usage_mb = total_chars * 2 / (1024 * 1024)  # UTF-8 기준 근사치
            
            # 연령 정보
            now = datetime.now()
            ages = [(now - m.created_at).days for m in active_memories]
            stats.oldest_memory_age_days = max(ages) if ages else 0
            stats.newest_memory_age_days = min(ages) if ages else 0
        
        self._cached_statistics = stats
        self._last_statistics_update = datetime.now()
        
        logger.debug(f"통계 업데이트 완료: 활성 {stats.active_memories}개, 아카이브 {stats.archived_memories}개")
    
    async def _calculate_importance(self, memory: BaseMemory) -> float:
        """
        기억의 중요도 자동 계산
        
        Args:
            memory: 평가할 기억
            
        Returns:
            importance_score: 중요도 점수 (0.0-1.0)
        """
        factors = []
        
        # 1. 기본 중요도 (기존 점수 참고)
        if memory.metadata.importance_score > 0:
            factors.append(('base', memory.metadata.importance_score, 0.3))
        
        # 2. 접근 빈도
        access_factor = min(memory.metadata.access_count / 10.0, 1.0)
        factors.append(('access_frequency', access_factor, 0.2))
        
        # 3. 최근성
        days_since_created = (datetime.now() - memory.created_at).days
        recency_factor = max(0.0, 1.0 - (days_since_created / 365.0))
        factors.append(('recency', recency_factor, 0.2))
        
        # 4. 내용 복잡도 (길이 기반)
        content_length = len(memory.content)
        complexity_factor = min(content_length / 1000.0, 1.0)
        factors.append(('complexity', complexity_factor, 0.3))
        
        # 가중 평균 계산
        weighted_sum = sum(score * weight for _, score, weight in factors)
        total_weight = sum(weight for _, _, weight in factors)
        
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        logger.debug(f"중요도 계산 완료: {final_score:.3f} (요인: {factors})")
        return min(max(final_score, 0.0), 1.0)  # 0.0-1.0 범위로 제한
    
    def _score_to_level(self, score: float) -> ImportanceLevel:
        """중요도 점수를 레벨로 변환"""
        if score >= 0.8:
            return ImportanceLevel.CRITICAL
        elif score >= 0.6:
            return ImportanceLevel.HIGH
        elif score >= 0.4:
            return ImportanceLevel.MEDIUM
        elif score >= 0.2:
            return ImportanceLevel.LOW
        elif score >= 0.1:
            return ImportanceLevel.MINIMAL
        else:
            return ImportanceLevel.TRIVIAL
    
    async def _compress_memory_content(
        self, 
        memory: BaseMemory,
        strategy: CompressionStrategy
    ) -> Optional[str]:
        """
        기억 내용 압축
        
        Args:
            memory: 압축할 기억
            strategy: 압축 전략
            
        Returns:
            compressed_content: 압축된 내용 (실패시 None)
        """
        try:
            if strategy == CompressionStrategy.SUMMARIZE:
                # LLM을 사용한 요약
                from ..ai_engine.llm_provider import ChatMessage
                
                messages = [
                    ChatMessage(
                        role="user",
                        content=f"""다음 내용을 핵심 정보만 포함하여 간결하게 요약해주세요:

원본 내용:
{memory.content}

요약 조건:
- 원본 길이의 30% 이하로 압축
- 핵심 정보와 중요한 세부사항 유지
- 명확하고 이해하기 쉬운 문장으로 작성
"""
                    )
                ]
                
                response = await self.llm_provider.generate_response(messages, max_tokens=300)
                return response.content.strip()
                
            elif strategy == CompressionStrategy.EXTRACT_KEY_POINTS:
                # 핵심 포인트 추출
                lines = memory.content.split('\n')
                key_lines = [line for line in lines if len(line.strip()) > 20][:5]  # 상위 5개 라인
                return '\n'.join(key_lines)
                
            else:
                logger.warning(f"지원하지 않는 압축 전략: {strategy}")
                return None
                
        except Exception as e:
            logger.error(f"기억 압축 실패: {e}")
            return None
    
    async def _find_archive_candidates(
        self, 
        criteria: Dict[str, Any]
    ) -> List[Tuple[BaseMemory, ArchiveReason]]:
        """
        아카이브 후보 기억들 찾기
        
        Args:
            criteria: 아카이브 기준
            
        Returns:
            candidates: (기억, 아카이브 이유) 튜플 리스트
        """
        candidates = []
        
        # 모든 활성 기억 조회
        active_memories = [
            m for m in self.memories.values() 
            if m.metadata.status == MemoryStatus.ACTIVE
        ]
        
        now = datetime.now()
        
        for memory in active_memories:
            reasons = []
            
            # 연령 기준
            age_days = (now - memory.created_at).days
            if age_days > criteria.get('max_age_days', self.archive_threshold_days):
                reasons.append(ArchiveReason.OLD_AGE)
            
            # 중요도 기준
            if memory.metadata.importance_score < criteria.get('min_importance', self.low_importance_threshold):
                reasons.append(ArchiveReason.LOW_IMPORTANCE)
            
            # 후보로 선정
            if reasons:
                # 첫 번째 이유를 주요 이유로 사용
                candidates.append((memory, reasons[0]))
        
        return candidates
    
    async def _create_compressed_summary(self, memory: BaseMemory) -> str:
        """
        기억의 압축된 요약 생성
        
        Args:
            memory: 요약할 기억
            
        Returns:
            summary: 압축된 요약
        """
        try:
            from ..ai_engine.llm_provider import ChatMessage
            
            messages = [
                ChatMessage(
                    role="user", 
                    content=f"""다음 기억을 한 문장으로 핵심만 요약해주세요:

{memory.content}

조건:
- 50단어 이내
- 가장 중요한 정보만 포함
- 명확하고 간결하게
"""
                )
            ]
            
            response = await self.llm_provider.generate_response(messages, max_tokens=100)
            return response.content.strip()
            
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            # 기본 요약 생성
            words = memory.content.split()[:20]
            return " ".join(words) + "..."
    
    async def _check_storage_limits(self) -> None:
        """저장소 용량 체크 및 필요시 정리"""
        active_count = len([m for m in self.memories.values() if m.metadata.status == MemoryStatus.ACTIVE])
        
        if active_count > self.max_active_memories:
            logger.warning(f"활성 기억 수 한계 도달: {active_count}/{self.max_active_memories}")
            
            # 오래되고 중요도가 낮은 기억들 자동 아카이브
            excess_count = active_count - self.max_active_memories
            await self._auto_archive_by_priority(excess_count)
    
    async def _auto_archive_by_priority(self, target_count: int) -> int:
        """
        우선순위에 따른 자동 아카이브
        
        Args:
            target_count: 목표 아카이브 수
            
        Returns:
            archived_count: 실제 아카이브된 수
        """
        # 모든 활성 기억 조회
        active_memories = [
            m for m in self.memories.values() 
            if m.metadata.status == MemoryStatus.ACTIVE
        ]
        
        # 우선순위 계산 (낮을수록 먼저 아카이브)
        priority_memories = []
        now = datetime.now()
        
        for memory in active_memories:
            age_days = (now - memory.created_at).days
            priority = (
                memory.metadata.importance_score * 0.5 +  # 중요도 (높을수록 낮은 우선순위)
                (1.0 - min(age_days / 365.0, 1.0)) * 0.3 +  # 최근성 (높을수록 낮은 우선순위)
                min(memory.metadata.access_count / 10.0, 1.0) * 0.2  # 접근 빈도
            )
            priority_memories.append((priority, memory))
        
        # 우선순위 낮은 순으로 정렬
        priority_memories.sort(key=lambda x: x[0])
        
        # 상위 target_count 개를 아카이브
        archived_count = 0
        for priority, memory in priority_memories[:target_count]:
            try:
                archive_entry = ArchiveEntry(
                    memory_id=memory.id,
                    original_memory=memory,
                    archive_date=datetime.now(),
                    archive_reason=ArchiveReason.STORAGE_LIMIT,
                    compressed_content=await self._create_compressed_summary(memory)
                )
                
                self.archive[memory.id] = archive_entry
                memory.metadata.status = MemoryStatus.ARCHIVED
                
                archived_count += 1
                
            except Exception as e:
                logger.error(f"자동 아카이브 실패 {memory.id}: {e}")
        
        logger.info(f"용량 제한으로 자동 아카이브: {archived_count}개")
        return archived_count


# 유틸리티 함수들

async def create_memory_manager(
    llm_provider: LLMProvider,
    **kwargs
) -> MemoryManager:
    """메모리 매니저 인스턴스 생성 및 초기화"""
    manager = MemoryManager(
        llm_provider=llm_provider,
        **kwargs
    )
    await manager.initialize()
    return manager


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
