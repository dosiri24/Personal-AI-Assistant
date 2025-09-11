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
from ..ai_engine.prompt_templates import PromptManager
from ..mcp.mcp_integration import MCPIntegration
from ..config import Settings

# MCP 도구 import
from ..mcp.base_tool import ExecutionStatus
from ..tools.notion.todo_tool import TodoTool
from ..tools.notion.calendar_tool import CalendarTool
from ..tools.calculator_tool import CalculatorTool
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
        # DiscordBot의 SessionManager를 주입하여 대화 컨텍스트를 활용 (선택적)
        # 주입되지 않은 경우에도 안전하게 동작하도록 None으로 초기화
        self.session_manager = None  # type: ignore[assignment]
        
        # MCP 도구들
        self.notion_todo_tool: Optional[TodoTool] = None
        self.notion_calendar_tool: Optional[CalendarTool] = None
        self.calculator_tool: Optional[CalculatorTool] = None
        # echo 도구 제거 (에이전틱 일반 응답으로 대체)
        # self.web_scraper_tool: Optional[WebScraperTool] = None  # 일시적으로 비활성화
        self.apple_auto_responder: Optional[Any] = None
        self.apple_notification_monitor: Optional[Any] = None
        
        # 도구 연결 상태
        self.tools_status = {}
        
        self._initialize_ai_engine()
        self._initialize_mcp_tools()
        self._report_tools_status()
        
        # MCP 통합 (에이전틱 LLM이 도구 선택/실행)
        self._mcp: Optional[MCPIntegration] = None
        
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
        
        # 4. Echo Tool 제거됨
        
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
        """사용자 메시지 처리: LLM이 도구 선택/실행(MCP)까지 담당"""
        try:
            # MCP 통합 초기화 (한 번만)
            await self._ensure_mcp()
            # 최근 대화 10개를 컨텍스트로 전달 (user/assistant 순서 유지)
            history: List[Dict[str, Any]] = []
            try:
                int_user_id = int(user_id)
            except Exception:
                int_user_id = None
            # 세션 매니저가 주입된 경우에만 안전하게 컨텍스트 조회
            if int_user_id is not None and getattr(self, "session_manager", None):
                try:
                    turns = await self.session_manager.get_conversation_context(int_user_id, turns_limit=10)  # type: ignore[attr-defined]
                    # 최근순 → 시간순으로 뒤집어서 추가
                    for t in reversed(turns):
                        if t.user_message:
                            history.append({"role": "user", "content": t.user_message})
                        if t.bot_response:
                            history.append({"role": "assistant", "content": t.bot_response})
                except Exception as _e:
                    # 컨텍스트 조회 실패는 무시하고 계속 진행 (MCP에는 문제 없음)
                    pass

            # 최근 Notion Todo 컨텍스트를 LLM이 활용할 수 있도록 대화 히스토리에 주입 (KST due_date 포함)
            try:
                if int_user_id is not None and getattr(self, "session_manager", None):
                    sess = self.session_manager.active_sessions.get(int_user_id)  # type: ignore[attr-defined]
                    if sess and isinstance(sess.context, dict):
                        last_todo = sess.context.get("last_notion_todo")
                        if isinstance(last_todo, dict):
                            lt_title = last_todo.get("title")
                            lt_id = last_todo.get("todo_id")
                            lt_due = last_todo.get("due_date")
                            ctx_text = f"[context] last_notion_todo: title={lt_title}, todo_id={lt_id}, due_date={lt_due} (KST)"
                            history.append({"role": "assistant", "content": ctx_text})
            except Exception:
                pass

            detailed = await self._mcp.process_user_request_detailed(
                user_message, user_id=user_id, conversation_history=history
            )
            content_text = detailed.get("text", "")
            exec_info = detailed.get("execution") or {}
            # 최근 메모 컨텍스트 가져오기 (저장만 사용)
            last_note_ctx = None
            try:
                if 'session' in locals() and hasattr(session, 'context'):
                    last_note_ctx = session.context.get('last_apple_note')
            except Exception:
                pass

            # 최근 Apple 노트 컨텍스트 저장(성공 시)
            try:
                if isinstance(exec_info, dict) and exec_info.get("status") == "success" and exec_info.get("tool_name") == "apple_notes":
                    params_used = exec_info.get("parameters") or {}
                    store_title = None
                    if isinstance(params_used, dict):
                        store_title = params_used.get("title") or params_used.get("target_title")
                    if not store_title and last_note_ctx:
                        store_title = last_note_ctx.get("title")
                    if store_title and self.session_manager and isinstance(int_user_id, int):
                        await self.session_manager.update_user_context(int_user_id, "last_apple_note", {"title": store_title, "folder": (params_used.get("folder") if isinstance(params_used, dict) else None) or "Notes"})
            except Exception:
                pass
            # 최근 Notion Todo 컨텍스트 저장(성공 시)
            try:
                if isinstance(exec_info, dict) and exec_info.get("status") == "success" and exec_info.get("tool_name") == "notion_todo":
                    params_used = exec_info.get("parameters") or {}
                    result_data = exec_info.get("result_data") or {}
                    title = None
                    todo_id = None
                    due_date = None
                    if isinstance(params_used, dict):
                        title = params_used.get("title") or params_used.get("target_title")
                        due_date = params_used.get("due_date")
                    if isinstance(result_data, dict):
                        todo_id = result_data.get("todo_id") or result_data.get("id")
                        if not title:
                            title = result_data.get("title")
                        if not due_date:
                            due_date = result_data.get("due_date")
                    if (title or todo_id) and self.session_manager and isinstance(int_user_id, int):
                        await self.session_manager.update_user_context(
                            int_user_id,
                            "last_notion_todo",
                            {"title": title, "todo_id": todo_id, "due_date": due_date}
                        )
            except Exception:
                pass
            system_notice = None
            logger.info("=== SYSTEM NOTICE 디버깅 시작 ===")
            logger.info(f"exec_info 타입: {type(exec_info)}")
            logger.info(f"exec_info 내용: {exec_info}")
            
            # MCP 도구 사용 알림: '성공'이며 실제 도구 호출이 있었던 경우에만 전송
            if exec_info and isinstance(exec_info, dict) and exec_info.get("status") == "success":
                logger.info("SUCCESS 조건 만족됨, system_notice 생성 시도")
                
                # 디버그: exec_info 내용 로깅
                logger.debug(f"System notice 생성 중: exec_info={exec_info}")
                
                total_calls = exec_info.get("total_tool_calls") or exec_info.get("total_calls") or 0
                success_calls = exec_info.get("successful_tool_calls") or exec_info.get("successful_calls") or 0
                tool = exec_info.get("tool_name")
                tools_used = exec_info.get("tools_used") or []
                
                logger.info(f"도구 정보: tool={tool}, tools_used={tools_used}, total_calls={total_calls}, success_calls={success_calls}")
                
                # 실제 사용된 도구들 목록 생성
                if isinstance(tools_used, (list, tuple)) and len(tools_used) > 0:
                    logger.info(f"tools_used 발견: {tools_used}")
                    # system_time 도구는 시스템 알림에서 제외 (사용자에게 불필요)
                    meaningful_tools = [t for t in tools_used if t != 'system_time']
                    
                    if meaningful_tools:
                        logger.info(f"meaningful_tools: {meaningful_tools}")
                        if len(meaningful_tools) == 1:
                            # 단일 도구 사용 시 더 정확한 action 정보 표시
                            tool_name = meaningful_tools[0]
                            # scratchpad_summary에서 실제 action 추출 시도
                            action = "실행"
                            try:
                                summary = exec_info.get("scratchpad_summary", "")
                                if "action" in str(summary).lower():
                                    # action 정보가 있으면 추출
                                    import re
                                    # notion_todo 사용이라는 표현에서 실제 action 추출
                                    if tool_name == "notion_todo":
                                        if "create" in summary.lower() or "추가" in summary or "생성" in summary:
                                            action = "create"
                                        elif "update" in summary.lower() or "수정" in summary or "변경" in summary:
                                            action = "update" 
                                        elif "delete" in summary.lower() or "삭제" in summary:
                                            action = "delete"
                                        elif "complete" in summary.lower() or "완료" in summary:
                                            action = "complete"
                                        elif "list" in summary.lower() or "조회" in summary or "목록" in summary:
                                            action = "list"
                            except Exception:
                                pass
                            
                            system_notice = f"시스템 안내: {tool_name} ({action}) 실행 완료"
                            logger.info(f"단일 도구 알림 생성: {system_notice}")
                        else:
                            # 여러 도구 사용 시 상세 알림 표시
                            tools_str = ", ".join(meaningful_tools)
                            system_notice = f"시스템 안내: {len(meaningful_tools)}개 도구 실행 완료 ({tools_str})"
                            logger.info(f"복수 도구 알림 생성: {system_notice}")
                    else:
                        logger.info("meaningful_tools가 비어있음 (모두 system_time)")
                        
                elif tool and tool != 'system_time':
                    logger.info(f"단일 tool 발견: {tool}")
                    # 단일 도구 사용인 경우
                    action = exec_info.get("action") or "execute"
                    system_notice = f"시스템 안내: {tool} ({action}) 실행 완료"
                    logger.info(f"단일 tool 알림 생성: {system_notice}")
                else:
                    logger.info(f"알림 생성 조건 불만족: tool={tool}, tools_used={tools_used}")
                
                # 최종 system_notice 결과 로깅
                logger.info(f"System notice 최종 결과: '{system_notice}'")
            else:
                logger.info(f"SUCCESS 조건 불만족: exec_info={bool(exec_info)}, is_dict={isinstance(exec_info, dict)}, status={exec_info.get('status') if isinstance(exec_info, dict) else 'N/A'}")
            
            logger.info("=== SYSTEM NOTICE 디버깅 종료 ===")

            meta = {
                "original_message": user_message,
                "processed_at": datetime.now().isoformat(),
                "via": "mcp_integration",
                "execution": exec_info,
            }
            resp = AIResponse(
                content=content_text,
                confidence=0.9,
                reasoning="agentic_mcp",
                metadata=meta,
            )
            # 동적으로 속성 추가: system_notice (호출측에서 사용)
            setattr(resp, "system_notice", system_notice)
            return resp
        except Exception as e:
            logger.error(f"MCP 처리 실패, 일반 LLM 응답 시도: {e}")
            # 일반 LLM 답변 (도구 미선택 등)
            try:
                if not self.llm_provider:
                    raise RuntimeError("LLM Provider not initialized")
                if not self.llm_provider.is_available():
                    ok = await self.llm_provider.initialize()
                    if not ok:
                        raise RuntimeError("LLM Provider initialize failed")
                messages = self._build_prompt(user_message, user_id)
                ai_response = await self.llm_provider.generate_response(messages)
                return AIResponse(content=ai_response.content, confidence=0.7)
            except Exception as e2:
                logger.error(f"일반 LLM 응답도 실패: {e2}")
                return AIResponse(content=f"❌ 처리 중 오류: {e}", confidence=0.0)
    
    def _build_prompt(self, user_message: str, user_id: str) -> List[ChatMessage]:
        """AI를 위한 프롬프트 구성"""
        system_prompt = (
            "당신은 Discord에서 사용자를 돕는 개인 비서 AI입니다.\n"
            "- 따뜻하고 친근한 톤으로 1~3문장 이내로 답하세요.\n"
            "- 과한 자기소개/홍보/기능 나열은 피하고, 바로 도움이 되는 답을 주세요.\n"
            "- 필요 시 간단한 후속 질문 하나만 덧붙이세요.\n"
            "- 도구 사용 언급은 최소화하고, 결과/다음 행동만 명확히 제시하세요.\n"
            "- 한국어로 자연스럽고 예의 있게 답하세요.\n"
            "- 중복/연속 답변 금지.\n"
            "- 당신의 이름은 '앙미니'입니다. 이름을 물으면 그렇게 소개하세요."
        )
        
        return [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_message)
        ]

    # 키워드 기반 파싱/후킹은 사용하지 않습니다 (에이전틱 LLM 판단에 위임)

    async def _ensure_mcp(self) -> None:
        if self._mcp is None:
            self._mcp = MCPIntegration()
            await self._mcp.initialize()
    
    # 키워드 기반 도구 상태 질의 제거 (에이전틱 판단/명령어 기반으로만 동작)

    async def _make_agentic_tool_decision(self, user_message: str) -> Optional[Dict[str, Any]]:
        """AI가 자연어를 분석하여 도구 선택을 결정"""
        
        # LLM provider가 초기화되지 않은 경우 처리 (키워드 폴백 제거)
        if not self.llm_provider:
            logger.warning("LLM provider 미가용: 도구 선택 생략")
            return None
        
        # 사용 가능한 도구 목록 생성
        available_tools = self._get_available_tools_info()

        # PromptManager 템플릿을 사용하여 프롬프트 생성
        pm = PromptManager()
        tool_selection_prompt = pm.render_template(
            "tool_selection",
            {
                "task_goal": user_message,
                "available_tools": available_tools,
                "context": "Discord"
            }
        )

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
            
            # JSON 응답 파싱 (템플릿 표준 또는 유사 형식 모두 허용)
            import json
            import re
            
            # JSON 부분만 추출
            json_match = re.search(r'\{.*\}', ai_response.content, re.DOTALL)
            if json_match:
                decision_json = json_match.group()
                decision = json.loads(decision_json)
                
                logger.info(f"AI 도구 선택 결정: {decision}")
                
                # 표준 형식
                if "tool_needed" in decision:
                    if decision.get("tool_needed", False):
                        return decision
                    logger.info(f"AI가 도구 사용 불필요로 판단: {decision.get('reasoning', '')}")
                    return None

                # 호환 형식(selected_tool만 존재) → 기본 변환
                if "selected_tool" in decision:
                    mapped = {
                        "tool_needed": True,
                        "selected_tool": decision.get("selected_tool"),
                        "action": decision.get("action")
                                  or (decision.get("parameters", {}) or {}).get("action")
                                  or "execute",
                        "reasoning": decision.get("reason")
                                    or decision.get("usage_plan")
                                    or decision.get("expected_result")
                                    or "",
                        "confidence": decision.get("confidence", 0.75),
                    }
                    return mapped
                
                logger.warning("AI 응답 JSON에서 필요한 키를 찾지 못했습니다")
                return self._fallback_tool_decision(user_message)
            else:
                logger.warning("AI 응답에서 JSON을 찾을 수 없습니다")
                return None
                
        except Exception as e:
            logger.error(f"AI 도구 선택 결정 중 오류: {e}")
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

        return "\n".join(tools_info) if tools_info else "현재 사용 가능한 도구가 없습니다."

    async def _execute_selected_tool(self, tool_decision: Dict[str, Any], user_message: str, int_user_id: Optional[int] = None) -> str:
        """AI가 선택한 도구를 실행"""
        selected_tool = tool_decision.get("selected_tool")
        action = tool_decision.get("action")
        reasoning = tool_decision.get("reasoning", "")
        confidence = tool_decision.get("confidence", 0.0)
        
        logger.info(f"에이전틱 도구 실행: {selected_tool} - {action} (신뢰도: {confidence})")
        logger.info(f"선택 이유: {reasoning}")
        
        try:
            if selected_tool == "notion_todo":
                return await self._execute_notion_todo(user_message, int_user_id)
            elif selected_tool == "apple_notes":
                return await self._execute_apple_notes(user_message)
            elif selected_tool == "notion_calendar":
                return await self._execute_notion_calendar(user_message)
            elif selected_tool == "calculator":
                return await self._execute_calculator(user_message)
            
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

    async def _execute_notion_todo(self, user_message: str, int_user_id: Optional[int] = None) -> str:
        """실제 Notion Todo 도구 실행"""
        try:
            if not self.notion_todo_tool:
                return "❌ Notion Todo 도구가 연결되지 않았습니다."
            
            # 자연어 → Todo 파라미터 변환 (LLM 에이전틱)
            parameters = await self._agentic_parameters(user_message, "notion_todo")
            # 설명이 없을 경우, 원문을 출처로 남김
            if "description" not in parameters:
                parameters["description"] = f"Discord에서 추가됨: {user_message}"

            # 업데이트 시 최근 컨텍스트의 todo_id 보강 (도구 내부 폴백 제거에 따른 보강)
            try:
                action = str(parameters.get("action", "")).lower()
                if action == "update" and "todo_id" not in parameters and self.session_manager and isinstance(int_user_id, int):
                    session = self.session_manager.active_sessions.get(int_user_id)  # type: ignore[attr-defined]
                    if session and isinstance(session.context, dict):
                        last_todo = session.context.get("last_notion_todo")
                        if isinstance(last_todo, dict):
                            todo_id = last_todo.get("todo_id")
                            if todo_id:
                                parameters["todo_id"] = todo_id
            except Exception:
                pass

            logger.info(f"Notion Todo 도구 실행 파라미터: {parameters}")
            result = await self.notion_todo_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                d = result.data or {}
                title = d.get("title") or parameters.get("title")
                due = parameters.get("due_date")
                due_text = f" (마감: {due})" if due else ""
                return f"✅ Notion에 할일을 추가했습니다: {title}{due_text}"
            else:
                return f"❌ Notion 할일 추가 실패: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Notion Todo 도구 실행 실패: {e}")
            return f"❌ Notion 할일 추가 실패: {str(e)}"

    async def _execute_apple_notes(self, user_message: str) -> str:
        """실제 Apple Notes 도구 실행 (LLM 에이전틱 파라미터)"""
        try:
            if not hasattr(self, 'apple_notes_tool') or not self.apple_notes_tool:
                return "❌ Apple Notes 도구가 연결되지 않았습니다."

            # LLM으로 자연어 → 파라미터 변환
            parameters = await self._agentic_parameters(user_message, "apple_notes")
            if "action" not in parameters:
                parameters["action"] = "create"
            if parameters.get("action") == "create" and "title" not in parameters:
                parameters["title"] = (user_message or "메모")[:30]

            result = await self.apple_notes_tool.execute(parameters)

            if result.status == ExecutionStatus.SUCCESS:
                title = parameters.get("title") or parameters.get("target_title") or "메모"
                return f"📝 Apple 메모에 저장했습니다: {title}"
            else:
                return f"❌ Apple 메모 처리 실패: {result.error_message}"

        except Exception as e:
            logger.error(f"Apple Notes 도구 실행 실패: {e}")
            return f"❌ Apple 메모 처리 실패: {str(e)}"

    async def _execute_notion_calendar(self, user_message: str) -> str:
        """실제 Notion Calendar 도구 실행"""
        try:
            if not self.notion_calendar_tool:
                return "❌ Notion Calendar 도구가 연결되지 않았습니다."
            
            # LLM 에이전틱으로 캘린더 파라미터 생성
            parameters = await self._agentic_parameters(user_message, "notion_calendar")
            if "description" not in parameters:
                parameters["description"] = f"Discord에서 추가됨: {user_message}"
            result = await self.notion_calendar_tool.execute(parameters)
            
            if result.status == ExecutionStatus.SUCCESS:
                title = parameters.get("title") or "새 일정"
                return f"📅 Notion에 일정을 추가했습니다: {title}"
            else:
                return f"❌ Notion 일정 추가 실패: {result.error_message}"
            
        except Exception as e:
            logger.error(f"Notion Calendar 도구 실행 실패: {e}")
            return f"❌ Notion 일정 추가 실패: {str(e)}"

    async def _agentic_parameters(self, natural_command: str, tool_name: str) -> Dict[str, Any]:
        """LLM 기반으로 자연어를 도구 파라미터로 변환"""
        if not self.llm_provider:
            raise RuntimeError("LLM Provider가 초기화되지 않았습니다")
        if not self.llm_provider.is_available():
            ok = await self.llm_provider.initialize()
            if not ok:
                raise RuntimeError("LLM Provider 초기화 실패")
        # 의존성 import 지연
        from ..ai_engine.decision_engine import AgenticDecisionEngine
        from ..ai_engine.prompt_templates import PromptManager
        engine = AgenticDecisionEngine(self.llm_provider, PromptManager())
        return await engine.parse_natural_command(natural_command, tool_name)

    async def _execute_calculator(self, user_message: str) -> str:
        """실제 Calculator 도구 실행 (LLM 우선, 최소 폴백)"""
        try:
            if not self.calculator_tool:
                return "❌ Calculator 도구가 연결되지 않았습니다."
            
            # 1) LLM 에이전틱 파라미터 생성 시도
            try:
                params = await self._agentic_parameters(user_message, "calculator")
                result = await self.calculator_tool.execute(params)
                if result.status == ExecutionStatus.SUCCESS:
                    return f"🔢 계산 결과: {params.get('a')} {params.get('operation')} {params.get('b')} = {result.data}"
            except Exception:
                pass

            # 2) 최소 폴백: 단순 정규식 매칭
            import re
            calculation = self._extract_calculation(user_message)
            patterns = [
                (r'(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)', '+'),
                (r'(\d+(?:\.\d+)?)\s*\-\s*(\d+(?:\.\d+)?)', '-'),
                (r'(\d+(?:\.\d+)?)\s*[\*×]\s*(\d+(?:\.\d+)?)', '*'),
                (r'(\d+(?:\.\d+)?)\s*[\/÷]\s*(\d+(?:\.\d+)?)', '/'),
            ]
            for pat, op in patterns:
                m = re.search(pat, calculation)
                if m:
                    p = {"operation": op, "a": float(m.group(1)), "b": float(m.group(2))}
                    result = await self.calculator_tool.execute(p)
                    if result.status == ExecutionStatus.SUCCESS:
                        return f"🔢 계산 결과: {calculation} = {result.data}"
                    break
            return "❌ 계산식을 인식할 수 없습니다"
            
        except Exception as e:
            logger.error(f"Calculator 도구 실행 실패: {e}")
            return f"❌ 계산 실행 실패: {str(e)}"

    async def _execute_web_scraper(self) -> str:
        """실제 Web Scraper 도구 실행 (일시적으로 비활성화)"""
        return "⚠️ Web Scraper 도구는 일시적으로 비활성화되었습니다."

    # echo 도구 제거: 따라하기는 일반 LLM 응답으로 처리
    
    # 키워드 기반 전처리/추출 로직 제거 (LLM 기반 파라미터 생성 사용)
    
    def _extract_calculation(self, message: str) -> str:
        """메시지에서 계산식 추출"""
        import re
        
        calc_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        match = re.search(calc_pattern, message)
        
        if match:
            return f"{match.group(1)}{match.group(2)}{match.group(3)}"
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
