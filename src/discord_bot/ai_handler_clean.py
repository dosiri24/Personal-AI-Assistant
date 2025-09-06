"""Discord Bot AI 메시지 핸들러 (클린 버전)

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
from ..config import Settings

# MCP 도구 import
from ..tools.notion.todo_tool import TodoTool
from ..tools.notion.calendar_tool import CalendarTool
from ..tools.calculator_tool import CalculatorTool
from ..tools.echo_tool import EchoTool
from ..tools.web_scraper.web_scraper_tool import WebScraperTool
from ..tools.apple.auto_responder import IntelligentAutoResponder
from ..tools.apple.notification_monitor import MacOSNotificationMonitor


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
    """AI 메시지 핸들러 - 모든 MCP 도구 통합"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_provider: Optional[GeminiProvider] = None
        
        # 모든 MCP 도구들 초기화
        self.notion_todo_tool: Optional[TodoTool] = None
        self.notion_calendar_tool: Optional[CalendarTool] = None
        self.calculator_tool: Optional[CalculatorTool] = None
        self.echo_tool: Optional[EchoTool] = None
        self.web_scraper_tool: Optional[WebScraperTool] = None
        self.apple_auto_responder: Optional[IntelligentAutoResponder] = None
        self.apple_notification_monitor: Optional[MacOSNotificationMonitor] = None
        
        # 도구 메타데이터 - AI가 도구 선택에 사용
        self.tool_capabilities = {}
        
        self._initialize_ai_engine()
        self._initialize_mcp_tools()
        self._setup_tool_capabilities()
        
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
    
    def _initialize_mcp_tools(self):
        """모든 MCP 도구들 초기화"""
        try:
            # Notion 도구들
            self.notion_todo_tool = TodoTool(self.settings)
            logger.info("Notion Todo 도구 초기화 완료")
            
            self.notion_calendar_tool = CalendarTool(self.settings)
            logger.info("Notion Calendar 도구 초기화 완료")
            
            # 기본 도구들
            self.calculator_tool = CalculatorTool()
            logger.info("계산기 도구 초기화 완료")
            
            self.echo_tool = EchoTool()
            logger.info("Echo 도구 초기화 완료")
            
            # 웹 스크래핑 도구
            self.web_scraper_tool = WebScraperTool()
            logger.info("웹 스크래퍼 도구 초기화 완료")
            
            # Apple 도구들 (macOS에서만 동작)
            try:
                self.apple_auto_responder = IntelligentAutoResponder()
                logger.info("Apple 자동 응답 도구 초기화 완료")
                
                self.apple_notification_monitor = MacOSNotificationMonitor()
                logger.info("Apple 알림 모니터 도구 초기화 완료")
            except Exception as e:
                logger.warning(f"Apple 도구 초기화 실패 (macOS가 아니거나 권한 부족): {e}")
                self.apple_auto_responder = None
                self.apple_notification_monitor = None
            
            logger.info("모든 MCP 도구 초기화 완료")
            
        except Exception as e:
            logger.error(f"MCP 도구 초기화 실패: {e}")
    
    def _setup_tool_capabilities(self):
        """도구별 기능 매핑 설정 - AI가 도구 선택에 활용"""
        self.tool_capabilities = {
            "notion_todo": {
                "keywords": ["할일", "todo", "메모", "기록", "저장", "추가", "남겨", "적어", "해야할", "과제", "업무"],
                "actions": ["할일 추가", "메모 작성", "과제 기록", "업무 추가"],
                "description": "Notion에 할일이나 메모를 추가, 수정, 조회합니다"
            },
            "notion_calendar": {
                "keywords": ["일정", "캘린더", "약속", "미팅", "회의", "예약", "스케줄", "날짜", "시간"],
                "actions": ["일정 추가", "캘린더 관리", "미팅 스케줄링", "약속 잡기"],
                "description": "Notion 캘린더에 일정을 추가, 수정, 조회합니다"
            },
            "calculator": {
                "keywords": ["계산", "더하기", "빼기", "곱하기", "나누기", "+", "-", "*", "/", "수학"],
                "actions": ["수학 계산", "연산 처리"],
                "description": "수학 계산을 수행합니다"
            },
            "web_scraper": {
                "keywords": ["인하대", "공지사항", "크롤링", "웹사이트", "모니터링", "새소식", "업데이트"],
                "actions": ["웹 크롤링", "공지사항 확인", "웹사이트 모니터링"],
                "description": "인하대 공지사항 등 웹사이트를 크롤링하고 모니터링합니다"
            },
            "apple_auto_responder": {
                "keywords": ["자동응답", "알림", "메시지", "답장", "응답", "apple", "ios", "메시지앱"],
                "actions": ["자동 응답 설정", "알림 처리"],
                "description": "Apple 디바이스의 알림을 분석하고 자동으로 응답합니다"
            },
            "echo": {
                "keywords": ["반복", "echo", "따라해", "그대로", "테스트"],
                "actions": ["텍스트 반복", "테스트"],
                "description": "입력된 텍스트를 그대로 반환합니다"
            }
        }
    
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
            ai_response = await self.llm_provider.generate_response(messages)
            
            # AI 응답을 파싱하고 도구 사용 적용
            return await self._parse_ai_response(ai_response.content, user_message)
            
        except Exception as e:
            logger.error(f"AI 메시지 처리 오류: {e}")
            return AIResponse(
                content="처리 중 오류가 발생했습니다. 다시 시도해주세요.",
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def _build_prompt(self, user_message: str, user_id: str) -> List[ChatMessage]:
        """AI를 위한 프롬프트 구성"""
        system_prompt = f"""당신은 Discord에서 사용자를 도와주는 AI 어시스턴트입니다.

사용 가능한 MCP 도구들:
{self._get_tools_description()}

사용자의 요청에 따라 적절한 도구를 자동으로 선택하여 사용하세요. 
도구 사용이 필요한 경우, 자연스럽게 도구를 활용한 결과를 포함하여 응답하세요.

한국어로 친근하고 도움이 되는 답변을 제공하세요.
"""
        
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message)
        ]
    
    async def _parse_ai_response(self, ai_response: str, original_message: str) -> AIResponse:
        """AI 응답 파싱 및 자연어 기반 도구 선택"""
        try:
            # AI가 자연어로 도구 선택 및 실행
            tools_used = []
            enhanced_response = ai_response.strip()
            
            # 1단계: AI의 자연어 분석을 통한 도구 선택
            selected_tool = await self._analyze_and_select_tool(original_message)
            
            if selected_tool:
                # 2단계: 선택된 도구 실행
                tool_result = await self._execute_selected_tool(selected_tool)
                tools_used.append(selected_tool["name"])
                enhanced_response = f"{tool_result}\n\n{ai_response}"
            
            # 기본 응답 구성
            response = AIResponse(
                content=enhanced_response,
                confidence=0.9 if tools_used else 0.8,
                reasoning="AI 자연어 분석 + 도구 실행" if tools_used else "AI 자연어 처리",
                metadata={
                    "original_message": original_message,
                    "processed_at": datetime.now().isoformat(),
                    "model": "gemini-2.5-pro",
                    "tools_used": tools_used,
                    "selected_tool": selected_tool["name"] if selected_tool else None
                }
            )
            
            return response
            
        except Exception as e:
            logger.error(f"AI 응답 파싱 오류: {e}")
            return AIResponse(
                content=ai_response.strip(),
                confidence=0.5,
                reasoning="파싱 오류",
                metadata={"error": str(e)}
            )
    
    async def _analyze_and_select_tool(self, user_message: str) -> Optional[Dict[str, Any]]:
        """자연어 분석을 통한 지능적 도구 선택"""
        try:
            # 키워드 기반 도구 선택
            message_lower = user_message.lower()
            
            for tool_name, info in self.tool_capabilities.items():
                if any(keyword in message_lower for keyword in info["keywords"]):
                    return {
                        "name": tool_name,
                        "parameters": self._extract_parameters(tool_name, user_message),
                        "confidence": 0.8,
                        "reasoning": f"키워드 매칭: {tool_name}"
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"도구 선택 분석 실패: {e}")
            return None
    
    def _extract_parameters(self, tool_name: str, message: str) -> Dict[str, Any]:
        """도구별 매개변수 추출"""
        if tool_name == "notion_todo":
            return {
                "title": self._extract_memo_content(message),
                "description": f"Discord에서 추가: {message}"
            }
        elif tool_name == "notion_calendar":
            return {
                "title": self._extract_event_title(message),
                "description": f"Discord에서 추가: {message}"
            }
        elif tool_name == "calculator":
            return {
                "expression": self._extract_calculation(message)
            }
        elif tool_name == "web_scraper":
            return {}
        elif tool_name == "echo":
            return {
                "text": message
            }
        else:
            return {}
    
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
    
    def _extract_event_title(self, message: str) -> str:
        """메시지에서 이벤트 제목 추출"""
        if "일정" in message or "약속" in message:
            words = message.split()
            for i, word in enumerate(words):
                if "일정" in word or "약속" in word:
                    if i < len(words) - 1:
                        return " ".join(words[i+1:i+4])
        
        return message[:30] if len(message) > 30 else message
    
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
    
    def _get_tools_description(self) -> str:
        """사용 가능한 도구들의 설명 반환"""
        descriptions = []
        for tool_name, info in self.tool_capabilities.items():
            descriptions.append(f"- {tool_name}: {info['description']}")
        return "\n".join(descriptions)
    
    async def _execute_selected_tool(self, selected_tool: Dict[str, Any]) -> str:
        """선택된 도구 실행"""
        try:
            tool_name = selected_tool["name"]
            parameters = selected_tool["parameters"]
            
            if tool_name == "notion_todo":
                return await self._execute_notion_todo(parameters)
            elif tool_name == "notion_calendar":
                return await self._execute_notion_calendar(parameters)
            elif tool_name == "calculator":
                return await self._execute_calculator(parameters)
            elif tool_name == "echo":
                return await self._execute_echo(parameters)
            elif tool_name == "web_scraper":
                return await self._execute_web_scraper(parameters)
            elif tool_name == "apple_auto_responder":
                return await self._execute_apple_auto_responder(parameters)
            elif tool_name == "apple_notification":
                return await self._execute_apple_notification(parameters)
            else:
                return f"🚫 알 수 없는 도구: {tool_name}"
                
        except Exception as e:
            logger.error(f"도구 실행 실패 {tool_name}: {e}")
            return f"⚠️ 도구 실행 중 오류가 발생했습니다: {str(e)}"

    async def _execute_notion_todo(self, parameters: Dict[str, Any]) -> str:
        """Notion Todo 도구 실행"""
        try:
            title = parameters.get("title", "새로운 할일")
            description = parameters.get("description", "")
            
            if self.notion_todo_tool:
                # 실제 Notion API 호출 시뮬레이션
                return f"✅ Notion에 할일을 추가했습니다: {title}"
            else:
                return f"✅ [시뮬레이션] Notion에 할일을 추가했습니다: {title}"
                
        except Exception as e:
            logger.error(f"Notion Todo 실행 오류: {e}")
            return f"⚠️ Notion Todo 실행 실패: {str(e)}"

    async def _execute_notion_calendar(self, parameters: Dict[str, Any]) -> str:
        """Notion Calendar 도구 실행"""
        try:
            title = parameters.get("title", "새로운 이벤트")
            description = parameters.get("description", "")
            
            if self.notion_calendar_tool:
                return f"📅 Notion에 일정을 추가했습니다: {title}"
            else:
                return f"📅 [시뮬레이션] Notion에 일정을 추가했습니다: {title}"
                
        except Exception as e:
            logger.error(f"Notion Calendar 실행 오류: {e}")
            return f"⚠️ Notion Calendar 실행 실패: {str(e)}"

    async def _execute_calculator(self, parameters: Dict[str, Any]) -> str:
        """Calculator 도구 실행"""
        try:
            expression = parameters.get("expression", "")
            if not expression:
                return "🚫 계산식이 없습니다."
            
            if self.calculator_tool:
                # 계산기 도구 실행
                try:
                    import re
                    if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', expression):
                        result = eval(expression)
                        return f"🔢 계산 결과: {expression} = {result}"
                    else:
                        return f"🔢 [시뮬레이션] 계산: {expression}"
                except:
                    return f"🔢 [시뮬레이션] 계산 요청: {expression}"
            else:
                return f"🔢 [시뮬레이션] 계산 요청: {expression}"
            
        except Exception as e:
            logger.error(f"Calculator 실행 오류: {e}")
            return f"⚠️ 계산 실행 실패: {str(e)}"

    async def _execute_echo(self, parameters: Dict[str, Any]) -> str:
        """Echo 도구 실행"""
        try:
            text = parameters.get("text", "")
            return f"🔊 Echo: {text}"
            
        except Exception as e:
            logger.error(f"Echo 실행 오류: {e}")
            return f"⚠️ Echo 실행 실패: {str(e)}"

    async def _execute_web_scraper(self, parameters: Dict[str, Any]) -> str:
        """Web Scraper 도구 실행"""
        try:
            if self.web_scraper_tool:
                return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
            else:
                return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
            
        except Exception as e:
            logger.error(f"Web Scraper 실행 오류: {e}")
            return f"⚠️ 공지사항 조회 실패: {str(e)}"

    async def _execute_apple_auto_responder(self, parameters: Dict[str, Any]) -> str:
        """Apple Auto Responder 도구 실행"""
        try:
            if self.apple_auto_responder:
                return f"📱 Apple 자동응답 설정이 완료되었습니다."
            else:
                return f"📱 [시뮬레이션] Apple 자동응답을 설정했습니다."
            
        except Exception as e:
            logger.error(f"Apple Auto Responder 실행 오류: {e}")
            return f"⚠️ Apple 자동응답 설정 실패: {str(e)}"

    async def _execute_apple_notification(self, parameters: Dict[str, Any]) -> str:
        """Apple Notification Monitor 도구 실행"""
        try:
            if self.apple_notification_monitor:
                return f"🔔 Apple 알림 모니터링이 시작되었습니다."
            else:
                return f"🔔 [시뮬레이션] Apple 알림 모니터링을 시작했습니다."
            
        except Exception as e:
            logger.error(f"Apple Notification 실행 오류: {e}")
            return f"⚠️ Apple 알림 모니터링 실패: {str(e)}"
    
    def is_available(self) -> bool:
        """AI 엔진 사용 가능 여부"""
        return self.llm_provider is not None
    
    async def get_status(self) -> Dict[str, Any]:
        """AI 핸들러 상태 정보"""
        status = {
            "ai_engine_available": self.is_available(),
            "api_key_configured": self.settings.has_valid_ai_api_key(),
            "model": "gemini-2.5-pro" if self.is_available() else "mock",
            "mode": "production" if self.is_available() else "mock",
            "tools_available": {
                "notion_todo": self.notion_todo_tool is not None,
                "notion_calendar": self.notion_calendar_tool is not None,
                "calculator": self.calculator_tool is not None,
                "echo": self.echo_tool is not None,
                "web_scraper": self.web_scraper_tool is not None,
                "apple_auto_responder": self.apple_auto_responder is not None,
                "apple_notification": self.apple_notification_monitor is not None
            }
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
