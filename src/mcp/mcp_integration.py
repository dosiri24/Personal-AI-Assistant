"""
MCP 시스템 통합 모듈

AI 엔진과 MCP 도구들을 통합하여 실제 작업을 수행할 수 있도록 하는 모듈입니다.
"""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..ai_engine.llm_provider import GeminiProvider, MockLLMProvider, ChatMessage
from ..ai_engine.decision_engine import AgenticDecisionEngine, DecisionContext
from ..ai_engine.prompt_templates import PromptManager
from .registry import ToolRegistry
from .executor import ToolExecutor
from .protocol import MCPMessage, MCPRequest, MCPResponse
from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MCPIntegration:
    """MCP 시스템과 AI 엔진을 통합하는 클래스"""
    
    def __init__(self):
        self.config = get_settings()
        
        # 실운영 강제: Gemini Provider 사용. 실패 시 에러로 처리
        self.llm_provider = GeminiProvider()
        
        self.prompt_manager = PromptManager()
        self.decision_engine = AgenticDecisionEngine(
            llm_provider=self.llm_provider,
            prompt_manager=self.prompt_manager
        )
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
    async def initialize(self):
        """MCP 시스템 초기화"""
        logger.info("MCP 시스템 초기화 중...")

        # LLM Provider 초기화 (실패 시 예외)
        ok = await self.llm_provider.initialize()
        if not ok or not self.llm_provider.is_available():
            raise RuntimeError(
                "LLM Provider(Gemini) 초기화 실패. 환경변수 'GOOGLE_API_KEY'를 설정했는지 확인하세요."
            )
        
        # 도구 자동 발견 및 등록
        await self._discover_and_register_tools()
        
        logger.info(f"MCP 시스템 초기화 완료. 등록된 도구 수: {len(self.tool_registry.list_tools())}")
    
    async def _discover_and_register_tools(self):
        """도구 자동 발견 및 등록 (프로덕션 경로)

        기존 예제 도구 경로(src.mcp.example_tools) 대신 실제 도구 패키지(src.tools)
        를 자동 검색하도록 단순화했습니다.
        """
        # 1) 일반 도구 자동 발견
        package_path = "src.tools"
        discovered_count = await self.tool_registry.discover_tools(package_path)
        logger.info(f"발견된 도구 수: {discovered_count} (패키지: {package_path})")

        # 2) Apple MCP 도구 수동 등록 (생성자 주입 필요)
        try:
            from .apple_tools import register_apple_tools
            from .apple_client import AppleAppsManager

            apple_manager = AppleAppsManager()
            apple_tools = register_apple_tools(apple_manager)

            registered = 0
            for tool in apple_tools:
                ok = await self.tool_registry.register_tool_instance(tool)
                if ok:
                    registered += 1

            if registered > 0:
                logger.info(f"Apple MCP 도구 등록: {registered}개")
            else:
                logger.warning("Apple MCP 도구 등록 0개 (권한/환경 확인 필요)")
        except Exception as e:
            logger.warning(f"Apple MCP 도구 등록 건너뜀: {e}")
    
    async def process_user_request(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """하위 호환용: 상세 실행 결과에서 텍스트만 반환"""
        detailed = await self.process_user_request_detailed(
            user_input, user_id=user_id, conversation_history=conversation_history
        )
        return detailed.get("text", "")

    async def process_user_request_detailed(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """사용자 요청을 처리하여 텍스트와 실행 메타데이터를 함께 반환"""
        try:
            logger.info(f"사용자 요청 처리 시작: {user_input}")

            # 1) 의사결정
            context = DecisionContext(
                user_message=user_input,
                user_id=user_id,
                conversation_history=conversation_history or []
            )
            decision = await self.decision_engine.make_decision(context)
            logger.info(f"AI 결정: {decision.selected_tools}, 신뢰도: {decision.confidence_score}")

            if decision.confidence_score < 0.7:
                text = await self._friendly_reply(user_input, hint="clarify")
                return {"text": text, "execution": None}

            if not decision.selected_tools:
                text = await self._friendly_reply(user_input)
                return {"text": text, "execution": None}

            tool_name = decision.selected_tools[0]
            available_tools = self.tool_registry.list_tools()
            if tool_name not in available_tools:
                text = f"❌ MCP 레지스트리에 '{tool_name}' 도구가 없습니다."
                return {"text": text, "execution": {"tool_name": tool_name, "status": "error", "error": "tool_not_found"}}

            # 2) 파라미터 정규화
            parameters: Dict[str, Any] = {}
            if decision.execution_plan:
                parameters = decision.execution_plan[0].get("parameters", {})
            parameters = self._normalize_parameters(tool_name, parameters)
            action = parameters.get("action") if isinstance(parameters, dict) else None

            # 3) 실행 (apple_notes update 시 내용 자동 보강)
            if tool_name == "apple_notes" and action == "update" and not parameters.get("content"):
                try:
                    # 3-1) 기존 메모 본문 읽기
                    read_params = {
                        "action": "read",
                        "target_title": parameters.get("target_title") or parameters.get("title"),
                        "folder": parameters.get("folder", "Notes"),
                    }
                    read_res = await self.tool_executor.execute_tool("apple_notes", read_params)
                    if read_res.result.is_success and isinstance(read_res.result.data, dict):
                        original_body = read_res.result.data.get("content", "")
                        # 3-2) LLM으로 본문 업데이트 생성
                        new_body = await self._llm_rewrite_note_body(original_body, user_input)
                        if new_body:
                            parameters["content"] = new_body
                except Exception as _e:
                    # 읽기/보강 실패 시 콘텐츠 없이 제목만 수정
                    pass

            execution_result = await self.tool_executor.execute_tool(tool_name=tool_name, parameters=parameters)

            # 4) 요약 + 메타
            if execution_result.result.is_success:
                logger.info(f"도구 실행 성공: {tool_name}")
                text = self._summarize_success(tool_name, parameters, execution_result.result.data)
                return {
                    "text": text,
                    "execution": {"tool_name": tool_name, "action": action, "status": "success", "parameters": parameters}
                }
            else:
                logger.error(f"도구 실행 실패: {execution_result.result.error_message}")
                text = self._summarize_failure(tool_name, parameters, execution_result.result.error_message)
                return {
                    "text": text,
                    "execution": {
                        "tool_name": tool_name,
                        "action": action,
                        "status": "error",
                        "error": execution_result.result.error_message,
                        "parameters": parameters,
                    },
                }
        except Exception as e:
            logger.error(f"요청 처리 중 오류: {e}")
            return {"text": f"❌ 시스템 오류: {str(e)}", "execution": {"status": "error", "error": str(e)}}

    async def _llm_rewrite_note_body(self, original_body: str, instruction: str) -> Optional[str]:
        """LLM을 사용해 메모 본문을 수정합니다.

        - 원문을 최대한 보존하면서, instruction에 해당하는 부분만 자연스럽게 반영
        - 결과는 전체 본문 문자열로만 반환 (포맷/코드블록 금지)
        """
        try:
            system = (
                "너는 메모 편집 도우미야.\n"
                "- 원문 본문을 최대한 보존하면서, 사용자의 지시사항만 반영해 업데이트해.\n"
                "- 중요: 결과는 전체 본문 문자열 하나만 반환해. 코드블록, 마크다운, 설명 금지.\n"
            )
            user = (
                f"[지시] {instruction}\n\n"
                f"[원문]\n{original_body}"
            )
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            resp = await self.llm_provider.generate_response(msgs, temperature=0.2)
            content = (resp.content or "").strip()
            # 코드블록 제거 등 최소 정리
            if content.startswith("```"):
                # 추출
                start = content.find("\n")
                end = content.rfind("```")
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()
            return content
        except Exception as e:
            logger.error(f"메모 본문 LLM 보강 실패: {e}")
            return None

    async def _friendly_reply(self, user_input: str, hint: Optional[str] = None) -> str:
        """도구 미사용 상황에서 간결한 개인비서 톤의 답변 생성"""
        try:
            system = (
                "당신은 Discord에서 사용자를 돕는 개인 비서 AI입니다.\n"
                "- 따뜻하고 친근한 톤으로 1~3문장 이내로 답하세요.\n"
                "- 과한 자기소개나 기능 나열은 피하고, 상대의 맥락에 맞게 답하세요.\n"
                "- 필요하면 간단한 후속 질문 하나만 덧붙이세요.\n"
                "- 이모지는 적절히 한두 개까지 허용합니다.\n"
                "- 도구/내부상태/오류 언급은 하지 마세요.\n"
                "- 한국어로 자연스럽게.\n"
                "- 당신의 이름은 '앙미니'입니다. 이름을 물으면 그렇게 소개하세요."
            )
            if hint == "clarify":
                system += "\n- 의도가 모호하면, 필요한 정보 한 가지만 정중히 물어보세요."
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ]
            # llm_provider는 이미 initialize됨
            chat_msgs = [ChatMessage(role=m["role"], content=m["content"]) for m in messages]
            resp = await self.llm_provider.generate_response(chat_msgs)
            return resp.content.strip()
        except Exception as e:
            logger.error(f"친화적 응답 생성 실패: {e}")
            # 최소한의 기본 인사/안내
            if hint == "clarify":
                return "요청을 조금만 더 구체적으로 알려주실 수 있을까요?"
            return "안녕하세요! 무엇을 도와드릴까요?"

    # ==========================
    # 결과 요약 포매터
    # ==========================
    def _summarize_success(self, tool_name: str, params: Dict[str, Any], data: Optional[Dict[str, Any]]) -> str:
        try:
            data = data or {}
            if tool_name == "echo":
                # 에코는 친절한 인사/안내 문장을 그대로 반환
                msg = data.get("echoed_message") or params.get("message")
                return msg or "안녕하세요! 무엇을 도와드릴까요?"
            if tool_name == "notion_todo":
                action = (params.get("action") or "create").lower()
                title = data.get("title") or params.get("title") or "할일"
                due = self._fmt_local_dt(params.get("due_date")) if params.get("due_date") else None
                url = data.get("url")
                if action == "create":
                    msg = f"✅ 할 일을 추가했어요: {title}"
                    if due:
                        msg += f" (마감: {due})"
                    if url:
                        msg += f"\n바로 열기: {url}"
                    return msg
                if action == "update":
                    return f"🔄 할 일을 업데이트했어요: {title}"
                if action == "complete":
                    return f"🎉 할 일을 완료 처리했어요: {title}"
                if action == "delete":
                    return f"🗑️ 할 일을 삭제했어요: {title}"
                if action in ("list", "get"):
                    todos = data.get("todos", [])
                    if not todos:
                        return "📭 표시할 할 일이 없어요."
                    lines = []
                    for t in todos[:5]:
                        t_title = t.get("title") or "(제목 없음)"
                        t_due = self._fmt_local_dt(t.get("due_date")) if t.get("due_date") else None
                        lines.append(f"• {t_title}{f' (마감: {t_due})' if t_due else ''}")
                    more = "\n…" if len(todos) > 5 else ""
                    return "📝 최근 할 일:\n" + "\n".join(lines) + more
                # fallback for unknown action
                return data.get("message") or "✅ 요청을 처리했어요."

            if tool_name == "notion_calendar":
                title = data.get("title") or params.get("title") or "일정"
                start = self._fmt_local_dt(params.get("start_date")) if params.get("start_date") else None
                end = self._fmt_local_dt(params.get("end_date")) if params.get("end_date") else None
                when = f" — {start}{f' ~ {end}' if end else ''}" if start else ""
                return f"📅 일정을 추가했어요: {title}{when}"

            if tool_name == "apple_notes":
                action = (params.get("action") or "create").lower()
                title = data.get("title") or params.get("title") or params.get("target_title") or "메모"
                if action == "update":
                    return f"📝 메모를 수정했어요: {title}"
                if action == "delete":
                    return f"🗑️ 메모를 삭제했어요: {title}"
                if action == "search":
                    count = (data.get("count") if isinstance(data, dict) else None) or 0
                    return f"🔎 메모를 {count}건 찾았어요."
                return f"📝 메모를 추가했어요: {title}"

            if tool_name == "apple_calendar":
                title = data.get("title") or params.get("title") or "일정"
                start = params.get("start_date")
                end = params.get("end_date")
                when = ""
                if isinstance(start, str) and start:
                    when = f" — {self._fmt_local_dt(start)}"
                    if isinstance(end, str) and end:
                        when = f" — {self._fmt_local_dt(start)} ~ {self._fmt_local_dt(end)}"
                return f"📅 Apple 캘린더에 일정을 추가했어요: {title}{when}"

            if tool_name == "calculator":
                expr = data.get("expression")
                res = data.get("result")
                if expr and res is not None:
                    return f"🔢 계산 결과: {expr}"
                return f"🔢 계산을 완료했어요: {res}"

            # 기본 요약
            msg = data.get("message") if isinstance(data, dict) else None
            return msg or "✅ 요청을 처리했어요."
        except Exception:
            return "✅ 요청을 처리했어요."

    def _summarize_failure(self, tool_name: str, params: Dict[str, Any], error: Optional[str]) -> str:
        # 사용자 친화적 실패 메시지
        if tool_name == "notion_todo":
            return "❌ 할 일을 처리하지 못했어요. 잠시 후 다시 시도해보시겠어요?"
        if tool_name == "notion_calendar":
            return "❌ 일정을 처리하지 못했어요. 입력하신 날짜/시간을 한 번만 더 확인해주세요."
        if tool_name == "apple_notes":
            return "❌ 메모를 추가하지 못했어요. macOS 권한 설정을 확인해 주세요."
        if tool_name == "calculator":
            return "❌ 계산을 완료하지 못했어요. 수식을 다시 한 번 확인해 주세요."
        return "❌ 요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요."

    def _fmt_local_dt(self, iso_str: Optional[str]) -> Optional[str]:
        if not iso_str or not isinstance(iso_str, str):
            return None
        try:
            from datetime import datetime
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            # 사용자가 KST를 쓰는 환경을 가정
            kst = dt.astimezone(ZoneInfo("Asia/Seoul"))
            return kst.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_str

    def _normalize_parameters(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """도구 실행 전 파라미터 정규화

        - calculator: {"expression": "2 + 3"} → {operation: "+", a: 2, b: 3}
        추가적인 도구별 맵핑이 필요하면 이곳에 확장합니다.
        """
        try:
            if tool_name == "calculator" and isinstance(params, dict):
                expr = params.get("expression")
                if isinstance(expr, str):
                    import re
                    m = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)", expr)
                    if m:
                        a = float(m.group(1))
                        op = m.group(2)
                        b = float(m.group(3))
                        return {"operation": op, "a": a, "b": b, **{k: v for k, v in params.items() if k != "expression"}}
            elif tool_name == "apple_notes" and isinstance(params, dict):
                raw_action = str(params.get("action", "")).strip().lower()
                # 한국어/자유형 액션을 표준으로 매핑 (부분 포함 허용)
                create_words = ["create", "add", "make", "메모 생성", "생성", "추가", "작성"]
                search_words = ["search", "find", "검색"]
                update_words = ["update", "수정", "편집"]
                delete_words = ["delete", "remove", "삭제"]

                def match_any(words: list[str]) -> bool:
                    return any(w.lower() in raw_action for w in words)

                normalized = None
                if raw_action:
                    if match_any(update_words):
                        normalized = "update"
                    elif match_any(search_words):
                        normalized = "search"
                    elif match_any(delete_words):
                        normalized = "delete"
                    elif match_any(create_words):
                        normalized = "create"

                # 힌트 기반 보정: target_title이 있으면 update가 자연스러움
                if not normalized:
                    if "target_title" in params or "note_id" in params:
                        normalized = "update"
                    else:
                        normalized = "create"

                params["action"] = normalized
                # 제목이 없으면 내용 앞부분으로 생성
                title = params.get("title")
                content = params.get("content") or ""
                if not title:
                    params["title"] = content[:30] if content else "새 메모"
                if "folder" not in params:
                    params["folder"] = "Notes"
                return params
            elif tool_name == "echo" and isinstance(params, dict):
                # flash 계열이 'text'로 내려줄 수 있어 'message'로 보정
                if "message" not in params:
                    if "text" in params:
                        params["message"] = params.pop("text")
                    elif "content" in params:
                        params["message"] = params.pop("content")
                # 여분 키 제거는 도구가 무시하지만, 명시적으로 유지/정리 가능
                return params
            elif tool_name == "notion_todo" and isinstance(params, dict):
                # 액션 표준화
                action = params.get("action", "create")
                synonyms = {
                    "create": {"create", "추가", "생성", "등록", "만들어", "만들다", "할일 추가"},
                    "update": {"update", "수정", "변경", "편집"},
                    "delete": {"delete", "삭제", "제거"},
                    "get": {"get", "조회", "확인", "보기"},
                    "list": {"list", "목록", "리스트"},
                    "complete": {"complete", "완료", "끝"}
                }
                normalized = "create"
                for key, words in synonyms.items():
                    if str(action).lower() in [w.lower() for w in words]:
                        normalized = key
                        break
                params["action"] = normalized

                # 우선순위 표준화 (영문/한글/동의어 허용 → 한국어: 높음/중간/낮음)
                pr = params.get("priority")
                if isinstance(pr, str) and pr.strip():
                    pr_l = pr.strip().lower()
                    high_set = {"high", "높음", "높다", "상", "urgent", "중요", "매우높음", "very high", "긴급"}
                    medium_set = {"medium", "normal", "중간", "보통", "일반", "중"}
                    low_set = {"low", "낮음", "낮다", "하", "minor", "low priority", "low-priority"}
                    if pr_l in [s.lower() for s in high_set]:
                        params["priority"] = "높음"
                    elif pr_l in [s.lower() for s in medium_set]:
                        params["priority"] = "중간"
                    elif pr_l in [s.lower() for s in low_set]:
                        params["priority"] = "낮음"
                    else:
                        # 문장형 입력 처리 (예: "very_high", "매우 높음")
                        if any(k in pr_l for k in ["very", "매우", "high", "urgent", "중요"]):
                            params["priority"] = "높음"
                        elif any(k in pr_l for k in ["low", "낮"]):
                            params["priority"] = "낮음"
                        else:
                            params["priority"] = "중간"
                # due_date ISO 보정(로컬 타임존 KST +09:00 적용)
                dd = params.get("due_date")
                if isinstance(dd, str) and ('Z' not in dd and '+' not in dd and '-' not in dd[10:]):
                    # naive ISO-like → KST(+09:00)로 간주
                    if len(dd) >= 16 and 'T' in dd:
                        params["due_date"] = dd + "+09:00"
                return params
            elif tool_name == "notion_calendar" and isinstance(params, dict):
                # 액션 표준화
                action = params.get("action", "create")
                synonyms = {
                    "create": {"create", "추가", "생성", "등록", "일정 추가", "일정 생성"},
                    "update": {"update", "수정", "변경", "편집", "일정 수정"},
                    "delete": {"delete", "삭제", "제거", "일정 삭제"},
                    "get": {"get", "조회", "확인", "보기"},
                    "list": {"list", "목록", "리스트"}
                }
                normalized = "create"
                for key, words in synonyms.items():
                    if str(action).lower() in [w.lower() for w in words]:
                        normalized = key
                        break
                params["action"] = normalized
                # 날짜 키 표준화
                if "start_date" not in params:
                    if "date" in params:
                        params["start_date"] = params.pop("date")
                    elif "start" in params:
                        params["start_date"] = params.pop("start")
                # ISO 보정 (로컬 타임존 KST +09:00 적용)
                for key in ("start_date", "end_date"):
                    v = params.get(key)
                    if isinstance(v, str) and ('Z' not in v and '+' not in v and '-' not in v[10:]):
                        if len(v) >= 16 and 'T' in v:
                            params[key] = v + "+09:00"
                return params
            elif tool_name == "apple_calendar" and isinstance(params, dict):
                # 액션 표준화
                action = params.get("action", "create")
                synonyms = {
                    "create": {"create", "추가", "생성", "등록", "일정 추가", "일정 생성"},
                    "search": {"search", "검색", "찾기"},
                    "list": {"list", "목록", "조회"},
                    "open": {"open", "열기"}
                }
                normalized = "create"
                for key, words in synonyms.items():
                    if str(action).lower() in [w.lower() for w in words]:
                        normalized = key
                        break
                params["action"] = normalized
                return params
            return params
        except Exception:
            return params
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록 반환"""
        tool_names = self.tool_registry.list_tools()
        tools = []
        
        for tool_name in tool_names:
            metadata = self.tool_registry.get_tool_metadata(tool_name)
            if metadata:
                tools.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "parameters": [param.to_dict() for param in metadata.parameters]
                })
        
        return tools
    
    async def test_tool_execution(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """특정 도구 테스트 실행"""
        try:
            execution_result = await self.tool_executor.execute_tool(tool_name, parameters)
            
            if execution_result.result.is_success:
                return f"✅ {tool_name} 실행 성공:\n{execution_result.result.data}"
            else:
                return f"❌ {tool_name} 실행 실패:\n{execution_result.result.error_message}"
                
        except Exception as e:
            return f"❌ 테스트 중 오류: {str(e)}"


async def run_integration_test():
    """MCP 통합 시스템 테스트"""
    print("🚀 MCP 통합 시스템 테스트 시작")
    
    # 1. 시스템 초기화
    integration = MCPIntegration()
    await integration.initialize()
    
    # 2. 사용 가능한 도구 확인
    tools = await integration.get_available_tools()
    print(f"\n📋 사용 가능한 도구 ({len(tools)}개):")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # 3. 직접 도구 테스트
    if tools:
        print(f"\n🔧 첫 번째 도구 테스트: {tools[0]['name']}")
        
        # 계산기 도구 테스트
        if tools[0]['name'] == 'calculator':
            test_result = await integration.test_tool_execution(
                'calculator', 
                {'expression': '2 + 3 * 4'}
            )
            print(f"결과: {test_result}")
    
    # 4. 자연어 요청 테스트
    print(f"\n💬 자연어 요청 테스트")
    test_requests = [
        "2 더하기 3은 얼마야?",
        "현재 시간 알려줘",
        "안녕하세요"  # 모호한 요청
    ]
    
    for request in test_requests:
        print(f"\n사용자: {request}")
        response = await integration.process_user_request(request)
        print(f"AI 비서: {response}")
    
    print("\n✅ MCP 통합 시스템 테스트 완료")


if __name__ == "__main__":
    asyncio.run(run_integration_test())
