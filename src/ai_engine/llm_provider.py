"""LLM Provider 추상화 모듈

Google Gemini 2.5 Pro API 래퍼 및 통합 인터페이스 제공
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

import google.generativeai as genai
from loguru import logger

from ..config import Settings


class ModelType(Enum):
    """지원하는 AI 모델 타입"""
    GEMINI_15_PRO = "gemini-1.5-pro"
    GEMINI_15_FLASH = "gemini-1.5-flash"
    GEMINI_25_PRO = "gemini-2.5-pro"
    GEMINI_2_FLASH_EXP = "gemini-2.0-flash-exp"


@dataclass
class ChatMessage:
    """채팅 메시지 데이터 클래스"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """LLM 응답 데이터 클래스"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """LLM 프로바이더 추상 기본 클래스"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.model_name: str = ""
        
    @abstractmethod
    async def initialize(self) -> bool:
        """프로바이더 초기화"""
        pass
        
    @abstractmethod
    async def generate_response(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """응답 생성"""
        pass
        
    @abstractmethod
    async def generate_stream(
        self,
        messages: List[ChatMessage], 
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """스트리밍 응답 생성"""
        pass
        
    @abstractmethod
    def is_available(self) -> bool:
        """프로바이더 사용 가능 여부"""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini 2.5 Pro Provider"""
    
    def __init__(self, config: Settings, model_type: Optional[ModelType] = None):
        super().__init__(config)
        
        # 환경변수에서 모델명 가져오기, 없으면 기본값 사용
        if model_type is None:
            model_name = config.ai_model
            # 문자열 모델명을 ModelType으로 변환
            for mt in ModelType:
                if mt.value == model_name:
                    model_type = mt
                    break
            else:
                # 일치하는 모델이 없으면 기본값 사용
                model_type = ModelType.GEMINI_25_PRO
                
        self.model_type = model_type
        self.model_name = model_type.value
        self.client = None
        self.model = None
        
    async def initialize(self) -> bool:
        """Gemini API 초기화"""
        try:
            # API 키 설정
            api_key = self.config.google_ai_api_key
            if not api_key:
                logger.error("Google AI API 키가 설정되지 않았습니다")
                return False
                
            genai.configure(api_key=api_key)
            
            # 모델 초기화
            self.model = genai.GenerativeModel(self.model_name)
            
            # 연결 테스트
            test_response = await self._test_connection()
            if test_response:
                logger.info(f"Gemini {self.model_name} 초기화 완료")
                return True
            else:
                logger.error("Gemini API 연결 테스트 실패")
                return False
                
        except Exception as e:
            logger.error(f"Gemini 초기화 중 오류: {e}")
            return False
            
    async def _test_connection(self) -> bool:
        """연결 테스트"""
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                "테스트 메시지입니다. '연결 성공'이라고 답해주세요."
            )
            
            if response and response.text:
                logger.debug(f"연결 테스트 응답: {response.text[:50]}...")
                return True
            return False
            
        except Exception as e:
            logger.error(f"연결 테스트 중 오류: {e}")
            return False
            
    async def generate_response(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """응답 생성"""
        try:
            # 메시지 변환
            prompt = self._convert_messages_to_prompt(messages)
            
            # 생성 설정
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens or 8192,
                **kwargs
            )
            
            # 응답 생성
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=generation_config
            )
            
            # 응답 처리
            if response and response.text:
                return LLMResponse(
                    content=response.text,
                    model=self.model_name,
                    usage=self._extract_usage(response),
                    finish_reason=getattr(response, 'finish_reason', None),
                    metadata={"prompt_tokens": len(prompt.split())}
                )
            else:
                raise Exception("빈 응답 받음")
                
        except Exception as e:
            logger.error(f"응답 생성 중 오류: {e}")
            raise
            
    async def generate_stream(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """스트리밍 응답 생성"""
        try:
            # 메시지 변환
            prompt = self._convert_messages_to_prompt(messages)
            
            # 생성 설정
            generation_config = genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens or 8192,
                **kwargs
            )
            
            # 스트리밍 응답 생성
            response_stream = await asyncio.to_thread(
                self.model.generate_content,
                prompt,
                generation_config=generation_config,
                stream=True
            )
            
            for chunk in response_stream:
                if chunk.text:
                    yield LLMResponse(
                        content=chunk.text,
                        model=self.model_name,
                        metadata={"is_streaming": True}
                    )
                    
        except Exception as e:
            logger.error(f"스트리밍 응답 생성 중 오류: {e}")
            raise
            
    def _convert_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """메시지 리스트를 Gemini 프롬프트로 변환"""
        prompt_parts = []
        
        for message in messages:
            if message.role == "system":
                prompt_parts.append(f"[시스템 지시사항]\n{message.content}\n")
            elif message.role == "user":
                prompt_parts.append(f"[사용자]\n{message.content}\n")
            elif message.role == "assistant":
                prompt_parts.append(f"[어시스턴트]\n{message.content}\n")
                
        return "\n".join(prompt_parts)
        
    def _extract_usage(self, response) -> Optional[Dict[str, int]]:
        """사용량 정보 추출"""
        try:
            if hasattr(response, 'usage_metadata'):
                usage = response.usage_metadata
                return {
                    "prompt_tokens": getattr(usage, 'prompt_token_count', 0),
                    "completion_tokens": getattr(usage, 'candidates_token_count', 0),
                    "total_tokens": getattr(usage, 'total_token_count', 0)
                }
        except:
            pass
        return None
        
    def is_available(self) -> bool:
        """프로바이더 사용 가능 여부"""
        return self.model is not None and self.config.google_ai_api_key is not None


class LLMProviderManager:
    """LLM 프로바이더 관리자"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.providers: Dict[str, LLMProvider] = {}
        self.default_provider: Optional[str] = None
        
    async def initialize_providers(self) -> bool:
        """모든 프로바이더 초기화"""
        success_count = 0
        
        # Gemini 프로바이더 초기화
        gemini_provider = GeminiProvider(self.config)
        if await gemini_provider.initialize():
            self.providers["gemini"] = gemini_provider
            if not self.default_provider:
                self.default_provider = "gemini"
            success_count += 1
            logger.info("Gemini 프로바이더 초기화 성공")
        else:
            logger.warning("Gemini 프로바이더 초기화 실패")
            
        logger.info(f"프로바이더 초기화 완료: {success_count}개 성공")
        return success_count > 0
        
    def get_provider(self, provider_name: Optional[str] = None) -> Optional[LLMProvider]:
        """프로바이더 가져오기"""
        if not provider_name:
            provider_name = self.default_provider
            
        return self.providers.get(provider_name)
        
    def list_available_providers(self) -> List[str]:
        """사용 가능한 프로바이더 목록"""
        return [name for name, provider in self.providers.items() if provider.is_available()]
        
    async def generate_response(
        self,
        messages: List[ChatMessage],
        provider_name: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """응답 생성 (자동 프로바이더 선택)"""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"사용 가능한 프로바이더가 없습니다: {provider_name}")
            
        return await provider.generate_response(messages, **kwargs)
        
    async def generate_stream(
        self,
        messages: List[ChatMessage],
        provider_name: Optional[str] = None,
        **kwargs
    ):
        """스트리밍 응답 생성 (자동 프로바이더 선택)"""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"사용 가능한 프로바이더가 없습니다: {provider_name}")
            
        async for chunk in provider.generate_stream(messages, **kwargs):
            yield chunk
