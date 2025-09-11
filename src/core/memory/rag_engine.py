"""
RAG 검색 엔진 - Step 4.3

지능형 기억 검색을 위한 하이브리드 검색 시스템
의미적 유사도 + 키워드 검색 + 고급 랭킹 알고리즘
"""

import re
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
import numpy as np

# 로컬 모듈
from .vector_store import VectorStore, VectorDocument, CollectionType
from .embedding_provider import QwenEmbeddingProvider
from .enhanced_models import (
    BaseMemory, ActionMemory, ConversationMemory, PreferenceMemory,
    MemoryType, ImportanceLevel, ActionType, MetadataSchema
)


class SearchMode(Enum):
    """검색 모드"""
    SEMANTIC = "semantic"          # 의미적 유사도 검색만
    KEYWORD = "keyword"            # 키워드 기반 검색만
    HYBRID = "hybrid"              # 하이브리드 검색
    CONTEXTUAL = "contextual"      # 컨텍스트 기반 검색


class RankingStrategy(Enum):
    """랭킹 전략"""
    SIMILARITY = "similarity"      # 유사도 우선
    RECENCY = "recency"           # 최신성 우선
    IMPORTANCE = "importance"      # 중요도 우선
    BALANCED = "balanced"          # 균형잡힌 랭킹
    FREQUENCY = "frequency"        # 접근 빈도 우선


@dataclass
class SearchFilter:
    """검색 필터"""
    memory_types: Optional[List[MemoryType]] = None
    importance_levels: Optional[List[ImportanceLevel]] = None
    date_range: Optional[Tuple[datetime, datetime]] = None
    users: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    min_confidence: Optional[float] = None
    exclude_archived: bool = True
    action_types: Optional[List[ActionType]] = None


@dataclass
class SearchResult:
    """검색 결과"""
    memory: BaseMemory
    similarity_score: float        # 유사도 점수 (0.0-1.0)
    keyword_score: float          # 키워드 점수 (0.0-1.0)
    importance_score: float       # 중요도 점수 (0.0-1.0)
    recency_score: float         # 최신성 점수 (0.0-1.0)
    frequency_score: float       # 접근빈도 점수 (0.0-1.0)
    final_score: float           # 최종 랭킹 점수
    match_info: Dict[str, Any]   # 매칭 상세 정보
    
    def __post_init__(self):
        """최종 점수가 없으면 기본 계산"""
        if self.final_score == 0.0:
            self.final_score = self._calculate_default_score()
    
    def _calculate_default_score(self) -> float:
        """기본 점수 계산 (균형잡힌 방식)"""
        return (
            self.similarity_score * 0.4 +
            self.keyword_score * 0.2 +
            self.importance_score * 0.2 +
            self.recency_score * 0.1 +
            self.frequency_score * 0.1
        )


@dataclass
class SearchQuery:
    """검색 쿼리"""
    text: str
    mode: SearchMode = SearchMode.HYBRID
    ranking_strategy: RankingStrategy = RankingStrategy.BALANCED
    filters: Optional[SearchFilter] = None
    limit: int = 10
    similarity_threshold: float = 0.3
    context: Optional[Dict[str, Any]] = None


class KeywordSearchEngine:
    """키워드 기반 검색 엔진 (BM25 알고리즘)"""
    
    def __init__(self):
        self.documents: List[Dict[str, Any]] = []
        self.index: Dict[str, List[int]] = defaultdict(list)
        self.document_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.k1: float = 1.5  # BM25 파라미터
        self.b: float = 0.75  # BM25 파라미터
    
    def add_document(self, doc_id: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        """문서 추가"""
        tokens = self._tokenize(content)
        doc_length = len(tokens)
        
        doc_info = {
            'id': doc_id,
            'content': content,
            'tokens': tokens,
            'length': doc_length,
            'metadata': metadata or {}
        }
        
        doc_index = len(self.documents)
        self.documents.append(doc_info)
        self.document_lengths.append(doc_length)
        
        # 인덱스 업데이트
        for token in set(tokens):
            self.index[token].append(doc_index)
        
        # 평균 문서 길이 업데이트
        self.avg_doc_length = sum(self.document_lengths) / len(self.document_lengths)
    
    def _tokenize(self, text: str) -> List[str]:
        """텍스트 토큰화"""
        # 한글, 영문, 숫자 추출
        korean_tokens = re.findall(r'[가-힣]+', text.lower())
        english_tokens = re.findall(r'[a-zA-Z]+', text.lower())
        number_tokens = re.findall(r'\d+', text)
        
        return korean_tokens + english_tokens + number_tokens
    
    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """BM25 기반 검색"""
        query_tokens = self._tokenize(query)
        scores = defaultdict(float)
        
        for token in query_tokens:
            if token in self.index:
                df = len(self.index[token])  # 문서 빈도
                idf = math.log((len(self.documents) - df + 0.5) / (df + 0.5))
                
                for doc_index in self.index[token]:
                    doc = self.documents[doc_index]
                    tf = doc['tokens'].count(token)  # 용어 빈도
                    
                    # BM25 점수 계산
                    score = idf * (tf * (self.k1 + 1)) / (
                        tf + self.k1 * (1 - self.b + self.b * doc['length'] / self.avg_doc_length)
                    )
                    scores[doc['id']] += score
        
        # 점수 정규화 (0-1 범위)
        if scores:
            max_score = max(scores.values())
            normalized_scores = [(doc_id, score / max_score) for doc_id, score in scores.items()]
        else:
            normalized_scores = []
        
        # 점수순 정렬
        sorted_results = sorted(normalized_scores, key=lambda x: x[1], reverse=True)
        return sorted_results[:limit]
    
    def clear(self):
        """인덱스 초기화"""
        self.documents.clear()
        self.index.clear()
        self.document_lengths.clear()
        self.avg_doc_length = 0.0


class RAGSearchEngine:
    """RAG 검색 엔진 메인 클래스"""
    
    def __init__(self, vector_store: VectorStore, embedding_provider: QwenEmbeddingProvider):
        self.vector_store = vector_store
        self.embedding_provider = embedding_provider
        self.keyword_engine = KeywordSearchEngine()
        
        # 검색 통계
        self.search_stats = {
            'total_searches': 0,
            'semantic_searches': 0,
            'keyword_searches': 0,
            'hybrid_searches': 0,
            'avg_response_time': 0.0
        }
    
    async def index_memory(self, memory: BaseMemory):
        """기억을 검색 인덱스에 추가"""
        try:
            # 1. 벡터 인덱스에 추가
            collection_type = self._get_collection_type(memory.memory_type)
            
            vector_doc = VectorDocument(
                id=memory.id,
                content=memory.content,
                metadata={
                    'user_id': memory.user_id,
                    'memory_type': memory.memory_type.value,
                    'importance': memory.importance.value,
                    'created_at': memory.created_at.isoformat(),
                    'updated_at': memory.updated_at.isoformat(),
                    'tags': memory.tags,
                    'keywords': memory.keywords,
                    'is_archived': memory.is_archived,
                    **memory.metadata.to_dict()
                }
            )
            
            await self.vector_store.add_document(collection_type, vector_doc)
            
            # 2. 키워드 인덱스에 추가
            searchable_content = self._create_searchable_content(memory)
            self.keyword_engine.add_document(
                memory.id, 
                searchable_content,
                {
                    'memory_type': memory.memory_type.value,
                    'importance': memory.importance.value,
                    'tags': memory.tags,
                    'keywords': memory.keywords
                }
            )
            
        except Exception as e:
            print(f"기억 인덱싱 실패 {memory.id}: {e}")
    
    def _get_collection_type(self, memory_type: MemoryType) -> CollectionType:
        """메모리 타입을 컬렉션 타입으로 변환"""
        mapping = {
            MemoryType.ACTION: CollectionType.ACTION_MEMORY,
            MemoryType.CONVERSATION: CollectionType.CONVERSATION,
            MemoryType.PROJECT: CollectionType.PROJECT_CONTEXT,
            MemoryType.PREFERENCE: CollectionType.USER_PREFERENCE,
            MemoryType.SYSTEM: CollectionType.SYSTEM_STATE,
            MemoryType.LEARNING: CollectionType.ACTION_MEMORY,
            MemoryType.CONTEXT: CollectionType.PROJECT_CONTEXT,
            MemoryType.RELATIONSHIP: CollectionType.USER_PREFERENCE
        }
        return mapping.get(memory_type, CollectionType.ACTION_MEMORY)
    
    def _create_searchable_content(self, memory: BaseMemory) -> str:
        """검색 가능한 통합 콘텐츠 생성"""
        parts = [memory.content]
        
        # 태그와 키워드 추가
        if memory.tags:
            parts.append(" ".join(memory.tags))
        if memory.keywords:
            parts.append(" ".join(memory.keywords))
        
        # ActionMemory 특별 처리
        if isinstance(memory, ActionMemory) and memory.action_reasoning_pair:
            pair = memory.action_reasoning_pair
            parts.extend([
                pair.action,
                pair.reasoning,
                pair.context,
                pair.outcome,
                " ".join(pair.tools_used)
            ])
        
        return " ".join(parts)
    
    async def search(self, query: SearchQuery) -> List[SearchResult]:
        """통합 검색 실행"""
        import time
        start_time = time.time()
        
        try:
            if query.mode == SearchMode.SEMANTIC:
                results = await self._semantic_search(query)
            elif query.mode == SearchMode.KEYWORD:
                results = self._keyword_search(query)
            elif query.mode == SearchMode.HYBRID:
                results = await self._hybrid_search(query)
            elif query.mode == SearchMode.CONTEXTUAL:
                results = await self._contextual_search(query)
            else:
                results = await self._hybrid_search(query)  # 기본값
            
            # 필터 적용
            if query.filters:
                results = self._apply_filters(results, query.filters)
            
            # 랭킹 적용
            results = self._apply_ranking(results, query.ranking_strategy)
            
            # 임계값 적용
            results = [r for r in results if r.similarity_score >= query.similarity_threshold]
            
            # 제한 적용
            results = results[:query.limit]
            
            # 통계 업데이트
            self._update_search_stats(query.mode, time.time() - start_time)
            
            return results
            
        except Exception as e:
            print(f"검색 실행 오류: {e}")
            return []
    
    async def _semantic_search(self, query: SearchQuery) -> List[SearchResult]:
        """의미적 유사도 검색"""
        results = []
        
        # 모든 컬렉션에서 검색
        for collection_type in CollectionType:
            try:
                vector_results = await self.vector_store.search_similar(
                    collection_type, query.text, n_results=query.limit * 2
                )
                
                for result_dict in vector_results:
                    # ChromaDB 결과에서 정보 추출
                    doc_id = result_dict.get('ids', [''])[0] if result_dict.get('ids') else ''
                    documents = result_dict.get('documents', [''])
                    distances = result_dict.get('distances', [1.0])
                    metadatas = result_dict.get('metadatas', [{}])
                    
                    if doc_id and documents:
                        distance = distances[0] if distances else 1.0
                        similarity = max(0.0, 1.0 - distance)  # 거리를 유사도로 변환
                        
                        # VectorDocument 객체 생성
                        doc = VectorDocument(
                            id=doc_id,
                            content=documents[0],
                            metadata=metadatas[0] if metadatas else {}
                        )
                        
                        # 메모리 객체 복원 (실제로는 데이터베이스에서 가져와야 함)
                        memory = self._create_mock_memory(doc)
                        
                        result = SearchResult(
                            memory=memory,
                            similarity_score=similarity,
                            keyword_score=0.0,
                            importance_score=self._calculate_importance_score(memory),
                            recency_score=self._calculate_recency_score(memory),
                            frequency_score=self._calculate_frequency_score(memory),
                            final_score=0.0,  # 나중에 계산
                            match_info={'method': 'semantic', 'collection': collection_type.value}
                        )
                        results.append(result)
                    
            except Exception as e:
                print(f"의미적 검색 오류 ({collection_type.value}): {e}")
        
        return results
    
    def _keyword_search(self, query: SearchQuery) -> List[SearchResult]:
        """키워드 기반 검색"""
        results = []
        
        keyword_results = self.keyword_engine.search(query.text, query.limit * 2)
        
        for doc_id, keyword_score in keyword_results:
            # 메모리 객체 복원 (실제로는 데이터베이스에서 가져와야 함)
            memory = self._find_memory_by_id(doc_id)
            if memory:
                result = SearchResult(
                    memory=memory,
                    similarity_score=0.0,
                    keyword_score=keyword_score,
                    importance_score=self._calculate_importance_score(memory),
                    recency_score=self._calculate_recency_score(memory),
                    frequency_score=self._calculate_frequency_score(memory),
                    final_score=0.0,
                    match_info={'method': 'keyword', 'matched_terms': self._find_matched_terms(query.text, memory)}
                )
                results.append(result)
        
        return results
    
    async def _hybrid_search(self, query: SearchQuery) -> List[SearchResult]:
        """하이브리드 검색 (의미적 + 키워드)"""
        # 의미적 검색 결과
        semantic_results = await self._semantic_search(query)
        
        # 키워드 검색 결과
        keyword_results = self._keyword_search(query)
        
        # 결과 병합 (ID 기준으로 중복 제거하면서 점수 결합)
        merged_results = {}
        
        # 의미적 검색 결과 추가
        for result in semantic_results:
            merged_results[result.memory.id] = result
        
        # 키워드 검색 결과 병합
        for result in keyword_results:
            memory_id = result.memory.id
            if memory_id in merged_results:
                # 기존 결과와 키워드 점수 결합
                existing = merged_results[memory_id]
                existing.keyword_score = result.keyword_score
                existing.match_info.update(result.match_info)
            else:
                # 새로운 결과 추가
                merged_results[memory_id] = result
        
        return list(merged_results.values())
    
    async def _contextual_search(self, query: SearchQuery) -> List[SearchResult]:
        """컨텍스트 기반 검색"""
        # 기본 하이브리드 검색 수행
        results = await self._hybrid_search(query)
        
        # 컨텍스트 정보를 활용한 점수 조정
        if query.context:
            for result in results:
                context_boost = self._calculate_context_relevance(result.memory, query.context)
                result.final_score *= (1.0 + context_boost)
        
        return results
    
    def _apply_filters(self, results: List[SearchResult], filters: SearchFilter) -> List[SearchResult]:
        """검색 필터 적용"""
        filtered_results = []
        
        for result in results:
            memory = result.memory
            
            # 메모리 타입 필터
            if filters.memory_types and memory.memory_type not in filters.memory_types:
                continue
            
            # 중요도 필터
            if filters.importance_levels and memory.importance not in filters.importance_levels:
                continue
            
            # 날짜 범위 필터
            if filters.date_range:
                start_date, end_date = filters.date_range
                if not (start_date <= memory.created_at <= end_date):
                    continue
            
            # 사용자 필터
            if filters.users and memory.user_id not in filters.users:
                continue
            
            # 태그 필터
            if filters.tags and not any(tag in memory.tags for tag in filters.tags):
                continue
            
            # 신뢰도 필터
            if filters.min_confidence and memory.metadata.confidence < filters.min_confidence:
                continue
            
            # 아카이브 필터
            if filters.exclude_archived and memory.is_archived:
                continue
            
            # ActionMemory 특별 필터
            if (filters.action_types and isinstance(memory, ActionMemory) and 
                memory.action_reasoning_pair and 
                memory.action_reasoning_pair.action_type not in filters.action_types):
                continue
            
            filtered_results.append(result)
        
        return filtered_results
    
    def _apply_ranking(self, results: List[SearchResult], strategy: RankingStrategy) -> List[SearchResult]:
        """랭킹 전략 적용"""
        for result in results:
            if strategy == RankingStrategy.SIMILARITY:
                result.final_score = result.similarity_score * 0.8 + result.keyword_score * 0.2
            elif strategy == RankingStrategy.RECENCY:
                result.final_score = result.recency_score * 0.5 + result.similarity_score * 0.3 + result.keyword_score * 0.2
            elif strategy == RankingStrategy.IMPORTANCE:
                result.final_score = result.importance_score * 0.5 + result.similarity_score * 0.3 + result.keyword_score * 0.2
            elif strategy == RankingStrategy.FREQUENCY:
                result.final_score = result.frequency_score * 0.4 + result.similarity_score * 0.3 + result.keyword_score * 0.3
            elif strategy == RankingStrategy.BALANCED:
                result.final_score = result._calculate_default_score()
        
        # 점수순 정렬
        return sorted(results, key=lambda x: x.final_score, reverse=True)
    
    def _calculate_importance_score(self, memory: BaseMemory) -> float:
        """중요도 점수 계산 (0.0-1.0)"""
        importance_map = {
            ImportanceLevel.MINIMAL: 0.1,
            ImportanceLevel.LOW: 0.3,
            ImportanceLevel.MEDIUM: 0.5,
            ImportanceLevel.HIGH: 0.8,
            ImportanceLevel.CRITICAL: 1.0
        }
        return importance_map.get(memory.importance, 0.5)
    
    def _calculate_recency_score(self, memory: BaseMemory) -> float:
        """최신성 점수 계산 (0.0-1.0)"""
        now = datetime.now()
        age_days = (now - memory.created_at).days
        
        # 지수 감소 함수 (30일 반감기)
        return math.exp(-age_days / 30.0)
    
    def _calculate_frequency_score(self, memory: BaseMemory) -> float:
        """접근 빈도 점수 계산 (0.0-1.0)"""
        # 최대 접근 횟수를 100으로 가정
        max_access = 100
        return min(memory.accessed_count / max_access, 1.0)
    
    def _calculate_context_relevance(self, memory: BaseMemory, context: Dict[str, Any]) -> float:
        """컨텍스트 관련성 계산 (부스트 점수)"""
        relevance = 0.0
        
        # 시간적 컨텍스트
        if 'time_context' in context:
            time_context = context['time_context']
            memory_hour = memory.created_at.hour
            current_hour = datetime.now().hour
            
            if abs(memory_hour - current_hour) <= 2:  # 2시간 내
                relevance += 0.1
        
        # 사용자 컨텍스트
        if 'user_context' in context and context['user_context'] == memory.user_id:
            relevance += 0.2
        
        # 주제 컨텍스트
        if 'topic_context' in context:
            topic_keywords = context['topic_context']
            if any(keyword in memory.keywords for keyword in topic_keywords):
                relevance += 0.15
        
        return min(relevance, 0.5)  # 최대 50% 부스트
    
    def _find_matched_terms(self, query: str, memory: BaseMemory) -> List[str]:
        """매칭된 용어 찾기"""
        query_tokens = re.findall(r'[가-힣a-zA-Z0-9]+', query.lower())
        content_tokens = re.findall(r'[가-힣a-zA-Z0-9]+', memory.content.lower())
        
        matched = []
        for token in query_tokens:
            if token in content_tokens or token in [k.lower() for k in memory.keywords]:
                matched.append(token)
        
        return matched
    
    def _create_mock_memory(self, doc: VectorDocument) -> BaseMemory:
        """VectorDocument로부터 BaseMemory 객체 생성 (임시)"""
        # 실제로는 데이터베이스에서 완전한 객체를 가져와야 함
        metadata = doc.metadata or {}
        
        return BaseMemory(
            id=doc.id,
            user_id=metadata.get('user_id', 'unknown'),
            memory_type=MemoryType(metadata.get('memory_type', 'action')),
            content=doc.content,
            importance=ImportanceLevel(metadata.get('importance', 3)),
            tags=metadata.get('tags', []),
            keywords=metadata.get('keywords', []),
            is_archived=metadata.get('is_archived', False),
            created_at=datetime.fromisoformat(metadata.get('created_at', datetime.now().isoformat())),
            accessed_count=metadata.get('accessed_count', 0)
        )
    
    def _find_memory_by_id(self, memory_id: str) -> Optional[BaseMemory]:
        """ID로 메모리 찾기 (임시 구현)"""
        # 실제로는 데이터베이스에서 찾아야 함
        for doc_info in self.keyword_engine.documents:
            if doc_info['id'] == memory_id:
                return self._create_mock_memory_from_doc(doc_info)
        return None
    
    def _create_mock_memory_from_doc(self, doc_info: Dict[str, Any]) -> BaseMemory:
        """문서 정보로부터 BaseMemory 생성 (임시)"""
        metadata = doc_info.get('metadata', {})
        
        return BaseMemory(
            id=doc_info['id'],
            user_id='test_user',
            memory_type=MemoryType(metadata.get('memory_type', 'action')),
            content=doc_info['content'],
            importance=ImportanceLevel(metadata.get('importance', 3)),
            tags=metadata.get('tags', []),
            keywords=metadata.get('keywords', [])
        )
    
    def _update_search_stats(self, mode: SearchMode, response_time: float):
        """검색 통계 업데이트"""
        self.search_stats['total_searches'] += 1
        
        if mode == SearchMode.SEMANTIC:
            self.search_stats['semantic_searches'] += 1
        elif mode == SearchMode.KEYWORD:
            self.search_stats['keyword_searches'] += 1
        elif mode == SearchMode.HYBRID:
            self.search_stats['hybrid_searches'] += 1
        
        # 평균 응답 시간 업데이트
        total = self.search_stats['total_searches']
        current_avg = self.search_stats['avg_response_time']
        self.search_stats['avg_response_time'] = (current_avg * (total - 1) + response_time) / total
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """검색 통계 반환"""
        return self.search_stats.copy()
    
    def clear_index(self):
        """모든 인덱스 초기화"""
        self.keyword_engine.clear()
        # 벡터 스토어는 별도로 관리


# 편의 함수들
def create_search_query(text: str, 
                       mode: SearchMode = SearchMode.HYBRID,
                       memory_types: Optional[List[MemoryType]] = None,
                       limit: int = 10) -> SearchQuery:
    """검색 쿼리 생성 헬퍼 함수"""
    filters = None
    if memory_types:
        filters = SearchFilter(memory_types=memory_types)
    
    return SearchQuery(
        text=text,
        mode=mode,
        filters=filters,
        limit=limit
    )


def create_time_based_filter(days_back: int = 30) -> SearchFilter:
    """시간 기반 필터 생성"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    return SearchFilter(date_range=(start_date, end_date))


def create_importance_filter(min_level: ImportanceLevel) -> SearchFilter:
    """중요도 기반 필터 생성"""
    importance_levels = []
    for level in ImportanceLevel:
        if level.value >= min_level.value:
            importance_levels.append(level)
    
    return SearchFilter(importance_levels=importance_levels)


def merge_search_filters(*filters: SearchFilter) -> SearchFilter:
    """여러 필터를 병합"""
    merged = SearchFilter()
    
    for filter_obj in filters:
        if filter_obj.memory_types:
            if merged.memory_types:
                merged.memory_types = list(set(merged.memory_types + filter_obj.memory_types))
            else:
                merged.memory_types = filter_obj.memory_types[:]
        
        if filter_obj.importance_levels:
            if merged.importance_levels:
                merged.importance_levels = list(set(merged.importance_levels + filter_obj.importance_levels))
            else:
                merged.importance_levels = filter_obj.importance_levels[:]
        
        # 다른 필터들도 병합...
        if filter_obj.date_range:
            merged.date_range = filter_obj.date_range
        if filter_obj.min_confidence:
            merged.min_confidence = max(merged.min_confidence or 0, filter_obj.min_confidence)
        if not filter_obj.exclude_archived:
            merged.exclude_archived = False
    
    return merged
