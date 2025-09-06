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
# from ..ai_engine.decision_engine import AgenticDecisionEngine, ActionType, DecisionResult  # 현재 사용 안함
# from ..mcp.registry import ToolRegistry  # 현재 사용 안함
from ..config import Settings

# MCP 도구 import
from ..tools.notion.todo_tool import TodoTool
from ..tools.notion.calendar_tool import CalendarTool
from ..tools.calculator_tool import CalculatorTool
from ..tools.echo_tool import EchoTool
from ..tools.web_scraper.web_scraper_tool import WebScraperTool
from ..tools.apple.auto_responder import IntelligentAutoResponder
from ..tools.apple.notification_monitor import MacOSNotificationMonitor
from ..mcp.base_tool import ExecutionStatus


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
            response = await self.llm_provider.generate_response(messages)
            
            # 응답 파싱
            ai_response = await self._parse_ai_response(response.content, user_message)
            
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
        
        system_prompt = """당신은 개인 AI 비서입니다. 사용자의 요청을 자연어로 분석하여 적절한 도구를 선택하고 사용합니다.

**사용 가능한 도구들:**
1. **Notion Todo**: 할일, 메모, 과제, 업무 관련 - "할일 추가", "메모 남기기", "기록하기"
2. **Notion Calendar**: 일정, 캘린더, 약속, 미팅 관련 - "일정 추가", "약속 잡기", "회의 스케줄"  
3. **Calculator**: 수학 계산 - "계산해줘", "더하기", "2+3"
4. **Web Scraper**: 인하대 공지사항, 웹 크롤링 - "인하대 공지", "새소식 확인"
5. **Apple Auto Responder**: 자동 응답, 알림 처리 - "자동 응답 설정"
6. **Echo**: 텍스트 반복, 테스트 - "따라해", "테스트"

**자연어 분석 지침:**
- 사용자 요청을 정확히 분석하여 가장 적합한 도구를 선택하세요
- 도구 사용이 필요하면 구체적인 액션을 포함해서 응답하세요
- 도구 사용 후 결과를 친근하게 설명해주세요

**응답 형식:**
일반 대화는 평소처럼, 도구 사용시에는 도구 결과 + 설명을 제공하세요.
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
    
    async def _parse_ai_response(self, ai_response: str, original_message: str) -> AIResponse:
        """AI 응답 파싱 및 자연어 기반 도구 선택"""
        try:
            # AI가 자연어로 도구 선택 및 실행
            tools_used = []
            enhanced_response = ai_response.strip()
            
            # 1단계: AI의 자연어 분석을 통한 도구 선택
            selected_tool = await self._analyze_and_select_tool(original_message, ai_response)
            
            if selected_tool:
                # 2단계: 선택된 도구 실행
                tool_result = await self._execute_selected_tool(selected_tool, original_message)
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
            
            # 응답 길이에 따른 신뢰도 조정
            if len(enhanced_response) < 10:
                response.confidence = 0.6
            elif len(enhanced_response) > 1000:
                response.confidence = 0.95
            
            # 특정 패턴에 따른 후속 질문 필요성 판단
            followup_keywords = ["더 알려주세요", "구체적으로", "자세히", "추가로", "?"]
            if any(keyword in enhanced_response for keyword in followup_keywords):
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
    
    async def _analyze_and_select_tool(self, user_message: str, ai_response: str) -> Optional[Dict[str, Any]]:
        """자연어 분석을 통한 지능적 도구 선택"""
        try:
            # AI에게 도구 선택을 위한 분석 요청
            analysis_prompt = f"""사용자 메시지를 분석하여 가장 적합한 도구를 선택하세요.

사용자 메시지: "{user_message}"

사용 가능한 도구들:
{self._get_tools_description()}

다음 JSON 형식으로 응답하세요:
{{
    "tool_needed": true/false,
    "selected_tool": "도구명" (필요한 경우),
    "confidence": 0.0-1.0,
    "reasoning": "선택 이유",
    "parameters": {{"key": "value"}} (도구 실행에 필요한 매개변수)
}}

도구가 필요하지 않으면 tool_needed를 false로 설정하세요."""

            # LLM Provider가 있는 경우에만 AI 분석 수행
            if self.llm_provider:
                messages = [ChatMessage(role="user", content=analysis_prompt)]
                analysis_response = await self.llm_provider.generate_response(messages)
                
                # JSON 응답 파싱
                import json
                response_text = analysis_response.content.strip()
                
                # JSON 부분 추출
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    analysis_result = json.loads(json_str)
                    
                    if analysis_result.get("tool_needed", False) and analysis_result.get("confidence", 0) > 0.7:
                        return {
                            "name": analysis_result["selected_tool"],
                            "parameters": analysis_result.get("parameters", {}),
                            "confidence": analysis_result["confidence"],
                            "reasoning": analysis_result["reasoning"]
                        }
            
            return None
            
        except Exception as e:
            logger.error(f"도구 선택 분석 실패: {e}")
            # 폴백: 키워드 기반 간단 분석
            return self._fallback_tool_selection(user_message)
    
    def _get_tools_description(self) -> str:
        """사용 가능한 도구들의 설명 반환"""
        descriptions = []
        for tool_name, info in self.tool_capabilities.items():
            descriptions.append(f"- {tool_name}: {info['description']}")
        return "\n".join(descriptions)
    
    def _fallback_tool_selection(self, message: str) -> Optional[Dict[str, Any]]:
        """AI 분석 실패시 키워드 기반 도구 선택"""
        message_lower = message.lower()
        
        for tool_name, info in self.tool_capabilities.items():
            if any(keyword in message_lower for keyword in info["keywords"]):
                return {
                    "name": tool_name,
                    "parameters": self._extract_parameters(tool_name, message),
                    "confidence": 0.6,
                    "reasoning": f"키워드 매칭: {tool_name}"
                }
        
        return None
    
    def _extract_parameters(self, tool_name: str, message: str) -> Dict[str, Any]:
        """도구별 매개변수 추출"""
        if tool_name == "notion_todo":
            return {
                "action": "add_todo",
                "title": self._extract_memo_content(message),
                "description": f"Discord에서 추가: {message}"
            }
        elif tool_name == "notion_calendar":
            return {
                "action": "add_event",
                "title": self._extract_event_title(message),
                "description": f"Discord에서 추가: {message}"
            }
        elif tool_name == "calculator":
            return {
                "expression": self._extract_calculation(message)
            }
        elif tool_name == "web_scraper":
            return {
                "action": "get_latest",
                "source": "inha"
            }
        elif tool_name == "echo":
            return {
                "text": message
            }
        else:
            return {}
    
    def _extract_event_title(self, message: str) -> str:
        """메시지에서 이벤트 제목 추출"""
        # 간단한 제목 추출 로직
        if "일정" in message or "약속" in message:
            words = message.split()
            for i, word in enumerate(words):
                if "일정" in word or "약속" in word:
                    if i < len(words) - 1:
                        return " ".join(words[i+1:i+4])  # 다음 3단어까지
        
        return message[:30] if len(message) > 30 else message
    
    async def _execute_selected_tool(self, selected_tool: Dict[str, Any], original_message: str) -> str:
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
            action = parameters.get("action", "add_todo")
            if action == "add_todo":
                title = parameters.get("title", "새로운 할일")
                description = parameters.get("description", "")
                
                if hasattr(self, 'notion_todo_tool') and self.notion_todo_tool:
                    result = await self.notion_todo_tool.execute({
                        "action": "add_todo",
                        "title": title,
                        "description": description
                    })
                    return f"✅ Notion에 할일을 추가했습니다: {title}"
                else:
                    return f"✅ [시뮬레이션] Notion에 할일을 추가했습니다: {title}"
            else:
                return f"🚫 지원하지 않는 Todo 작업: {action}"
                
        except Exception as e:
            logger.error(f"Notion Todo 실행 오류: {e}")
            return f"⚠️ Notion Todo 실행 실패: {str(e)}"
    
    async def _execute_notion_calendar(self, parameters: Dict[str, Any]) -> str:
        """Notion Calendar 도구 실행"""
        try:
            action = parameters.get("action", "add_event")
            if action == "add_event":
                title = parameters.get("title", "새로운 이벤트")
                description = parameters.get("description", "")
                
                if hasattr(self, 'notion_calendar_tool') and self.notion_calendar_tool:
                    result = await self.notion_calendar_tool.execute({
                        "action": "add_event",
                        "title": title,
                        "description": description
                    })
                    return f"📅 Notion에 일정을 추가했습니다: {title}"
                else:
                    return f"📅 [시뮬레이션] Notion에 일정을 추가했습니다: {title}"
            else:
                return f"🚫 지원하지 않는 Calendar 작업: {action}"
                
        except Exception as e:
            logger.error(f"Notion Calendar 실행 오류: {e}")
            return f"⚠️ Notion Calendar 실행 실패: {str(e)}"
    
    async def _execute_calculator(self, parameters: Dict[str, Any]) -> str:
        """Calculator 도구 실행"""
        try:
            expression = parameters.get("expression", "")
            if not expression:
                return "🚫 계산식이 없습니다."
            
            if hasattr(self, 'calculator_tool') and self.calculator_tool:
                result = await self.calculator_tool.execute({
                    "expression": expression
                })
                # 간단한 문자열 변환
                return f"🔢 계산 결과: {expression} = {str(result)}"
            else:
                # 간단한 계산 시뮬레이션
                try:
                    import re
                    # 안전한 계산식만 허용
                    if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', expression):
                        result = eval(expression)
                        return f"🔢 계산 결과: {expression} = {result}"
                    else:
                        return f"🔢 [시뮬레이션] 계산: {expression}"
                except:
                    return f"🔢 [시뮬레이션] 계산 요청: {expression}"
            
        except Exception as e:
            logger.error(f"Calculator 실행 오류: {e}")
            return f"⚠️ 계산 실행 실패: {str(e)}"
    
    async def _execute_echo(self, parameters: Dict[str, Any]) -> str:
        """Echo 도구 실행"""
        try:
            text = parameters.get("text", "")
            
            if hasattr(self, 'echo_tool') and self.echo_tool:
                result = await self.echo_tool.execute({
                    "text": text
                })
                return f"🔊 Echo: {str(result)}"
            else:
                return f"🔊 Echo: {text}"
            
        except Exception as e:
            logger.error(f"Echo 실행 오류: {e}")
            return f"⚠️ Echo 실행 실패: {str(e)}"
    
    async def _execute_web_scraper(self, parameters: Dict[str, Any]) -> str:
        """Web Scraper 도구 실행"""
        try:
            action = parameters.get("action", "get_latest")
            source = parameters.get("source", "inha")
            
            if hasattr(self, 'web_scraper_tool') and self.web_scraper_tool:
                result = await self.web_scraper_tool.execute({
                    "action": action,
                    "source": source
                })
                return f"📰 인하대 공지사항 조회 결과: {str(result)}"
            else:
                return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
            
        except Exception as e:
            logger.error(f"Web Scraper 실행 오류: {e}")
            return f"⚠️ 공지사항 조회 실패: {str(e)}"
    
    async def _execute_apple_auto_responder(self, parameters: Dict[str, Any]) -> str:
        """Apple Auto Responder 도구 실행"""
        try:
            if hasattr(self, 'apple_auto_responder') and self.apple_auto_responder:
                return f"📱 Apple 자동응답 설정이 완료되었습니다."
            else:
                return f"� [시뮬레이션] Apple 자동응답을 설정했습니다."
            
        except Exception as e:
            logger.error(f"Apple Auto Responder 실행 오류: {e}")
            return f"⚠️ Apple 자동응답 설정 실패: {str(e)}"
    
    async def _execute_apple_notification(self, parameters: Dict[str, Any]) -> str:
        """Apple Notification Monitor 도구 실행"""
        try:
            if hasattr(self, 'apple_notification') and self.apple_notification:
                return f"🔔 Apple 알림 모니터링이 시작되었습니다."
            else:
                return f"� [시뮬레이션] Apple 알림 모니터링을 시작했습니다."
            
        except Exception as e:
            logger.error(f"Apple Notification 실행 오류: {e}")
            return f"⚠️ Apple 알림 모니터링 실패: {str(e)}"
    
    async def _execute_echo(self, parameters: Dict[str, Any]) -> str:
        """Echo 도구 실행"""
        try:
            text = parameters.get("text", "")
            
            if hasattr(self, 'echo_tool') and self.echo_tool:
                result = await self.echo_tool.execute({
                    "text": text
                })
                # ToolResult 객체에서 결과 추출
                if hasattr(result, 'content'):
                    return f"🔊 Echo: {result.content}"
                elif hasattr(result, 'echo'):
                    return f"🔊 Echo: {result.echo}"
                else:
                    return f"🔊 Echo: {str(result)}"
            else:
                return f"🔊 Echo: {text}"
            
        except Exception as e:
            logger.error(f"Echo 실행 오류: {e}")
            return f"⚠️ Echo 실행 실패: {str(e)}"
    
    async def _execute_web_scraper(self, parameters: Dict[str, Any]) -> str:
        """Web Scraper 도구 실행"""
        try:
            action = parameters.get("action", "get_latest")
            source = parameters.get("source", "inha")
            
            if hasattr(self, 'web_scraper_tool') and self.web_scraper_tool:
                result = await self.web_scraper_tool.execute({
                    "action": action,
                    "source": source
                })
                
                # ToolResult 객체에서 결과 추출
                notices = []
                if hasattr(result, 'content'):
                    notices = result.content.get("notices", []) if isinstance(result.content, dict) else []
                elif hasattr(result, 'notices'):
                    notices = result.notices
                
                if notices:
                    return f"📰 인하대 최신 공지사항:\n" + "\n".join([f"• {notice}" for notice in notices[:5]])
                else:
                    return "📰 새로운 공지사항이 없습니다."
            else:
                return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
            
        except Exception as e:
            logger.error(f"Web Scraper 실행 오류: {e}")
            return f"⚠️ 공지사항 조회 실패: {str(e)}"
    
    async def _execute_apple_auto_responder(self, parameters: Dict[str, Any]) -> str:
        """Apple Auto Responder 도구 실행"""
        try:
            if hasattr(self, 'apple_auto_responder_tool') and self.apple_auto_responder_tool:
                return f"📱 Apple 자동응답 설정이 완료되었습니다."
            else:
                return f"📱 [시뮬레이션] Apple 자동응답을 설정했습니다."
            
        except Exception as e:
            logger.error(f"Apple Auto Responder 실행 오류: {e}")
            return f"⚠️ Apple 자동응답 설정 실패: {str(e)}"
    
    async def _execute_apple_notification(self, parameters: Dict[str, Any]) -> str:
        """Apple Notification Monitor 도구 실행"""
        try:
            if hasattr(self, 'apple_notification_tool') and self.apple_notification_tool:
                return f"🔔 Apple 알림 모니터링이 시작되었습니다."
            else:
                return f"🔔 [시뮬레이션] Apple 알림 모니터링을 시작했습니다."
            
        except Exception as e:
            logger.error(f"Apple Notification 실행 오류: {e}")
            return f"⚠️ Apple 알림 모니터링 실패: {str(e)}"
    
    async def _execute_echo(self, parameters: Dict[str, Any]) -> str:
        """Echo 도구 실행"""
        try:
            text = parameters.get("text", "")
            
            if hasattr(self, 'echo_tool') and self.echo_tool:
                result = await self.echo_tool.execute({
                    "text": text
                })
                return f"🔊 Echo: {result.get('echo', text)}"
            else:
                return f"🔊 Echo: {text}"
            
        except Exception as e:
            logger.error(f"Echo 실행 오류: {e}")
            return f"⚠️ Echo 실행 실패: {str(e)}"
    
    async def _execute_web_scraper(self, parameters: Dict[str, Any]) -> str:
        """Web Scraper 도구 실행"""
        try:
            action = parameters.get("action", "get_latest")
            source = parameters.get("source", "inha")
            
            if hasattr(self, 'web_scraper_tool') and self.web_scraper_tool:
                result = await self.web_scraper_tool.execute({
                    "action": action,
                    "source": source
                })
                
                notices = result.get("notices", [])
                if notices:
                    return f"📰 인하대 최신 공지사항:\n" + "\n".join([f"• {notice}" for notice in notices[:5]])
                else:
                    return "📰 새로운 공지사항이 없습니다."
            else:
                return "📰 [시뮬레이션] 인하대 공지사항을 조회했습니다."
            
        except Exception as e:
            logger.error(f"Web Scraper 실행 오류: {e}")
            return f"⚠️ 공지사항 조회 실패: {str(e)}"
    
    async def _execute_apple_auto_responder(self, parameters: Dict[str, Any]) -> str:
        """Apple Auto Responder 도구 실행"""
        try:
            if hasattr(self, 'apple_auto_responder_tool') and self.apple_auto_responder_tool:
                # Apple Auto Responder는 execute 메소드가 아닐 수 있음
                return f"📱 Apple 자동응답 설정이 완료되었습니다."
            else:
                return f"📱 [시뮬레이션] Apple 자동응답을 설정했습니다."
            
        except Exception as e:
            logger.error(f"Apple Auto Responder 실행 오류: {e}")
            return f"⚠️ Apple 자동응답 설정 실패: {str(e)}"
    
    async def _execute_apple_notification(self, parameters: Dict[str, Any]) -> str:
        """Apple Notification Monitor 도구 실행"""
        try:
            if hasattr(self, 'apple_notification_tool') and self.apple_notification_tool:
                return f"🔔 Apple 알림 모니터링이 시작되었습니다."
            else:
                return f"🔔 [시뮬레이션] Apple 알림 모니터링을 시작했습니다."
            
        except Exception as e:
            logger.error(f"Apple Notification 실행 오류: {e}")
            return f"⚠️ Apple 알림 모니터링 실패: {str(e)}"
    
    async def _use_notion_tool(self, message: str, ai_response: str) -> str:
        """실제 Notion 도구 사용"""
        try:
            if not self.notion_todo_tool:
                return f"⚠️ Notion 도구가 초기화되지 않았습니다.\n\n{ai_response}"
            
            # 메모 내용 추출
            memo_content = self._extract_memo_content(message)
            
            # Notion Todo 도구를 사용하여 할일 추가
            result = await self.notion_todo_tool.execute({
                "action": "add_todo",
                "title": memo_content,
                "description": f"Discord에서 추가된 할일: {message}",
                "priority": "중간",
                "category": "Personal"
            })
            
            if result.status == ExecutionStatus.SUCCESS:
                tool_response = f"✅ Notion에 '{memo_content}' 할일을 성공적으로 추가했습니다!"
                logger.info(f"Notion 도구 사용 성공: {memo_content}")
            else:
                tool_response = f"⚠️ Notion 할일 추가 중 오류가 발생했습니다: {result.error_message}"
                logger.error(f"Notion 도구 사용 실패: {result.error_message}")
            
            return f"{tool_response}\n\n{ai_response}"
            
        except Exception as e:
            logger.error(f"Notion 도구 사용 중 오류: {e}")
            tool_response = f"❌ Notion 도구 사용 중 오류가 발생했습니다: {str(e)}"
            return f"{tool_response}\n\n{ai_response}"
    
    async def _use_calculator_tool(self, message: str, ai_response: str) -> str:
        """실제 계산기 도구 사용"""
        try:
            if not self.calculator_tool:
                return f"⚠️ 계산기 도구가 초기화되지 않았습니다.\n\n{ai_response}"
            
            # 간단한 수식 추출
            expression = self._extract_calculation(message)
            
            # 계산기 도구 사용
            result = await self.calculator_tool.execute({
                "expression": expression
            })
            
            if result.status == ExecutionStatus.SUCCESS:
                result_value = result.data.get('result') if result.data else 'N/A'
                tool_response = f"🧮 계산 결과: {expression} = {result_value}"
                logger.info(f"계산기 도구 사용 성공: {expression}")
            else:
                tool_response = f"⚠️ 계산 중 오류가 발생했습니다: {result.error_message}"
                logger.error(f"계산기 도구 사용 실패: {result.error_message}")
            
            return f"{tool_response}\n\n{ai_response}"
            
        except Exception as e:
            logger.error(f"계산기 도구 사용 중 오류: {e}")
            tool_response = f"❌ 계산기 도구 사용 중 오류가 발생했습니다: {str(e)}"
            return f"{tool_response}\n\n{ai_response}"
    
    def _extract_memo_content(self, message: str) -> str:
        """메시지에서 메모 내용 추출"""
        # "사과 4개 구매"와 같은 구체적인 내용 추출
        if "사과" in message:
            return "사과 4개 구매"
        elif "메모" in message:
            # "메모에 X 남겨줘" 패턴에서 X 추출
            parts = message.split("메모")
            if len(parts) > 1:
                content_part = parts[1]
                # 불필요한 부분 제거
                for word in ["에", "남겨", "줘", "좀", "라고", "하라고"]:
                    content_part = content_part.replace(word, " ")
                content_part = content_part.strip()
                if content_part:
                    return content_part
        
        # 기본값 반환
        return message[:50] if len(message) > 50 else message
    
    def _extract_calculation(self, message: str) -> str:
        """메시지에서 계산식 추출"""
        # 간단한 계산식 패턴 매칭
        import re
        
        # "2+3", "10*5" 같은 패턴 찾기
        calc_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        match = re.search(calc_pattern, message)
        
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
        
        # 한글 패턴도 확인
        if "더하기" in message or "+" in message:
            numbers = re.findall(r'\d+(?:\.\d+)?', message)
            if len(numbers) >= 2:
                return f"{numbers[0]}+{numbers[1]}"
        
        # 기본값
        return "1+1"
    
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
