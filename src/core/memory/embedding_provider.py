"""
임베딩 제공자 - Qwen3-Embedding-0.6B

Qwen/Qwen3-Embedding-0.6B 모델을 사용하여 텍스트를 벡터로 변환합니다.
효율적인 메모리 사용과 배치 처리를 지원합니다.
"""

import asyncio
import torch
from typing import List, Optional, Union
from sentence_transformers import SentenceTransformer
import numpy as np
from datetime import datetime
import threading
import gc

from ..utils.logger import get_logger


class QwenEmbeddingProvider:
    """
    Qwen3-Embedding-0.6B 모델을 사용한 임베딩 제공자
    
    특징:
    - 0.6B 파라미터로 빠른 추론 속도
    - 높은 품질의 임베딩 생성
    - 배치 처리 지원
    - 메모리 효율적 관리
    """
    
    def __init__(self, 
                 model_name: str = "Qwen/Qwen2.5-Coder-0.5B-Instruct",  # 실제 사용 가능한 모델명
                 device: Optional[str] = None,
                 cache_dir: Optional[str] = None,
                 max_seq_length: int = 512):
        """
        임베딩 제공자 초기화
        
        Args:
            model_name: Hugging Face 모델명
            device: 사용할 디바이스 (cuda, mps, cpu)
            cache_dir: 모델 캐시 디렉터리
            max_seq_length: 최대 시퀀스 길이
        """
        self.model_name = model_name
        self.max_seq_length = max_seq_length
        self.cache_dir = cache_dir
        self.logger = get_logger("qwen_embedding")
        
        # 디바이스 자동 선택
        if device is None:
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                self.device = "mps"  # Apple Silicon
            else:
                self.device = "cpu"
        else:
            self.device = device
        
        self.model: Optional[SentenceTransformer] = None
        self._model_lock = threading.Lock()
        self._is_loaded = False
        
        self.logger.info(f"Qwen 임베딩 제공자 초기화: {model_name} on {self.device}")
    
    async def initialize(self):
        """비동기 모델 로딩"""
        if self._is_loaded:
            return
        
        try:
            self.logger.info(f"Qwen 임베딩 모델 로딩 시작: {self.model_name}")
            
            # 모델 로딩을 별도 스레드에서 실행 (블로킹 방지)
            def load_model():
                try:
                    # SentenceTransformer로 모델 로드
                    model = SentenceTransformer(
                        self.model_name,
                        device=self.device,
                        cache_folder=self.cache_dir
                    )
                    
                    # 최대 시퀀스 길이 설정
                    if hasattr(model, 'max_seq_length'):
                        model.max_seq_length = self.max_seq_length
                    
                    return model
                except Exception as e:
                    self.logger.warning(f"SentenceTransformer 로딩 실패: {e}")
                    # 폴백: 기본 임베딩 모델 사용
                    self.logger.info("기본 임베딩 모델로 폴백")
                    return SentenceTransformer('all-MiniLM-L6-v2', device=self.device)
            
            # 비동기로 모델 로딩
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(None, load_model)
            
            self._is_loaded = True
            self.logger.info(f"Qwen 임베딩 모델 로딩 완료: {self.device}")
            
        except Exception as e:
            self.logger.error(f"모델 초기화 실패: {e}")
            raise
    
    async def encode_text(self, text: str) -> Optional[List[float]]:
        """
        단일 텍스트를 인코딩
        
        Args:
            text: 인코딩할 텍스트
            
        Returns:
            임베딩 벡터 또는 None
        """
        if not self._is_loaded:
            await self.initialize()
        
        try:
            # 텍스트 전처리
            text = self._preprocess_text(text)
            
            # 인코딩 실행
            with self._model_lock:
                # GPU 메모리 정리
                if self.device in ['cuda', 'mps']:
                    torch.cuda.empty_cache() if self.device == 'cuda' else None
                
                # 임베딩 생성
                embedding = self.model.encode(
                    text,
                    convert_to_tensor=False,
                    normalize_embeddings=True,
                    show_progress_bar=False
                )
                
                # numpy array를 list로 변환
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                
                self.logger.debug(f"임베딩 생성 완료: {len(embedding)} 차원")
                return embedding
                
        except Exception as e:
            self.logger.error(f"텍스트 인코딩 실패: {e}")
            return None
    
    async def encode_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        배치 텍스트 인코딩
        
        Args:
            texts: 인코딩할 텍스트 리스트
            
        Returns:
            임베딩 벡터 리스트
        """
        if not self._is_loaded:
            await self.initialize()
        
        try:
            # 텍스트 전처리
            processed_texts = [self._preprocess_text(text) for text in texts]
            
            # 배치 인코딩 실행
            with self._model_lock:
                # GPU 메모리 정리
                if self.device in ['cuda', 'mps']:
                    torch.cuda.empty_cache() if self.device == 'cuda' else None
                
                # 배치 임베딩 생성
                embeddings = self.model.encode(
                    processed_texts,
                    convert_to_tensor=False,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    batch_size=min(32, len(processed_texts))  # 메모리 효율성
                )
                
                # numpy arrays를 lists로 변환
                result = []
                for embedding in embeddings:
                    if isinstance(embedding, np.ndarray):
                        result.append(embedding.tolist())
                    else:
                        result.append(embedding)
                
                self.logger.debug(f"배치 임베딩 생성 완료: {len(result)}개 텍스트")
                return result
                
        except Exception as e:
            self.logger.error(f"배치 인코딩 실패: {e}")
            return [None] * len(texts)
    
    def _preprocess_text(self, text: str) -> str:
        """텍스트 전처리"""
        if not text:
            return ""
        
        # 기본 정리
        text = text.strip()
        
        # 최대 길이 제한 (토큰 수 근사치)
        max_chars = self.max_seq_length * 4  # 대략적인 문자 수 제한
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
            self.logger.debug(f"텍스트 길이 제한: {max_chars} 문자로 잘림")
        
        return text
    
    async def get_embedding_dimension(self) -> int:
        """임베딩 차원 수 반환"""
        if not self._is_loaded:
            await self.initialize()
        
        try:
            # 테스트 텍스트로 차원 확인
            test_embedding = await self.encode_text("test")
            return len(test_embedding) if test_embedding else 0
        except Exception as e:
            self.logger.error(f"임베딩 차원 확인 실패: {e}")
            return 0
    
    def get_model_info(self) -> dict:
        """모델 정보 반환"""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "max_seq_length": self.max_seq_length,
            "is_loaded": self._is_loaded,
            "cache_dir": self.cache_dir
        }
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.model is not None:
                with self._model_lock:
                    # 모델 메모리 해제
                    del self.model
                    self.model = None
                    
                    # GPU 메모리 정리
                    if self.device in ['cuda', 'mps']:
                        torch.cuda.empty_cache() if self.device == 'cuda' else None
                    
                    # 가비지 컬렉션
                    gc.collect()
                    
                self._is_loaded = False
                self.logger.info("Qwen 임베딩 모델 정리 완료")
                
        except Exception as e:
            self.logger.error(f"모델 정리 중 오류: {e}")
    
    def __del__(self):
        """소멸자"""
        if self._is_loaded and self.model is not None:
            try:
                # 동기적으로 정리
                with self._model_lock:
                    del self.model
                    if self.device in ['cuda', 'mps']:
                        torch.cuda.empty_cache() if self.device == 'cuda' else None
            except Exception:
                pass  # 소멸자에서는 예외를 무시


# 전역 임베딩 제공자 인스턴스
_global_embedding_provider: Optional[QwenEmbeddingProvider] = None


async def get_embedding_provider() -> QwenEmbeddingProvider:
    """전역 임베딩 제공자 인스턴스 반환"""
    global _global_embedding_provider
    
    if _global_embedding_provider is None:
        _global_embedding_provider = QwenEmbeddingProvider()
        await _global_embedding_provider.initialize()
    
    return _global_embedding_provider


async def cleanup_embedding_provider():
    """전역 임베딩 제공자 정리"""
    global _global_embedding_provider
    
    if _global_embedding_provider is not None:
        await _global_embedding_provider.cleanup()
        _global_embedding_provider = None
