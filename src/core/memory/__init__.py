"""
장기기억 시스템 모듈

AI가 과거 행동 패턴을 학습하고 기억하는 RAG 기반 시스템을 제공합니다.

주요 컴포넌트:
- VectorStore: ChromaDB 기반 벡터 데이터베이스
- MemoryManager: 기억 생명주기 관리
- RAGEngine: 검색 증강 생성 엔진
- MemoryModels: 기억 데이터 구조 정의
"""

from .vector_store import VectorStore, VectorDocument, CollectionType
from .models import (
    Memory, MemoryType, ImportanceLevel,
    ActionMemory, ConversationMemory, ProjectMemory, UserPreferenceMemory
)
from .embedding_provider import QwenEmbeddingProvider, get_embedding_provider

__all__ = [
    "VectorStore", "VectorDocument", "CollectionType",
    "Memory", "MemoryType", "ImportanceLevel", 
    "ActionMemory", "ConversationMemory", "ProjectMemory", "UserPreferenceMemory",
    "QwenEmbeddingProvider", "get_embedding_provider"
]

__version__ = "1.0.0"
