"""
벡터 저장소 - ChromaDB 기반 구현

AI의 장기기억을 위한 벡터 데이터베이스를 관리합니다.
행동 패턴, 대화 기록, 프로젝트 기록 등을 임베딩으로 저장하고 검색합니다.
"""

import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from chromadb.api import ClientAPI

from ..utils.logger import get_logger
from ..ai_engine.llm_provider import LLMProvider
from .embedding_provider import QwenEmbeddingProvider, get_embedding_provider


class CollectionType(Enum):
    """컬렉션 타입"""
    ACTION_MEMORY = "action_memory"      # 행동 기록
    CONVERSATION = "conversation"        # 대화 기록  
    PROJECT_CONTEXT = "project_context"  # 프로젝트 맥락
    USER_PREFERENCE = "user_preference"  # 사용자 선호도
    SYSTEM_STATE = "system_state"        # 시스템 상태


@dataclass
class VectorDocument:
    """벡터 문서 데이터 구조"""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat() if self.timestamp else datetime.now().isoformat()
        }


class VectorStore:
    """
    ChromaDB 기반 벡터 저장소
    
    AI의 장기기억을 위한 벡터 데이터베이스를 관리합니다.
    Google Gemini 임베딩을 사용하여 텍스트를 벡터로 변환하고 저장합니다.
    """
    
    def __init__(self, 
                 data_path: str = "data/memory",
                 llm_provider: Optional[LLMProvider] = None,
                 embedding_provider: Optional[QwenEmbeddingProvider] = None):
        """
        벡터 저장소 초기화
        
        Args:
            data_path: 데이터 저장 경로
            llm_provider: LLM 제공자 (사용 안함)
            embedding_provider: 임베딩 제공자 (Qwen3)
        """
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.logger = get_logger("vector_store")
        
        # ChromaDB 클라이언트 초기화
        self.client: Optional[ClientAPI] = None
        self.collections: Dict[str, Any] = {}
        
        self.logger.info("벡터 저장소 초기화 시작")
    
    async def initialize(self):
        """비동기 초기화"""
        try:
            # ChromaDB 클라이언트 생성
            self.client = chromadb.PersistentClient(
                path=str(self.data_path / "chroma_db"),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # 임베딩 제공자 초기화
            if self.embedding_provider is None:
                self.embedding_provider = await get_embedding_provider()
            
            # 기본 컬렉션들 생성
            await self._create_default_collections()
            
            self.logger.info("벡터 저장소 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"벡터 저장소 초기화 실패: {e}")
            raise
    
    async def _create_default_collections(self):
        """기본 컬렉션들을 생성합니다"""
        for collection_type in CollectionType:
            await self._get_or_create_collection(collection_type)
    
    async def _get_or_create_collection(self, collection_type: CollectionType):
        """컬렉션을 가져오거나 생성합니다"""
        try:
            collection_name = collection_type.value
            
            # 기존 컬렉션 확인
            try:
                collection = self.client.get_collection(collection_name)
                self.logger.debug(f"기존 컬렉션 사용: {collection_name}")
            except Exception:
                # 새 컬렉션 생성
                # 임베딩 함수는 기본값 사용 (나중에 Google Gemini로 대체)
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={"type": collection_type.value}
                )
                self.logger.info(f"새 컬렉션 생성: {collection_name}")
            
            self.collections[collection_type.value] = collection
            return collection
            
        except Exception as e:
            self.logger.error(f"컬렉션 생성 실패 ({collection_type.value}): {e}")
            raise
    
    async def add_document(self, 
                          collection_type: CollectionType,
                          document: VectorDocument) -> bool:
        """
        문서를 컬렉션에 추가합니다
        
        Args:
            collection_type: 컬렉션 타입
            document: 추가할 문서
            
        Returns:
            성공 여부
        """
        try:
            collection = self.collections.get(collection_type.value)
            if not collection:
                collection = await self._get_or_create_collection(collection_type)
            
            # 임베딩 생성
            if document.embedding is None:
                document.embedding = await self._generate_embedding(document.content)
            
            # 메타데이터 준비
            metadata = document.metadata.copy()
            metadata.update({
                "timestamp": document.timestamp.isoformat() if document.timestamp else datetime.now().isoformat(),
                "content_length": len(document.content)
            })
            
            # 문서 추가
            collection.add(
                ids=[document.id],
                documents=[document.content],
                embeddings=[document.embedding] if document.embedding else None,
                metadatas=[metadata]
            )
            
            self.logger.debug(f"문서 추가 완료: {document.id} in {collection_type.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"문서 추가 실패: {e}")
            return False
    
    async def search_similar(self,
                           collection_type: CollectionType,
                           query: str,
                           n_results: int = 5,
                           where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        유사한 문서를 검색합니다
        
        Args:
            collection_type: 검색할 컬렉션 타입
            query: 검색 쿼리
            n_results: 반환할 결과 수
            where: 필터 조건
            
        Returns:
            검색 결과 리스트
        """
        try:
            collection = self.collections.get(collection_type.value)
            if not collection:
                self.logger.warning(f"컬렉션이 존재하지 않음: {collection_type.value}")
                return []
            
            # 쿼리 임베딩 생성
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                # 임베딩 실패시 텍스트 검색으로 폴백
                return await self._text_search(collection, query, n_results, where)
            
            # 벡터 검색 수행
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            # 결과 정리
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    search_results.append({
                        "id": doc_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1 - results["distances"][0][i]  # 거리를 유사도로 변환
                    })
            
            self.logger.debug(f"검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            self.logger.error(f"검색 실패: {e}")
            return []
    
    async def _text_search(self, collection, query: str, n_results: int, where: Optional[Dict]) -> List[Dict]:
        """텍스트 기반 폴백 검색"""
        try:
            # ChromaDB의 기본 검색 기능 사용
            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )
            
            search_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    search_results.append({
                        "id": doc_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1 - results["distances"][0][i]
                    })
            
            return search_results
            
        except Exception as e:
            self.logger.error(f"텍스트 검색 실패: {e}")
            return []
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        텍스트의 임베딩을 생성합니다 (Qwen3 사용)
        
        Args:
            text: 임베딩할 텍스트
            
        Returns:
            임베딩 벡터 또는 None
        """
        try:
            if self.embedding_provider:
                # Qwen3 임베딩 생성
                embedding = await self.embedding_provider.encode_text(text)
                if embedding:
                    self.logger.debug(f"Qwen3 임베딩 생성 성공: {len(embedding)} 차원")
                    return embedding
            
            self.logger.warning("임베딩 제공자가 없거나 실패, None 반환")
            return None
            
        except Exception as e:
            self.logger.error(f"임베딩 생성 실패: {e}")
            return None
    
    async def get_document(self, collection_type: CollectionType, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 문서를 가져옵니다
        
        Args:
            collection_type: 컬렉션 타입
            doc_id: 문서 ID
            
        Returns:
            문서 데이터 또는 None
        """
        try:
            collection = self.collections.get(collection_type.value)
            if not collection:
                return None
            
            results = collection.get(
                ids=[doc_id],
                include=["documents", "metadatas"]
            )
            
            if results["ids"] and results["ids"][0]:
                return {
                    "id": results["ids"][0],
                    "content": results["documents"][0],
                    "metadata": results["metadatas"][0]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"문서 조회 실패: {e}")
            return None
    
    async def delete_document(self, collection_type: CollectionType, doc_id: str) -> bool:
        """
        문서를 삭제합니다
        
        Args:
            collection_type: 컬렉션 타입
            doc_id: 삭제할 문서 ID
            
        Returns:
            성공 여부
        """
        try:
            collection = self.collections.get(collection_type.value)
            if not collection:
                return False
            
            collection.delete(ids=[doc_id])
            self.logger.debug(f"문서 삭제 완료: {doc_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"문서 삭제 실패: {e}")
            return False
    
    async def get_collection_stats(self, collection_type: CollectionType) -> Dict[str, Any]:
        """
        컬렉션 통계를 가져옵니다
        
        Args:
            collection_type: 컬렉션 타입
            
        Returns:
            통계 정보
        """
        try:
            collection = self.collections.get(collection_type.value)
            if not collection:
                return {"count": 0, "error": "Collection not found"}
            
            count = collection.count()
            
            return {
                "collection_name": collection_type.value,
                "document_count": count,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"통계 조회 실패: {e}")
            return {"count": 0, "error": str(e)}
    
    async def reset_collection(self, collection_type: CollectionType) -> bool:
        """
        컬렉션을 초기화합니다 (모든 문서 삭제)
        
        Args:
            collection_type: 초기화할 컬렉션 타입
            
        Returns:
            성공 여부
        """
        try:
            collection_name = collection_type.value
            
            # 기존 컬렉션 삭제
            try:
                self.client.delete_collection(collection_name)
            except Exception:
                pass  # 컬렉션이 없어도 무시
            
            # 새 컬렉션 생성
            await self._get_or_create_collection(collection_type)
            
            self.logger.info(f"컬렉션 초기화 완료: {collection_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"컬렉션 초기화 실패: {e}")
            return False
    
    def close(self):
        """연결을 종료합니다"""
        try:
            if self.client:
                # ChromaDB는 자동으로 연결이 정리됨
                self.collections.clear()
                self.logger.info("벡터 저장소 연결 종료")
        except Exception as e:
            self.logger.error(f"연결 종료 중 오류: {e}")


# 유틸리티 함수들
def create_action_memory_id(user_id: str, timestamp: datetime) -> str:
    """행동 기록 ID 생성"""
    return f"action_{user_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}"


def create_conversation_id(user_id: str, session_id: str) -> str:
    """대화 기록 ID 생성"""
    return f"conv_{user_id}_{session_id}"


def create_document_from_action(user_id: str,
                               action: str,
                               reasoning: str,
                               result: str,
                               metadata: Optional[Dict[str, Any]] = None) -> VectorDocument:
    """행동 기록으로부터 벡터 문서 생성"""
    timestamp = datetime.now()
    doc_id = create_action_memory_id(user_id, timestamp)
    
    content = f"행동: {action}\n이유: {reasoning}\n결과: {result}"
    
    doc_metadata = {
        "user_id": user_id,
        "action": action,
        "reasoning": reasoning,
        "result": result,
        "type": "action_memory"
    }
    
    if metadata:
        doc_metadata.update(metadata)
    
    return VectorDocument(
        id=doc_id,
        content=content,
        metadata=doc_metadata,
        timestamp=timestamp
    )
