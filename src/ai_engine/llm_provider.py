"""LLM Provider 추상화 모듈 (수정됨)

Google Gemini 2.5 Pro API 래퍼 및 통합 인터페이스 제공
호환성 문제 해결 및 안전한 fallback 구현
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

# Google Generative AI 안전한 import
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
    print("Google Generative AI 패키지 로드 성공")
except ImportError as e:
    print(f"Google Generative AI 패키지 import 실패 (Mock 모드로 동작): {e}")
    GENAI_AVAILABLE = False
    genai = None

from loguru import logger

try:
    from ..config import Settings  # type: ignore
except ImportError:
    # 테스트 환경을 위한 fallback
    class Settings:
        def __init__(self):
            self.gemini_api_key = "test_key"


class LLMProviderError(Exception):
    """LLM 제공자 관련 오류"""
    pass


class ModelType(Enum):
    """지원하는 AI 모델 타입"""
    GEMINI_15_PRO = "gemini-1.5-pro"
    GEMINI_15_FLASH = "gemini-1.5-flash"
    MOCK = "mock"


@dataclass
class ChatMessage:
    """채팅 메시지 클래스"""
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResponse:
    """LLM 응답 클래스"""
    content: str
    model: str
    usage: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """LLM 프로바이더 추상 기본 클래스"""
    
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
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
    def is_available(self) -> bool:
        """프로바이더 사용 가능 여부"""
        pass


class GeminiProvider(LLMProvider):
    """Google Gemini API 프로바이더 (호환성 개선)"""
    
    def __init__(self, config: Optional[Settings] = None):
        super().__init__(config)
        self.model_name = "gemini-1.5-pro"
        self.model = None
        
    async def initialize(self) -> bool:
        """Gemini API 초기화"""
        try:
            if not GENAI_AVAILABLE:
                logger.error("Google Generative AI 패키지가 설치되지 않았습니다.")
                return False
                
            # API 키 확인
            api_key = getattr(self.config, 'google_ai_api_key', None)
            if not api_key:
                logger.error("Google AI API 키가 설정되지 않았습니다. config에서 google_ai_api_key를 확인해주세요.")
                return False
            
            # API 설정
            try:
                if hasattr(genai, 'configure'):
                    genai.configure(api_key=api_key)  # type: ignore
                    logger.info("Gemini API 설정 완료")
                else:
                    logger.error("genai.configure 메서드를 찾을 수 없습니다.")
                    return False
                
                # 모델 생성
                if hasattr(genai, 'GenerativeModel'):
                    self.model = genai.GenerativeModel(self.model_name)  # type: ignore
                    logger.info(f"Gemini 모델 '{self.model_name}' 생성 완료")
                else:
                    logger.error("genai.GenerativeModel 클래스를 찾을 수 없습니다.")
                    return False
                    
            except Exception as api_error:
                logger.error(f"Gemini API 설정 실패: {api_error}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Gemini 초기화 실패: {e}")
            return False
    
    def is_available(self) -> bool:
        """프로바이더 사용 가능 여부"""
        return GENAI_AVAILABLE and self.model is not None
    
    async def generate_response(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """응답 생성"""
        try:
            if not self.model:
                raise LLMProviderError("Gemini 모델이 초기화되지 않았습니다.")
                
            # 메시지 변환
            prompt = self._convert_messages_to_prompt(messages)
            
            # 생성 설정
            config_dict = {
                'temperature': temperature,
                **kwargs
            }
            
            if max_tokens:
                config_dict['max_output_tokens'] = max_tokens
            
            # 응답 생성
            if hasattr(self.model, 'generate_content'):
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=config_dict  # type: ignore
                )
                
                content = ""
                if hasattr(response, 'text'):
                    content = response.text
                else:
                    content = str(response)
                
                return LLMResponse(
                    content=content,
                    model=self.model_name,
                    usage={
                        "input_tokens": len(prompt.split()),
                        "output_tokens": len(content.split())
                    }
                )
            else:
                raise LLMProviderError("모델의 generate_content 메서드를 찾을 수 없습니다.")
                
        except Exception as e:
            logger.error(f"Gemini 응답 생성 중 오류: {e}")
            raise LLMProviderError(f"응답 생성 실패: {e}")
    
    async def stream_generate(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """스트림 형태로 응답 생성"""
        try:
            if not self.model:
                raise LLMProviderError("Gemini 모델이 초기화되지 않았습니다.")
                
            # 메시지를 ChatMessage로 변환
            chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]
            prompt = self._convert_messages_to_prompt(chat_messages)
            
            # 생성 설정
            config_dict = kwargs
            
            if hasattr(self.model, 'generate_content'):
                response = await asyncio.to_thread(
                    self.model.generate_content,
                    prompt,
                    generation_config=config_dict,  # type: ignore
                    stream=True
                )
                
                if hasattr(response, '__iter__'):
                    for chunk in response:
                        if hasattr(chunk, 'text') and chunk.text:
                            yield chunk.text
                elif hasattr(response, 'text'):
                    yield response.text
                else:
                    yield str(response)
            else:
                raise LLMProviderError("모델의 generate_content 메서드를 찾을 수 없습니다.")
                    
        except Exception as e:
            logger.error(f"Gemini 스트림 생성 중 오류: {e}")
            raise LLMProviderError(f"스트림 생성 실패: {e}")
    
    def _convert_messages_to_prompt(self, messages: List[ChatMessage]) -> str:
        """메시지들을 Gemini 프롬프트로 변환"""
        prompt_parts = []
        
        for msg in messages:
            role = msg.role.lower()
            content = msg.content
            
            if role == "system":
                prompt_parts.append(f"시스템: {content}")
            elif role == "user":
                prompt_parts.append(f"사용자: {content}")
            elif role == "assistant":
                prompt_parts.append(f"어시스턴트: {content}")
            else:
                prompt_parts.append(f"{role}: {content}")
        
        return "\n\n".join(prompt_parts)


class MockLLMProvider(LLMProvider):
    """테스트용 Mock LLM Provider"""
    
    def __init__(self, config: Optional[Settings] = None):
        super().__init__(config)
        self.model_name = "mock-llm"
    
    async def initialize(self) -> bool:
        """Mock 초기화 - 항상 성공"""
        return True
    
    def is_available(self) -> bool:
        """항상 사용 가능"""
        return True
    
    async def generate_response(
        self,
        messages: List[ChatMessage],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs
    ) -> LLMResponse:
        """Mock 응답 생성"""
        await asyncio.sleep(0.1)  # 실제 API 호출 시뮬레이션
        
        # 간단한 요약 응답 생성
        if messages:
            last_message = messages[-1]
            content = f"Mock AI 응답: '{last_message.content}'에 대한 테스트 응답입니다."
        else:
            content = "Mock AI 응답: 테스트용 기본 응답입니다."
        
        return LLMResponse(
            content=content,
            model=self.model_name,
            usage={"input_tokens": 10, "output_tokens": len(content.split())}
        )


class LLMManager:
    """LLM Provider 통합 관리자"""
    
    def __init__(self, config: Optional[Settings] = None):
        self.config = config or Settings()
        self.providers: Dict[str, LLMProvider] = {}
        self.default_provider = "gemini"
        
    async def initialize(self) -> bool:
        """모든 프로바이더 초기화"""
        try:
            # Gemini Provider 등록
            gemini_provider = GeminiProvider(self.config)
            await gemini_provider.initialize()
            self.providers["gemini"] = gemini_provider
            
            # Mock Provider 등록
            mock_provider = MockLLMProvider(self.config)
            await mock_provider.initialize()
            self.providers["mock"] = mock_provider
            
            logger.info(f"LLM Manager 초기화 완료. 사용 가능한 프로바이더: {list(self.providers.keys())}")
            return True
            
        except Exception as e:
            logger.error(f"LLM Manager 초기화 실패: {e}")
            return False
    
    def get_provider(self, provider_name: Optional[str] = None) -> Optional[LLMProvider]:
        """특정 제공자 반환"""
        if not provider_name:
            provider_name = self.default_provider
        return self.providers.get(provider_name)
    
    def list_available_providers(self) -> List[str]:
        """사용 가능한 프로바이더 목록"""
        return list(self.providers.keys())
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        provider_name: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """통합 응답 생성"""
        provider = self.get_provider(provider_name)
        if not provider:
            raise LLMProviderError(f"Provider {provider_name} not found")
        
        # Dict를 ChatMessage로 변환
        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]
        
        return await provider.generate_response(chat_messages, **kwargs)
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        provider_name: Optional[str] = None,
        **kwargs
    ):
        """스트리밍 응답 생성"""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"사용 가능한 프로바이더가 없습니다: {provider_name}")
            
        # GeminiProvider인 경우에만 스트림 지원
        if isinstance(provider, GeminiProvider):
            async for chunk in provider.stream_generate(messages, **kwargs):
                yield chunk
        else:
            # 다른 프로바이더는 일반 응답을 한 번에 반환
            chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]
            response = await provider.generate_response(chat_messages, **kwargs)
            yield response.content


# 하위 호환성을 위한 기본 인스턴스
llm_manager = None


async def get_llm_manager(config: Optional[Settings] = None) -> LLMManager:
    """LLM Manager 싱글톤 인스턴스 반환"""
    global llm_manager
    if llm_manager is None:
        llm_manager = LLMManager(config)
        await llm_manager.initialize()
    return llm_manager
