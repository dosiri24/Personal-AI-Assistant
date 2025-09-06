"""Discord Bot AI 메시지 핸들러 (에이전틱 AI 엔진 통합)

Discord Bot과 에이전틱 AI 엔진 간의 메시지 처리를 담당하는 모듈
개발 계획서 Phase 3.3: 진정한 AI 에이전트 구현
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from loguru import logger

# AI 엔진 관련 import
from ..ai_engine.llm_provider import GeminiProvider, ChatMessage
from ..ai_engine.decision_engine import AgenticDecisionEngine, ActionType, DecisionResult
from ..mcp.registry import ToolRegistry  
from ..config import Settings


@dataclass
class AIResponse:
    """AI 응답 데이터 클래스"""
    content: str
    confidence: float = 1.0
    reasoning: str = "AI processing"
    needs_followup: bool = False
    tool_calls_made: List[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tool_calls_made is None:
            self.tool_calls_made = []

import asyncio
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from src.utils.logger import get_logger
from src.ai_engine.llm_provider import GeminiProvider
from src.config import Settings

logger = get_logger(__name__)

@dataclass
class AIResponse:
    """AI 응답 데이터 클래스"""
    content: str
    confidence: float
    reasoning: Optional[str] = None
    suggested_actions: Optional[list] = None
    needs_followup: bool = False
    metadata: Optional[Dict[str, Any]] = None

class AIMessageHandler:
    """AI 메시지 처리기"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_provider = None
        self._initialize_ai_engine()
        
    def _initialize_ai_engine(self):
        """AI 엔진 초기화"""
        try:
            if self.settings.has_valid_ai_api_key():
                self.llm_provider = GeminiProvider(self.settings)
                # GeminiProvider 초기화 호출
                asyncio.create_task(self._async_initialize_gemini())
                logger.info("AI 엔진 초기화 완료")
            else:
                logger.warning("AI API 키가 설정되지 않음. Mock 모드로 동작")
                self.llm_provider = None
        except Exception as e:
            logger.error(f"AI 엔진 초기화 실패: {e}")
            self.llm_provider = None
    
    async def _async_initialize_gemini(self):
        """비동기 Gemini 초기화"""
        try:
            if self.llm_provider:
                success = await self.llm_provider.initialize()
                if success:
                    logger.info("Gemini Provider 비동기 초기화 성공")
                else:
                    logger.error("Gemini Provider 비동기 초기화 실패")
        except Exception as e:
            logger.error(f"Gemini Provider 비동기 초기화 중 오류: {e}")
    
    async def process_message(self, user_message: str, user_id: str, channel_id: str) -> AIResponse:
        """사용자 메시지를 AI 엔진으로 처리"""
        if not self.llm_provider:
            return AIResponse(
                content="AI 엔진이 초기화되지 않았습니다. 관리자에게 문의하세요.",
                confidence=0.0,
                metadata={"error": "AI 엔진 미초기화"}
            )
        
        # Gemini가 초기화되지 않았다면 다시 시도
        if not self.llm_provider.is_available():
            logger.info("Gemini Provider 재초기화 시도")
            try:
                success = await self.llm_provider.initialize()
                if not success:
                    logger.error("Gemini Provider 재초기화 실패")
                    return AIResponse(
                        content="AI 서비스 초기화에 실패했습니다. 잠시 후 다시 시도해주세요.",
                        confidence=0.0,
                        metadata={"error": "Gemini 초기화 실패"}
                    )
            except Exception as e:
                logger.error(f"Gemini Provider 재초기화 중 오류: {e}")
                return AIResponse(
                    content="AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
                    confidence=0.0,
                    metadata={"error": str(e)}
                )
        
        try:
            # 프롬프트 생성
            messages = self._build_prompt(user_message, user_id)
            
            # AI 응답 생성
            response = await self.llm_provider.generate_response(messages)
            
            # 응답 파싱
            ai_response = self._parse_ai_response(response.content, user_message)
            
            logger.info(f"AI 메시지 처리 완료: {user_id} -> {ai_response.content[:50]}...")
            return ai_response
            
        except Exception as e:
            logger.error(f"AI 메시지 처리 실패: {e}")
            return AIResponse(
                content="죄송합니다. 메시지 처리 중 오류가 발생했습니다.",
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def _build_prompt(
        self, 
        user_message: str, 
        user_id: str
    ) -> List[ChatMessage]:
        """AI 프롬프트 구성"""
        
        system_prompt = """당신은 개인 AI 비서입니다. 사용자의 요청을 친근하고 도움이 되도록 응답해주세요.

응답 지침:
1. 친근하고 도움이 되는 톤으로 응답
2. 명확하고 실용적인 정보 제공
3. 필요시 추가 질문이나 확인 요청
4. 할 수 없는 일은 솔직하게 설명
5. 한국어로 답변해주세요"""

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message)
        ]
        
        return messages
        
        return base_prompt
    
    def _parse_ai_response(self, ai_response: str, original_message: str) -> AIResponse:
        """AI 응답 파싱"""
        try:
            # 기본 응답 구성
            response = AIResponse(
                content=ai_response.strip(),
                confidence=0.9,  # 기본 신뢰도
                reasoning="AI 자연어 처리",
                metadata={
                    "original_message": original_message,
                    "processed_at": datetime.now().isoformat(),
                    "model": "gemini-2.5-pro"
                }
            )
            
            # 응답 길이에 따른 신뢰도 조정
            if len(ai_response.strip()) < 10:
                response.confidence = 0.6
            elif len(ai_response.strip()) > 1000:
                response.confidence = 0.95
            
            # 특정 패턴에 따른 후속 질문 필요성 판단
            followup_keywords = ["더 알려주세요", "구체적으로", "자세히", "추가로", "?"]
            if any(keyword in ai_response for keyword in followup_keywords):
                response.needs_followup = True
            
            return response
            
        except Exception as e:
            logger.error(f"AI 응답 파싱 오류: {e}")
            return AIResponse(
                content=ai_response.strip(),
                confidence=0.5,
                reasoning="파싱 오류",
                metadata={"error": str(e)}
            )
    
    async def _mock_ai_response(self, user_message: str, user_name: str) -> AIResponse:
        """Mock AI 응답 (API 키가 없을 때)"""
        
        # 간단한 패턴 매칭 응답
        message_lower = user_message.lower()
        
        if any(greeting in message_lower for greeting in ["안녕", "hello", "hi", "헬로"]):
            content = f"안녕하세요, {user_name}님! 👋 무엇을 도와드릴까요?"
        elif any(keyword in message_lower for keyword in ["날씨", "weather"]):
            content = "죄송합니다. 현재 날씨 정보를 가져올 수 없습니다. API 키 설정이 필요합니다."
        elif any(keyword in message_lower for keyword in ["도움", "help", "헬프"]):
            content = """🤖 AI 비서가 도와드릴 수 있는 일들:

• 일반적인 질문 답변
• 일정 관리 (Notion 연동 시)
• 간단한 계산 및 정보 검색
• Apple 앱 연동 (설정 시)

더 자세한 기능을 위해서는 AI API 키 설정이 필요합니다."""
        elif "테스트" in message_lower or "test" in message_lower:
            content = f"✅ AI 비서 테스트 성공!\n\n📱 Discord 연결: 정상\n🤖 메시지 처리: 정상\n👤 사용자: {user_name}\n⏰ 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            content = f"메시지를 받았습니다: \"{user_message}\"\n\n현재는 제한된 기능으로 동작 중입니다. 완전한 AI 기능을 위해서는 Gemini API 키 설정이 필요합니다."
        
        await asyncio.sleep(0.5)  # 실제 AI 처리 시뮬레이션
        
        return AIResponse(
            content=content,
            confidence=0.8,
            reasoning="Mock AI 응답",
            metadata={
                "mode": "mock",
                "original_message": user_message,
                "processed_at": datetime.now().isoformat()
            }
        )
    
    def is_available(self) -> bool:
        """AI 엔진 사용 가능 여부"""
        return self.llm_provider is not None
    
    async def get_status(self) -> Dict[str, Any]:
        """AI 핸들러 상태 정보"""
        status = {
            "ai_engine_available": self.is_available(),
            "api_key_configured": self.settings.has_valid_ai_api_key(),
            "model": "gemini-2.5-pro" if self.is_available() else "mock",
            "mode": "production" if self.is_available() else "mock"
        }
        
        if self.llm_provider:
            try:
                # LLM 제공자 상태 확인
                provider_available = self.llm_provider.is_available()
                status["llm_provider_available"] = provider_available
            except Exception as e:
                status["provider_error"] = str(e)
        
        return status

# 전역 인스턴스
_ai_handler: Optional[AIMessageHandler] = None

def get_ai_handler() -> AIMessageHandler:
    """전역 AI 핸들러 인스턴스 가져오기"""
    global _ai_handler
    if _ai_handler is None:
        logger.info("AI Handler 새로 생성")
        settings = Settings()
        _ai_handler = AIMessageHandler(settings)
        logger.info("AI Handler 초기화 완료")
    return _ai_handler

async def process_discord_message(
    user_message: str,
    user_id: int, 
    user_name: str,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Discord 메시지를 AI로 처리하는 편의 함수
    
    Returns:
        AI 응답 문자열
    """
    handler = get_ai_handler()
    response = await handler.process_message(user_message, str(user_id), "general")
    return response.content
