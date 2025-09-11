"""
장기기억 시스템 모듈

AI가 과거 행동 패턴을 학습하고 기억하는 RAG 기반 시스템을 제공합니다.

새로운 모듈 구조:
- models/: 메모리 데이터 모델들 (BaseMemory, ActionMemory, ConversationMemory 등)
- engines/: 검색 및 임베딩 엔진들 (RAGSearchEngine, QwenEmbeddingProvider)
- managers/: 메모리 생명주기 관리자들 (MemoryManager)
- vector_store.py: ChromaDB 기반 벡터 데이터베이스
"""

# Core components
from .vector_store import VectorStore, VectorDocument, CollectionType

# Memory models (새로운 enhanced 모델들)
from .models import (
    BaseMemory, MetadataSchema, MemoryType, ImportanceLevel, MemoryStatus, ActionType,
    ActionMemory, ConversationMemory, PreferenceMemory, ActionReasoningPair,
    ImportanceCalculator, create_action_memory, create_conversation_memory, create_preference_memory
)

# Engines
from .engines import (
    SearchMode, RankingStrategy, SearchFilter, SearchResult, SearchQuery,
    KeywordSearchEngine, RAGSearchEngine, QwenEmbeddingProvider
)

# Managers  
from .managers import MemoryManager

__all__ = [
    # Core
    "VectorStore", "VectorDocument", "CollectionType",
    
    # Models
    "BaseMemory", "MetadataSchema", "MemoryType", "ImportanceLevel", "MemoryStatus", "ActionType",
    "ActionMemory", "ConversationMemory", "PreferenceMemory", "ActionReasoningPair",
    "ImportanceCalculator", "create_action_memory", "create_conversation_memory", "create_preference_memory",
    
    # Engines
    "SearchMode", "RankingStrategy", "SearchFilter", "SearchResult", "SearchQuery", 
    "KeywordSearchEngine", "RAGSearchEngine", "QwenEmbeddingProvider",
    
    # Managers
    "MemoryManager"
]

__version__ = "2.0.0"
