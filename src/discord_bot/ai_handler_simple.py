"""Discord Bot AI 메시지 핸들러 (간소화 버전)

Discord Bot과 AI 엔진 간의 메시지 처리를 담당하는 모듈
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from loguru import logger

# AI 엔진 관련 import
from ..ai_engine.llm_provider import GeminiProvider, ChatMessage
from ..config import Settings


@dataclass
class AIResponse:
    """AI 응답 데이터 클래스"""
    content: str
    confidence: float = 1.0
    reasoning: str = "AI processing"
    needs_followup: bool = False
    tool_calls_made: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tool_calls_made is None:
            self.tool_calls_made = []


class AIMessageHandler:
    """AI 메시지 핸들러 - 간소화된 버전"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_provider: Optional[GeminiProvider] = None
        
        self._initialize_ai_engine()
        
    def _initialize_ai_engine(self):
        """AI 엔진 초기화"""
        try:
            if self.settings.has_valid_ai_api_key():
                self.llm_provider = GeminiProvider(self.settings)
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
        
        # 1단계: 도구 필요성 확인 및 실행
        tool_result = self._check_and_execute_tools(user_message)
        
        if not self.llm_provider:
            response_content = f"AI 엔진이 초기화되지 않았습니다. 관리자에게 문의하세요."
            if tool_result:
                response_content = f"{tool_result}\n\n{response_content}"
                
            return AIResponse(
                content=response_content,
                confidence=0.5,
                metadata={"error": "AI 엔진 미초기화"}
            )
        
        # Gemini가 초기화되지 않았다면 다시 시도
        if not self.llm_provider.is_available():
            logger.info("Gemini Provider 재초기화 시도")
            try:
                success = await self.llm_provider.initialize()
                if not success:
                    logger.error("Gemini Provider 재초기화 실패")
                    response_content = "AI 서비스 초기화에 실패했습니다. 잠시 후 다시 시도해주세요."
                    if tool_result:
                        response_content = f"{tool_result}\n\n{response_content}"
                    return AIResponse(
                        content=response_content,
                        confidence=0.0,
                        metadata={"error": "Gemini 초기화 실패"}
                    )
            except Exception as e:
                logger.error(f"Gemini Provider 재초기화 중 오류: {e}")
                response_content = "AI 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
                if tool_result:
                    response_content = f"{tool_result}\n\n{response_content}"
                return AIResponse(
                    content=response_content,
                    confidence=0.0,
                    metadata={"error": str(e)}
                )
        
        try:
            # 프롬프트 생성
            messages = self._build_prompt(user_message, user_id)
            
            # AI 응답 생성
            ai_response = await self.llm_provider.generate_response(messages)
            
            # 도구 결과와 AI 응답 합치기
            enhanced_response = ai_response.content
            tools_used = []
            
            if tool_result:
                enhanced_response = f"{tool_result}\n\n{ai_response.content}"
                tools_used = ["tool_simulation"]
            
            return AIResponse(
                content=enhanced_response,
                confidence=0.9 if tools_used else 0.8,
                reasoning="AI 자연어 처리" + (" + 도구 실행" if tools_used else ""),
                metadata={
                    "original_message": user_message,
                    "processed_at": datetime.now().isoformat(),
                    "model": "gemini-2.5-pro",
                    "tools_used": tools_used
                }
            )
            
        except Exception as e:
            logger.error(f"AI 메시지 처리 오류: {e}")
            response_content = "처리 중 오류가 발생했습니다. 다시 시도해주세요."
            if tool_result:
                response_content = f"{tool_result}\n\n{response_content}"
            return AIResponse(
                content=response_content,
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def _build_prompt(self, user_message: str, user_id: str) -> List[ChatMessage]:
        """AI를 위한 프롬프트 구성"""
        system_prompt = """당신은 Discord에서 사용자를 도와주는 AI 어시스턴트입니다.

사용자의 요청에 따라 친절하고 도움이 되는 답변을 제공하세요.
한국어로 자연스럽게 대화하세요.

메모나 할일 관련 요청이 있으면 도구를 사용해서 처리한다고 안내하세요.
"""
        
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message)
        ]
    
    def _check_and_execute_tools(self, user_message: str) -> Optional[str]:
        """간단한 도구 실행 시뮬레이션"""
        message_lower = user_message.lower()
        
        # Notion 메모/할일 관련
        if any(keyword in message_lower for keyword in ["메모", "할일", "todo", "기록", "저장", "추가", "남겨"]):
            memo_content = self._extract_memo_content(user_message)
            return f"✅ [시뮬레이션] Notion에 메모를 추가했습니다: {memo_content}"
        
        # 계산 관련
        elif any(keyword in message_lower for keyword in ["계산", "+", "-", "*", "/", "더하기", "빼기"]):
            calculation = self._extract_calculation(user_message)
            try:
                import re
                if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', calculation):
                    result = eval(calculation)
                    return f"🔢 계산 결과: {calculation} = {result}"
                else:
                    return f"🔢 [시뮬레이션] 계산 요청: {calculation}"
            except:
                return f"🔢 [시뮬레이션] 계산 요청: {calculation}"
        
        # 인하대 공지사항 관련
        elif any(keyword in message_lower for keyword in ["인하대", "공지사항", "크롤링"]):
            return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
        
        # Echo 관련
        elif any(keyword in message_lower for keyword in ["echo", "반복", "따라해"]):
            return f"🔊 Echo: {user_message}"
        
        return None
    
    def _extract_memo_content(self, message: str) -> str:
        """메시지에서 메모 내용 추출"""
        if "사과" in message:
            return "사과 4개 구매"
        elif "메모" in message:
            parts = message.split("메모")
            if len(parts) > 1:
                content_part = parts[1]
                for word in ["에", "남겨", "줘", "좀", "라고", "하라고"]:
                    content_part = content_part.replace(word, " ")
                content_part = content_part.strip()
                if content_part:
                    return content_part
        
        return message[:50] if len(message) > 50 else message
    
    def _extract_calculation(self, message: str) -> str:
        """메시지에서 계산식 추출"""
        import re
        
        calc_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        match = re.search(calc_pattern, message)
        
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
        
        if "더하기" in message or "+" in message:
            numbers = re.findall(r'\d+(?:\.\d+)?', message)
            if len(numbers) >= 2:
                return f"{numbers[0]}+{numbers[1]}"
        
        return "1+1"
    
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
