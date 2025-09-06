"""Discord Bot AI 메시지 핸들러 (실제 MCP 도구 통합)

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

# MCP 도구 import
from ..mcp.base_tool import ExecutionStatus
from ..tools.notion.todo_tool import TodoTool
from ..tools.notion.calendar_tool import CalendarTool
from ..tools.calculator_tool import CalculatorTool
from ..tools.echo_tool import EchoTool
# from ..tools.web_scraper.web_scraper_tool import WebScraperTool  # 일시적으로 비활성화
try:
    from ..tools.apple.auto_responder import IntelligentAutoResponder
    from ..tools.apple.notification_monitor import MacOSNotificationMonitor
    APPLE_TOOLS_AVAILABLE = True
except ImportError:
    APPLE_TOOLS_AVAILABLE = False
    logger.warning("Apple 도구들을 가져올 수 없습니다 (macOS가 아니거나 권한 부족)")


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
    """AI 메시지 핸들러 - 실제 MCP 도구 통합"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_provider: Optional[GeminiProvider] = None
        
        # MCP 도구들
        self.notion_todo_tool: Optional[TodoTool] = None
        self.notion_calendar_tool: Optional[CalendarTool] = None
        self.calculator_tool: Optional[CalculatorTool] = None
        self.echo_tool: Optional[EchoTool] = None
        # self.web_scraper_tool: Optional[WebScraperTool] = None  # 일시적으로 비활성화
        self.apple_auto_responder: Optional[Any] = None
        self.apple_notification_monitor: Optional[Any] = None
        
        # 도구 연결 상태
        self.tools_status = {}
        
        self._initialize_ai_engine()
        self._initialize_mcp_tools()
        self._report_tools_status()
        
    def _initialize_ai_engine(self):
        """AI 엔진 초기화"""
        try:
            if self.settings.has_valid_ai_api_key():
                self.llm_provider = GeminiProvider(self.settings)
                asyncio.create_task(self._async_initialize_gemini())
                logger.info("✅ AI 엔진 초기화 완료")
            else:
                logger.warning("⚠️ AI API 키가 설정되지 않음. Mock 모드로 동작")
                self.llm_provider = None
        except Exception as e:
            logger.error(f"❌ AI 엔진 초기화 실패: {e}")
            self.llm_provider = None

    def _initialize_mcp_tools(self):
        """실제 MCP 도구들 초기화"""
        logger.info("🔧 MCP 도구들 초기화 시작...")
        
        # 1. Notion Todo Tool
        try:
            self.notion_todo_tool = TodoTool(self.settings)
            self.tools_status["notion_todo"] = "✅ 연결됨"
            logger.info("✅ Notion Todo 도구 초기화 완료")
        except Exception as e:
            self.tools_status["notion_todo"] = f"❌ 실패: {str(e)}"
            logger.error(f"❌ Notion Todo 도구 초기화 실패: {e}")
        
        # 2. Notion Calendar Tool
        try:
            self.notion_calendar_tool = CalendarTool(self.settings)
            self.tools_status["notion_calendar"] = "✅ 연결됨"
            logger.info("✅ Notion Calendar 도구 초기화 완료")
        except Exception as e:
            self.tools_status["notion_calendar"] = f"❌ 실패: {str(e)}"
            logger.error(f"❌ Notion Calendar 도구 초기화 실패: {e}")
        
        # 3. Calculator Tool
        try:
            self.calculator_tool = CalculatorTool()
            self.tools_status["calculator"] = "✅ 연결됨"
            logger.info("✅ Calculator 도구 초기화 완료")
        except Exception as e:
            self.tools_status["calculator"] = f"❌ 실패: {str(e)}"
            logger.error(f"❌ Calculator 도구 초기화 실패: {e}")
        
        # 4. Echo Tool
        try:
            self.echo_tool = EchoTool()
            self.tools_status["echo"] = "✅ 연결됨"
            logger.info("✅ Echo 도구 초기화 완료")
        except Exception as e:
            self.tools_status["echo"] = f"❌ 실패: {str(e)}"
            logger.error(f"❌ Echo 도구 초기화 실패: {e}")
        
        # 5. Web Scraper Tool (일시적으로 비활성화)
        # try:
        #     self.web_scraper_tool = WebScraperTool()
        #     self.tools_status["web_scraper"] = "✅ 연결됨"
        #     logger.info("✅ Web Scraper 도구 초기화 완료")
        # except Exception as e:
        #     self.tools_status["web_scraper"] = f"❌ 실패: {str(e)}"
        #     logger.error(f"❌ Web Scraper 도구 초기화 실패: {e}")
        self.tools_status["web_scraper"] = "⚠️ 일시적으로 비활성화됨"
        logger.warning("⚠️ Web Scraper 도구는 일시적으로 비활성화되었습니다.")
        
        # 6. Apple Tools (macOS 전용)
        if APPLE_TOOLS_AVAILABLE:
            # Apple Auto Responder
            try:
                self.apple_auto_responder = IntelligentAutoResponder()
                self.tools_status["apple_auto_responder"] = "✅ 연결됨"
                logger.info("✅ Apple Auto Responder 도구 초기화 완료")
            except Exception as e:
                self.tools_status["apple_auto_responder"] = f"❌ 실패: {str(e)}"
                logger.error(f"❌ Apple Auto Responder 도구 초기화 실패: {e}")
            
            # Apple Notification Monitor
            try:
                self.apple_notification_monitor = MacOSNotificationMonitor()
                self.tools_status["apple_notification_monitor"] = "✅ 연결됨"
                logger.info("✅ Apple Notification Monitor 도구 초기화 완료")
            except Exception as e:
                self.tools_status["apple_notification_monitor"] = f"❌ 실패: {str(e)}"
                logger.error(f"❌ Apple Notification Monitor 도구 초기화 실패: {e}")
            
            # Apple Notes Tool
            try:
                from src.tools.apple.notes_tool import AppleNotesTool
                self.apple_notes_tool = AppleNotesTool()
                self.tools_status["apple_notes"] = "✅ 연결됨"
                logger.info("✅ Apple Notes 도구 초기화 완료")
            except Exception as e:
                self.tools_status["apple_notes"] = f"❌ 실패: {str(e)}"
                logger.error(f"❌ Apple Notes 도구 초기화 실패: {e}")
        else:
            self.tools_status["apple_auto_responder"] = "⚠️ macOS 전용"
            self.tools_status["apple_notification_monitor"] = "⚠️ macOS 전용"
            self.tools_status["apple_notes"] = "⚠️ macOS 전용"

    def _report_tools_status(self):
        """MCP 도구들 연결 상태 보고"""
        logger.info("📋 MCP 도구 연결 상태 보고:")
        connected_count = 0
        total_tools = len(self.tools_status)
        
        for tool_name, status in self.tools_status.items():
            logger.info(f"   {tool_name}: {status}")
            if "✅" in status:
                connected_count += 1
        
        logger.info(f"🔗 총 {connected_count}/{total_tools}개 도구 연결됨")
        
        if connected_count == 0:
            logger.error("❌ 연결된 MCP 도구가 없습니다!")
        elif connected_count < total_tools:
            logger.warning(f"⚠️ 일부 도구만 연결됨 ({connected_count}/{total_tools})")
        else:
            logger.info("🎉 모든 MCP 도구가 성공적으로 연결되었습니다!")
    
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
        tool_result = await self._check_and_execute_tools(user_message)
        
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
            # 도구 실행 결과가 있으면 도구 결과만 반환 (AI 응답 생략)
            if tool_result:
                return AIResponse(
                    content=tool_result,
                    confidence=0.95,
                    reasoning="도구 실행 완료",
                    metadata={
                        "original_message": user_message,
                        "processed_at": datetime.now().isoformat(),
                        "tool_executed": True,
                        "tools_used": ["mcp_tool"]
                    }
                )
            
            # 도구 실행이 없었던 경우에만 AI 응답 생성
            messages = self._build_prompt(user_message, user_id)
            ai_response = await self.llm_provider.generate_response(messages)
            
            return AIResponse(
                content=ai_response.content,
                confidence=0.8,
                reasoning="AI 자연어 처리",
                metadata={
                    "original_message": user_message,
                    "processed_at": datetime.now().isoformat(),
                    "model": "gemini-2.5-pro",
                    "tools_used": []
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
    
    async def _check_and_execute_tools(self, user_message: str) -> Optional[str]:
        """에이전틱 AI 기반 도구 선택 및 실행"""
        
        # 도구 상태 확인 명령어는 즉시 처리
        message_lower = user_message.lower()
        if any(keyword in message_lower for keyword in ["도구상태", "tool status", "도구확인", "연결상태"]):
            return self._get_tools_status_report()
        
        # 에이전틱 AI 방식: LLM이 직접 자연어를 이해하고 도구 선택
        if not self.llm_provider:
            return "❌ AI 엔진이 초기화되지 않아 도구 선택이 불가능합니다."
        
        try:
            # AI가 자연어를 분석하고 적절한 도구와 액션을 결정
            tool_decision = await self._make_agentic_tool_decision(user_message)
            
            if not tool_decision:
                return None  # AI가 도구 사용이 불필요하다고 판단
            
            # AI가 선택한 도구 실행
            return await self._execute_selected_tool(tool_decision, user_message)
            
        except Exception as e:
            logger.error(f"에이전틱 도구 선택 중 오류: {e}")
            return f"❌ AI 도구 선택 중 오류가 발생했습니다: {e}"

    async def _make_agentic_tool_decision(self, user_message: str) -> Optional[Dict[str, Any]]:
        """AI가 자연어를 분석하여 도구 선택을 결정"""
        
        # LLM provider가 초기화되지 않은 경우 처리
        if not self.llm_provider:
            logger.warning("LLM provider가 없어 간단한 키워드 매칭으로 폴백")
            return self._fallback_tool_decision(user_message)
        
        # 사용 가능한 도구 목록 생성
        available_tools = self._get_available_tools_info()
        
        # AI에게 도구 선택을 요청하는 프롬프트
        tool_selection_prompt = f"""
당신은 지능형 개인 비서입니다. 사용자의 자연어 요청을 분석하여 적절한 도구를 선택하고 실행해야 합니다.

**사용자 요청**: "{user_message}"

**사용 가능한 도구들**:
{available_tools}

**에이전틱 분석 지침**:
1. 사용자의 의도를 정확히 파악하세요
2. 요청을 완수하는데 필요한 도구가 있는지 판단하세요
3. 도구가 필요하다면 가장 적절한 도구와 액션을 선택하세요
4. 도구가 불필요하다면 null을 반환하세요

**응답 형식 (JSON)**:
도구가 필요한 경우:
{{
    "tool_needed": true,
    "selected_tool": "도구명",
    "action": "액션명",
    "reasoning": "선택 이유",
    "confidence": 0.95
}}

도구가 불필요한 경우:
{{
    "tool_needed": false,
    "reasoning": "도구가 필요하지 않은 이유"
}}

응답:"""

        try:
            messages = [
                ChatMessage(role="system", content="당신은 에이전틱 AI 개인비서입니다. 자연어 요청을 분석하여 적절한 도구를 선택합니다."),
                ChatMessage(role="user", content=tool_selection_prompt)
            ]
            
            # LLM provider가 있는 경우에만 호출
            if hasattr(self.llm_provider, 'generate_response'):
                ai_response = await self.llm_provider.generate_response(messages)
            else:
                logger.warning("LLM provider에 generate_response 메서드가 없음")
                return self._fallback_tool_decision(user_message)
            
            # JSON 응답 파싱
            import json
            import re
            
            # JSON 부분만 추출
            json_match = re.search(r'\{.*\}', ai_response.content, re.DOTALL)
            if json_match:
                decision_json = json_match.group()
                decision = json.loads(decision_json)
                
                logger.info(f"AI 도구 선택 결정: {decision}")
                
                if decision.get("tool_needed", False):
                    return decision
                else:
                    logger.info(f"AI가 도구 사용 불필요로 판단: {decision.get('reasoning', '')}")
                    return None
            else:
                logger.warning("AI 응답에서 JSON을 찾을 수 없습니다")
                return self._fallback_tool_decision(user_message)
                
        except Exception as e:
            logger.error(f"AI 도구 선택 결정 중 오류: {e}")
            return self._fallback_tool_decision(user_message)

    def _fallback_tool_decision(self, user_message: str) -> Optional[Dict[str, Any]]:
        """LLM이 사용 불가능할 때 기본 키워드 매칭으로 폴백"""
        message_lower = user_message.lower()
        
        # Apple Notes 관련 키워드를 먼저 체크
        if any(keyword in message_lower for keyword in ["애플메모", "apple notes", "애플 메모", "메모장에"]):
            return {
                "tool_needed": True,
                "selected_tool": "apple_notes",
                "action": "create",
                "reasoning": "키워드 매칭 - Apple Notes 메모 요청",
                "confidence": 0.8
            }
        # Notion Todo 관련 키워드
        elif any(keyword in message_lower for keyword in ["메모", "할일", "todo", "기록", "저장", "추가", "남겨"]):
            return {
                "tool_needed": True,
                "selected_tool": "notion_todo",
                "action": "create",
                "reasoning": "키워드 매칭 - 메모/할일 관련 요청",
                "confidence": 0.7
            }
        elif any(keyword in message_lower for keyword in ["계산", "+", "-", "*", "/", "더하기", "빼기", "곱하기", "나누기"]):
            return {
                "tool_needed": True,
                "selected_tool": "calculator",
                "action": "calculate",
                "reasoning": "키워드 매칭 - 계산 관련 요청",
                "confidence": 0.7
            }
        elif any(keyword in message_lower for keyword in ["echo", "반복", "따라해"]):
            return {
                "tool_needed": True,
                "selected_tool": "echo",
                "action": "echo",
                "reasoning": "키워드 매칭 - 에코 요청",
                "confidence": 0.7
            }
        
        return None

    def _get_available_tools_info(self) -> str:
        """사용 가능한 도구들의 정보를 AI가 이해할 수 있는 형태로 반환"""
        tools_info = []
        
        if self.notion_todo_tool:
            tools_info.append("""
1. **notion_todo** - Notion 할일 관리
   - 액션: create (할일 생성), list (할일 목록), update (수정), delete (삭제)
   - 용도: 할일, 작업, 리스트, 태스크 관련 요청시 사용
   - 예시: "할일 추가해줘", "작업 목록 확인", "태스크 생성"
""")
        
        if hasattr(self, 'apple_notes_tool') and self.apple_notes_tool:
            tools_info.append("""
2. **apple_notes** - Apple Notes 메모장
   - 액션: create (메모 생성), search (검색), update (수정), delete (삭제)
   - 용도: 애플 메모장, Apple Notes, 메모, 기록, 저장 요청시 사용
   - 예시: "애플메모장에 적어줘", "Apple Notes에 메모", "메모 저장해줘"
""")
        
        if self.notion_calendar_tool:
            tools_info.append("""
3. **notion_calendar** - Notion 캘린더 관리  
   - 액션: create (일정 생성), list (일정 목록), update (수정), delete (삭제)
   - 용도: 일정, 약속, 미팅, 회의 관련 요청시 사용
   - 예시: "내일 오후 3시 회의 일정 추가", "이번 주 일정 확인"
""")
        
        if self.calculator_tool:
            tools_info.append("""
4. **calculator** - 계산기
   - 액션: calculate (계산 실행)
   - 용도: 수학 계산, 연산 요청시 사용
   - 예시: "5 + 3 계산해줘", "100 나누기 4"
""")
        
        if self.echo_tool:
            tools_info.append("""
5. **echo** - 에코/반복
   - 액션: echo (메시지 반복)
   - 용도: 테스트, 확인, 반복 요청시 사용
   - 예시: "안녕하세요 따라해", "echo test"
""")
        
        return "\n".join(tools_info) if tools_info else "현재 사용 가능한 도구가 없습니다."

    async def _execute_selected_tool(self, tool_decision: Dict[str, Any], user_message: str) -> str:
        """AI가 선택한 도구를 실행"""
        selected_tool = tool_decision.get("selected_tool")
        action = tool_decision.get("action")
        reasoning = tool_decision.get("reasoning", "")
        confidence = tool_decision.get("confidence", 0.0)
        
        logger.info(f"에이전틱 도구 실행: {selected_tool} - {action} (신뢰도: {confidence})")
        logger.info(f"선택 이유: {reasoning}")
        
        try:
            if selected_tool == "notion_todo":
                return await self._execute_notion_todo(user_message)
            elif selected_tool == "apple_notes":
                return await self._execute_apple_notes(user_message)
            elif selected_tool == "notion_calendar":
                return await self._execute_notion_calendar(user_message)
            elif selected_tool == "calculator":
                return await self._execute_calculator(user_message)
            elif selected_tool == "echo":
                return await self._execute_echo(user_message)
            elif selected_tool == "web_scraper":
                return await self._execute_web_scraper()
            else:
                return f"❌ 알 수 없는 도구: {selected_tool}"
                
        except Exception as e:
            logger.error(f"도구 실행 중 오류: {e}")
            return f"❌ {selected_tool} 도구 실행 중 오류: {e}"

    def _get_tools_status_report(self) -> str:
        """MCP 도구 연결 상태 보고서 생성"""
        if not hasattr(self, 'tools_status') or not self.tools_status:
            # 도구가 아직 초기화되지 않았다면 초기화
            self._initialize_mcp_tools()
        
        status_lines = ["🔧 **MCP 도구 연결 상태**\n"]
        connected_count = 0
        total_tools = len(self.tools_status)
        
        for tool_name, status in self.tools_status.items():
            tool_display_name = {
                "notion_todo": "📝 Notion Todo",
                "notion_calendar": "📅 Notion Calendar", 
                "calculator": "🔢 Calculator",
                "echo": "🔊 Echo Tool",
                "web_scraper": "🌐 Web Scraper",
                "apple_auto_responder": "🍎 Apple Auto Responder",
                "apple_notification_monitor": "📱 Apple Notification Monitor"
            }.get(tool_name, tool_name)
            
            status_lines.append(f"{tool_display_name}: {status}")
            if "✅" in status:
                connected_count += 1
        
        status_lines.append(f"\n📊 **총 {connected_count}/{total_tools}개 도구 연결됨**")
        
        if connected_count == 0:
            status_lines.append("❌ 연결된 MCP 도구가 없습니다!")
        elif connected_count < total_tools:
            status_lines.append(f"⚠️ 일부 도구만 연결됨")
        else:
            status_lines.append("🎉 모든 MCP 도구가 정상 연결됨!")
        
        return "\n".join(status_lines)

    async def _execute_notion_todo(self, user_message: str) -> str:
        """실제 Notion Todo 도구 실행"""
        try:
            if not self.notion_todo_tool:
                return "❌ Notion Todo 도구가 연결되지 않았습니다."
            
            memo_content = self._extract_memo_content(user_message)
            
            # 실제 Notion API 호출
            logger.info(f"Notion Todo 도구 실행: {memo_content}")
            
            # TodoTool의 execute 메서드 호출 - 올바른 파라미터 형식
            parameters = {
                "action": "create",
                "title": memo_content,
                "description": f"Discord에서 추가됨: {user_message}"
            }
            result = await self.notion_todo_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                return f"✅ Notion에 할일을 추가했습니다: {memo_content}"
            else:
                return f"❌ Notion 할일 추가 실패: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Notion Todo 도구 실행 실패: {e}")
            return f"❌ Notion 할일 추가 실패: {str(e)}"

    async def _execute_apple_notes(self, user_message: str) -> str:
        """실제 Apple Notes 도구 실행"""
        try:
            if not hasattr(self, 'apple_notes_tool') or not self.apple_notes_tool:
                return "❌ Apple Notes 도구가 연결되지 않았습니다."
            
            memo_content = self._extract_memo_content(user_message)
            
            # 실제 Apple Notes 도구 호출
            logger.info(f"Apple Notes 도구 실행: {memo_content}")
            
            # AppleNotesTool의 execute 메서드 호출
            parameters = {
                "action": "create",
                "title": memo_content[:30] if len(memo_content) > 30 else memo_content,  # 제목은 30자 제한
                "content": memo_content,
                "folder": "Notes"
            }
            result = await self.apple_notes_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                return f"✅ Apple Notes에 메모를 추가했습니다: {memo_content}"
            else:
                return f"❌ Apple Notes 메모 추가 실패: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Apple Notes 도구 실행 실패: {e}")
            return f"❌ Apple Notes 메모 추가 실패: {str(e)}"

    async def _execute_notion_calendar(self, user_message: str) -> str:
        """실제 Notion Calendar 도구 실행"""
        try:
            if not self.notion_calendar_tool:
                return "❌ Notion Calendar 도구가 연결되지 않았습니다."
            
            # 일정 내용 추출
            schedule_content = self._extract_schedule_content(user_message)
            
            # 실제 Notion Calendar API 호출
            logger.info(f"Notion Calendar 도구 실행: {schedule_content}")
            
            # CalendarTool의 execute 메서드 호출
            parameters = {
                "action": "create",
                "title": schedule_content.get("title", "새 일정"),
                "date": schedule_content.get("date"),
                "time": schedule_content.get("time"),
                "description": f"Discord에서 추가됨: {user_message}"
            }
            result = await self.notion_calendar_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                return f"📅 Notion에 일정을 추가했습니다: {schedule_content.get('title', '새 일정')}"
            else:
                return f"❌ Notion 일정 추가 실패: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Notion Calendar 도구 실행 실패: {e}")
            return f"❌ Notion 일정 추가 실패: {str(e)}"

    async def _execute_calculator(self, user_message: str) -> str:
        """실제 Calculator 도구 실행"""
        try:
            if not self.calculator_tool:
                return "❌ Calculator 도구가 연결되지 않았습니다."
            
            calculation = self._extract_calculation(user_message)
            
            # 실제 Calculator 도구 호출 - 계산식 파싱
            logger.info(f"Calculator 도구 실행: {calculation}")
            
            # 간단한 계산식 파싱
            import re
            
            # 더하기 패턴
            add_match = re.search(r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)', calculation)
            if add_match:
                parameters = {
                    "operation": "+",
                    "a": float(add_match.group(1)),
                    "b": float(add_match.group(2))
                }
                result = await self.calculator_tool.execute(parameters)
                if result.status == ExecutionStatus.SUCCESS:
                    return f"🔢 계산 결과: {calculation} = {result.data}"
                    
            # 빼기 패턴
            sub_match = re.search(r'(\d+(?:\.\d+)?)\s*\-\s*(\d+(?:\.\d+)?)', calculation)
            if sub_match:
                parameters = {
                    "operation": "-",
                    "a": float(sub_match.group(1)),
                    "b": float(sub_match.group(2))
                }
                result = await self.calculator_tool.execute(parameters)
                if result.status == ExecutionStatus.SUCCESS:
                    return f"🔢 계산 결과: {calculation} = {result.data}"
                    
            # 곱하기 패턴
            mul_match = re.search(r'(\d+(?:\.\d+)?)\s*[\*×]\s*(\d+(?:\.\d+)?)', calculation)
            if mul_match:
                parameters = {
                    "operation": "*",
                    "a": float(mul_match.group(1)),
                    "b": float(mul_match.group(2))
                }
                result = await self.calculator_tool.execute(parameters)
                if result.status == ExecutionStatus.SUCCESS:
                    return f"🔢 계산 결과: {calculation} = {result.data}"
                    
            # 나누기 패턴
            div_match = re.search(r'(\d+(?:\.\d+)?)\s*[\/÷]\s*(\d+(?:\.\d+)?)', calculation)
            if div_match:
                parameters = {
                    "operation": "/",
                    "a": float(div_match.group(1)),
                    "b": float(div_match.group(2))
                }
                result = await self.calculator_tool.execute(parameters)
                if result.status == ExecutionStatus.SUCCESS:
                    return f"🔢 계산 결과: {calculation} = {result.data}"
            
            # 계산식을 인식하지 못한 경우 폴백
            try:
                if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', calculation):
                    result = eval(calculation)
                    return f"🔢 계산 결과: {calculation} = {result}"
                else:
                    return f"❌ 계산식을 인식할 수 없습니다: {calculation}"
            except:
                return f"❌ 계산 실행 실패: 올바른 계산식을 입력해주세요"
            
        except Exception as e:
            logger.error(f"Calculator 도구 실행 실패: {e}")
            return f"❌ 계산 실행 실패: {str(e)}"

    async def _execute_web_scraper(self) -> str:
        """실제 Web Scraper 도구 실행 (일시적으로 비활성화)"""
        return "⚠️ Web Scraper 도구는 일시적으로 비활성화되었습니다."

    async def _execute_echo(self, user_message: str) -> str:
        """실제 Echo 도구 실행"""
        try:
            if not self.echo_tool:
                return "❌ Echo 도구가 연결되지 않았습니다."
            
            # 실제 Echo 도구 호출
            logger.info(f"Echo 도구 실행: {user_message}")
            
            parameters = {"message": user_message}
            result = await self.echo_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                return f"🔊 Echo: {result.data}"
            else:
                return f"❌ Echo 오류: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Echo 도구 실행 실패: {e}")
            return f"🔊 Echo: {user_message}"
    
    def _extract_memo_content(self, message: str) -> str:
        """메시지에서 메모 내용 추출"""
        import re
        
        # 사과 관련 패턴 개선
        apple_pattern = r'사과\s*(\d+)\s*개'
        apple_match = re.search(apple_pattern, message)
        if apple_match:
            count = apple_match.group(1)
            return f"사과 {count}개 구매"
        
        # 애플메모장, Apple Notes 관련 키워드 제거
        cleaned_message = message
        remove_words = [
            "애플메모장에", "애플 메모장에", "apple notes에", "애플메모", 
            "메모장에", "적어줘", "적어줄래", "저장해줘", "기록해줘", 
            "남겨줘", "추가해줘", "써줘", "라고", "하라고", "사라고"
        ]
        
        for word in remove_words:
            cleaned_message = cleaned_message.replace(word, " ")
        
        # 연속된 공백 제거
        cleaned_message = re.sub(r'\s+', ' ', cleaned_message).strip()
        
        # 빈 문자열이면 원본 메시지의 일부 반환
        if not cleaned_message:
            return message[:50] if len(message) > 50 else message
        
        return cleaned_message[:100] if len(cleaned_message) > 100 else cleaned_message

    def _extract_schedule_content(self, message: str) -> Dict[str, Any]:
        """메시지에서 일정 내용 추출"""
        import re
        from datetime import datetime, timedelta
        
        # 기본값
        schedule_info = {
            "title": "새 일정",
            "date": None,
            "time": None
        }
        
        # 시간 패턴 추출 (예: "오후 3시", "15:00", "3시")
        time_patterns = [
            r'오후\s*(\d{1,2})시',  # 오후 3시
            r'오전\s*(\d{1,2})시',  # 오전 9시
            r'(\d{1,2}):(\d{2})',   # 15:00
            r'(\d{1,2})시',         # 3시
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, message)
            if match:
                if "오후" in pattern and match.group(1):
                    hour = int(match.group(1))
                    if hour != 12:
                        hour += 12
                    schedule_info["time"] = f"{hour:02d}:00"
                elif "오전" in pattern and match.group(1):
                    hour = int(match.group(1))
                    schedule_info["time"] = f"{hour:02d}:00"
                elif ":" in pattern:
                    schedule_info["time"] = f"{match.group(1):0>2}:{match.group(2)}"
                else:
                    hour = int(match.group(1))
                    schedule_info["time"] = f"{hour:02d}:00"
                break
        
        # 날짜 패턴 추출 (예: "내일", "오늘", "다음주")
        today = datetime.now().date()
        if "내일" in message:
            schedule_info["date"] = (today + timedelta(days=1)).isoformat()
        elif "오늘" in message:
            schedule_info["date"] = today.isoformat()
        elif "다음주" in message:
            schedule_info["date"] = (today + timedelta(days=7)).isoformat()
        else:
            schedule_info["date"] = today.isoformat()
        
        # 일정 제목 추출
        title_keywords = ["회의", "미팅", "약속", "일정", "만남"]
        for keyword in title_keywords:
            if keyword in message:
                # 키워드 주변 텍스트를 제목으로 사용
                parts = message.split(keyword)
                if len(parts) > 1:
                    title_part = parts[0].strip()
                    if title_part:
                        schedule_info["title"] = title_part + " " + keyword
                    else:
                        schedule_info["title"] = keyword
                break
        else:
            # 키워드가 없으면 메시지 전체를 제목으로
            clean_title = message
            for word in ["일정", "추가", "해줘", "만들어", "줘"]:
                clean_title = clean_title.replace(word, "").strip()
            if clean_title:
                schedule_info["title"] = clean_title
        
        return schedule_info
    
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
