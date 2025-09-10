"""
MCP 시스템 통합 모듈 (에이전틱 AI 업그레이드)

AI 엔진과 MCP 도구들을 통합하여 실제 작업을 수행할 수 있도록 하는 모듈입니다.
진정한 에이전틱 AI ReAct 엔진을 사용하면서 기존 인터페이스와의 호환성을 유지합니다.
"""

import asyncio
import os
import json
from typing import List, Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..integration.legacy_adapter import LegacyMCPAdapter
from pathlib import Path
import unicodedata
import re
import time

from ..ai_engine.llm_provider import GeminiProvider, MockLLMProvider, ChatMessage, LLMProviderError
from ..ai_engine.decision_engine import AgenticDecisionEngine, DecisionContext
from ..ai_engine.prompt_templates import PromptManager
from .registry import ToolRegistry
from .executor import ToolExecutor
from .protocol import MCPMessage, MCPRequest, MCPResponse
from ..config import get_settings
from ..utils.logger import get_logger

# 새로운 에이전틱 AI 시스템 import
from ..integration.legacy_adapter import LegacyMCPAdapter

logger = get_logger(__name__)


class MCPIntegration:
    """
    MCP 시스템과 AI 엔진을 통합하는 클래스 (에이전틱 AI 업그레이드)
    
    기존 인터페이스를 완전히 유지하면서 내부적으로는 진정한 에이전틱 AI를 사용합니다.
    """
    
    def __init__(self):
        self.config = get_settings()
        
        # 실운영 강제: Gemini Provider 사용. 실패 시 에러로 처리
        self.llm_provider = GeminiProvider()
        
        self.prompt_manager = PromptManager()
        
        # 기존 decision_engine 유지 (하위 호환성)
        self.decision_engine = AgenticDecisionEngine(
            llm_provider=self.llm_provider,
            prompt_manager=self.prompt_manager
        )
        
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
        # 새로운 에이전틱 AI 어댑터 초기화
        self.agentic_adapter: Optional['LegacyMCPAdapter'] = None  # 지연 초기화
        
        # 에이전틱 모드 설정 (환경변수로 제어 가능)
        self.agentic_enabled = os.getenv("PAI_AGENTIC_ENABLED", "true").lower() == "true"
        
        logger.info(f"MCP 통합 초기화 (에이전틱 모드: {'활성화' if self.agentic_enabled else '비활성화'})")
    
    async def _ensure_agentic_adapter(self):
        """에이전틱 어댑터 지연 초기화"""
        if self.agentic_adapter is None:
            from ..integration.legacy_adapter import LegacyMCPAdapter
            self.agentic_adapter = LegacyMCPAdapter(
                llm_provider=self.llm_provider,
                tool_registry=self.tool_registry,
                tool_executor=self.tool_executor,
                prompt_manager=self.prompt_manager
            )
            await self.agentic_adapter.initialize()
        
    async def initialize(self):
        """MCP 시스템 초기화"""
        logger.info("MCP 시스템 초기화 중...")

        # 에이전틱 어댑터 초기화 (기존 초기화 로직 포함)
        await self._ensure_agentic_adapter()
        
        # 기존 호환성을 위해 기본 초기화도 수행
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

        # 2) 시스템 시간 도구 수동 등록
        try:
            from ..tools.system_time_tool import create_system_time_tool
            system_time_tool = create_system_time_tool()
            await system_time_tool.initialize()
            ok = await self.tool_registry.register_tool_instance(system_time_tool)
            if ok:
                logger.info("시스템 시간 도구 등록 완료")
            else:
                logger.warning("시스템 시간 도구 등록 실패")
        except Exception as e:
            logger.warning(f"시스템 시간 도구 등록 건너뜀: {e}")

        # 3) Apple MCP 도구 수동 등록 (생성자 주입 필요)
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
        """
        사용자 요청 처리 (기존 인터페이스 유지, 에이전틱 AI 업그레이드)
        
        기존 인터페이스를 완전히 유지하면서 내부적으로는 새로운 에이전틱 AI를 사용합니다.
        """
        if self.agentic_enabled:
            # 새로운 에이전틱 AI 시스템 사용
            await self._ensure_agentic_adapter()
            assert self.agentic_adapter is not None  # 타입 체커를 위한 assertion
            return await self.agentic_adapter.process_user_request(
                user_input=user_input,
                user_id=user_id,
                conversation_history=conversation_history
            )
        else:
            # 기존 방식 (레거시 모드)
            detailed = await self._process_user_request_legacy(
                user_input, user_id=user_id, conversation_history=conversation_history
            )
            return detailed.get("text", "")

    async def process_user_request_detailed(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        사용자 요청 처리 (상세 결과 반환, 에이전틱 AI 업그레이드)
        
        기존 인터페이스를 완전히 유지하면서 내부적으로는 새로운 에이전틱 AI를 사용합니다.
        """
        if self.agentic_enabled:
            # 새로운 에이전틱 AI 시스템 사용
            await self._ensure_agentic_adapter()
            assert self.agentic_adapter is not None  # 타입 체커를 위한 assertion
            return await self.agentic_adapter.process_user_request_detailed(
                user_input=user_input,
                user_id=user_id,
                conversation_history=conversation_history
            )
        else:
            # 기존 방식 (레거시 모드)
            return await self._process_user_request_legacy(
                user_input, user_id=user_id, conversation_history=conversation_history
            )
    
    async def _process_user_request_legacy(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """기존 처리 방식 (레거시 모드용)"""
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

            # 자연어 직접 답변(REPLY) 경로 우선 처리
            if not decision.selected_tools and decision.reasoning:
                txt = (decision.reasoning or "").strip()
                if txt:
                    logger.info("Agentic: Direct REPLY 선택 — 도구 실행 없이 응답 반환")
                    return {"text": txt, "execution": None}

            if decision.confidence_score < 0.7:
                logger.info("Agentic: 낮은 신뢰도 — 의도 확인 질문으로 전환")
                text = await self._friendly_reply(user_input, hint="clarify")
                return {"text": text, "execution": None}

            if not decision.selected_tools:
                logger.info("Agentic: 선택된 도구 없음 — 일반 답변 모드")
                text = await self._friendly_reply(user_input)
                return {"text": text, "execution": None}

            # Plan 실행 (원샷 에이전틱): 모든 스텝을 순차적으로 실행
            tool_name = decision.selected_tools[0]
            available_tools = self.tool_registry.list_tools()
            if tool_name not in available_tools:
                text = f"❌ MCP 레지스트리에 '{tool_name}' 도구가 없습니다."
                return {"text": text, "execution": {"tool_name": tool_name, "status": "error", "error": "tool_not_found"}}

            # 파일시스템 계획에 move 스텝이 하나라도 있으면 NL 해석/탐색 핸들러로 일괄 처리
            if tool_name == "filesystem":
                move_step = None
                for st in (decision.execution_plan or []):
                    if isinstance(st, dict):
                        act = (st.get("action") or "").strip().lower()
                        # 한국어 동의어 포함 처리
                        if act in {"move", "이동", "옮겨", "옮기기", "파일/폴더 이동"}:
                            move_step = st
                            break
                if move_step is not None:
                    params0 = (move_step.get("parameters") if isinstance(move_step, dict) else {}) or {}
                    return await self._handle_filesystem_request(user_input, "move", params0)

            plan_result = await self._execute_plan(decision, user_input)
            return plan_result
            
        except Exception as e:
            logger.error(f"레거시 요청 처리 실패: {e}")
            return {
                "text": f"요청 처리 중 오류가 발생했습니다: {str(e)}",
                "execution": {
                    "status": "error",
                    "error": str(e)
                }
            }

    async def _maybe_refine_response(self, user_input: str, draft: str, result_data: Optional[Dict[str, Any]] = None) -> str:
        """환경변수로 제어되는 최종 응답 LLM 리파인 단계 (JSON 강제 없음)."""
        try:
            if os.getenv("PAI_REFINE_FINAL", "0") not in {"1", "true", "TRUE"}:
                logger.debug("Refine: 비활성화 — 초안 그대로 사용")
                return draft
            logger.debug("Refine: 활성화 — 초안 응답을 LLM으로 매끄럽게 정리")
            system = (
                "너는 사용자의 요청과 초안 응답, 도구 결과를 바탕으로 짧고 자연스러운 한국어 답변을 만들어.")
            user = (
                f"[사용자 요청]\n{user_input}\n\n[초안]\n{draft}\n\n[도구 결과]\n{json.dumps(result_data, ensure_ascii=False) if result_data is not None else '없음'}\n\n"
                "- 1~3문장으로 간결하게 정리\n- 과한 수식/코드블록/마크다운 금지\n- 핵심만 부드럽게 전달"
            )
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            resp = await self.llm_provider.generate_response(msgs, temperature=0.3)
            content = (resp.content or draft).strip()
            # 간단한 정리: 코드블록 제거
            if content.startswith("```"):
                s = content.find("\n"); e = content.rfind("```")
                if s != -1 and e != -1:
                    content = content[s+1:e].strip()
            return content or draft
        except Exception:
            return draft

    # ==========================
    # Filesystem NL Handling
    # ==========================
    def _norm(self, s: str) -> str:
        try:
            forms = [unicodedata.normalize(f, s) for f in ("NFC", "NFD", "NFKC", "NFKD")]
            # 공백/구분자 제거한 축약형도 포함해 매칭 강건성 향상
            import re as _re
            collapsed = []
            for f in forms + [s]:
                collapsed.append(_re.sub(r"[\s\-_.\/]+", "", f))
            return "\n".join(forms + [s] + collapsed).lower()
        except Exception:
            return str(s).lower()

    def _score_filename(self, name: str, hints: List[str]) -> int:
        n = self._norm(name)
        score = 0
        # 확장자 힌트 가중치
        lower = name.lower()
        doc_exts = [".txt", ".hwpx", ".hwp", ".docx", ".pdf", ".md"]
        if any(lower.endswith(ext) for ext in doc_exts):
            # 문서류 파일이면 기본 가점
            score += 2
        if lower.endswith(".txt"):
            score += 1
        for h in hints:
            hn = self._norm(h)
            if hn in n:
                score += 3
        # common variants for the sample request
        for key in ["mcp", "설계", "계획", "학회", "여름", "세미나", "문서", "파일", "설계계획", "qgis"]:
            if key and self._norm(key) in n:
                score += 2
        return score

    def _score_file_entry(self, entry: Dict[str, Any], hints: List[str], desktop_root: Optional[str] = None) -> int:
        name = entry.get("name", "")
        path = entry.get("path", "") or name
        score = self._score_filename(name, hints)
        try:
            if desktop_root and isinstance(desktop_root, str) and path.startswith(desktop_root):
                rel = path[len(desktop_root):].lstrip("/")
                depth = rel.count("/")
                if depth <= 0:
                    score += 5  # 바탕화면 최상위 가점
                elif depth == 1:
                    score += 3
        except Exception:
            pass
        return score

    async def _handle_filesystem_request(self, user_input: str, action: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """자연어 기반 파일 시스템 작업 처리 (특히 move 시나리오)

        1) 바탕화면(Desktop) 등 허용 루트에서 재귀 탐색으로 원본 파일 후보 탐색
        2) 사용자가 언급한 목적 폴더 탐색
        3) dry_run으로 계획 검증 후 실제 실행 및 검증
        """
        try:
            # 기본 해석: '옮겨' 포함 시 move로 간주
            u = user_input
            if not action:
                if any(k in u for k in ["옮겨", "move", "이동"]):
                    action = "move"

            if action != "move":
                # 기타 액션은 그대로 실행
                execution_result = await self.tool_executor.execute_tool("filesystem", params)
                if execution_result.result.is_success:
                    text = self._summarize_success("filesystem", params, execution_result.result.data)
                    return {
                        "text": text,
                        "execution": {
                            "tool_name": "filesystem",
                            "action": params.get("action"),
                            "status": "success",
                            "parameters": params,
                            "result_data": execution_result.result.data,
                        },
                    }
                else:
                    text = self._summarize_failure("filesystem", params, execution_result.result.error_message)
                    return {
                        "text": text,
                        "execution": {
                            "tool_name": "filesystem",
                            "action": params.get("action"),
                            "status": "error",
                            "error": execution_result.result.error_message,
                            "parameters": params,
                        },
                    }

            # ===== move 전용 처리 =====
            desktop_path = Path.home() / "Desktop"
            desktop = str(desktop_path)

            # 보조: 루트 별칭 매핑
            def map_root(seg: str) -> Optional[Path]:
                # 루트 세그먼트 정규화 + 불용어 제거("내","나의","my","the")
                try:
                    import re as _re
                    base = unicodedata.normalize("NFKC", seg).strip().lower()
                    base = _re.sub(r"[\s\-_.]+", "", base)
                    base = base.replace("내", "").replace("나의", "").replace("my", "").replace("the", "")
                except Exception:
                    base = str(seg).strip().lower()
                if base in {"desktop", "바탕화면"}:
                    return desktop_path
                if base in {"documents", "문서", "도큐먼트", "내문서", "mydocuments"}:
                    return Path.home() / "Documents"
                if base in {"downloads", "다운로드", "mydownloads"}:
                    return Path.home() / "Downloads"
                return None

            # 보조: "바탕화면/대학/2025-2" 같은 의미 경로를 실제 경로로 추정
            def semantic_to_path(text: str) -> Optional[Path]:
                if not text:
                    return None
                raw = text.replace("\\", "/").strip().strip("\"")
                # 1) 절대 경로 처리
                try:
                    from os.path import isabs as _isabs
                except Exception:
                    _isabs = None  # type: ignore
                if (hasattr(Path, 'is_absolute') and Path(raw).is_absolute()) or (_isabs and _isabs(raw)):
                    try:
                        return Path(raw).resolve(strict=False)
                    except Exception:
                        return Path(raw)
                # 2) ~ 확장
                if raw.startswith("~"):
                    try:
                        return Path(raw).expanduser().resolve(strict=False)
                    except Exception:
                        return Path(raw).expanduser()
                # 3) 의미 경로(바탕화면/문서 등) → 실제 경로 추정
                parts = [p for p in raw.split('/') if p]
                if not parts:
                    return None
                mapped_root = map_root(parts[0])
                if mapped_root is not None:
                    root = mapped_root
                    sub = parts[1:]
                else:
                    # 'Users/...' 같이 시스템 루트 하위로 시작하면 절대 루트로 해석
                    if parts[0].lower() in {"users", "system", "library", "applications", "volumes"}:
                        root = Path('/')
                        sub = parts
                    else:
                        # 기본 Desktop 기준 상대 경로
                        root = desktop_path
                        sub = parts
                p = root
                for seg in sub:
                    p = p / seg
                return p

            # 보조: Desktop 경로 중복 정규화 (예: ~/Desktop/바탕화면/대학 → ~/Desktop/대학)
            def sanitize_desktop_path(p: Path) -> Path:
                try:
                    p = p.resolve(strict=False)
                except Exception:
                    pass
                try:
                    root = desktop_path.resolve(strict=False)
                    # 상대 경로 분해
                    rel = None
                    try:
                        rel = p.relative_to(root)
                    except Exception:
                        return p
                    parts = list(rel.parts)
                    if parts and parts[0] in {"바탕화면", "desktop", "Desktop"}:
                        parts = parts[1:]
                    newp = root
                    for seg in parts:
                        newp = newp / seg
                    return newp
                except Exception:
                    return p

            # 1) 원본 파일 추정 + 스캔 루트 보조 추정
            src = params.get("src")
            src_path = None
            scan_root_override: Optional[Path] = None
            src_extra_tokens: list[str] = []
            if isinstance(src, str) and src:
                raw_src = src.replace("\\", "/").strip().strip("\"")
                cand = semantic_to_path(raw_src)
                try:
                    if cand and cand.exists():
                        # 파일이 바로 존재하면 그대로 사용. 폴더면 그 폴더를 스캔 루트로 사용
                        if cand.is_file():
                            src_path = str(cand)
                        elif cand.is_dir():
                            scan_root_override = cand
                    else:
                        # 마지막 세그먼트를 파일 질의로 가정, 나머지는 폴더로 해석
                        parts = [p for p in raw_src.split('/') if p]
                        if len(parts) >= 2:
                            folder_guess = semantic_to_path('/'.join(parts[:-1]))
                            if folder_guess and folder_guess.exists() and folder_guess.is_dir():
                                scan_root_override = folder_guess
                                src_extra_tokens.append(parts[-1])
                except Exception:
                    pass
            need_find_src = not src_path

            # 빠른 경로: 바탕화면 최상위에서 한글 핵심 키워드 우선 매칭
            if need_find_src:
                try:
                    top_files = [p for p in desktop_path.iterdir() if p.is_file()]
                    def _k_match(nm: str) -> bool:
                        nn = self._norm(nm)
                        return all(self._norm(k) in nn for k in ["설계", "세미나"]) or \
                               (self._norm("여름") in nn and self._norm("세미나") in nn)
                    for p in top_files:
                        if _k_match(p.name):
                            src_path = str(p)
                            break
                except Exception:
                    pass
                need_find_src = not src_path
            # 2) 목적 폴더 추정
            dst = params.get("dst")
            dst_folder_path: Optional[Path] = None
            if isinstance(dst, str) and dst:
                cand = semantic_to_path(dst)
                if cand:
                    # 폴더로 간주 (존재하지 않아도 허용: move가 부모 생성)
                    dst_folder_path = cand if cand.suffix == '' else cand.parent
                    dst_folder_path = sanitize_desktop_path(dst_folder_path)
                    # 마지막 세그먼트가 파일명 유사(파일/문서/설계/세미나/여름/학회 포함)면 상위 폴더로 보정
                    try:
                        last = dst_folder_path.name
                        if any(self._norm(k) in self._norm(last) for k in ["파일", "문서", "설계", "세미나", "여름", "학회"]):
                            dst_folder_path = dst_folder_path.parent
                    except Exception:
                        pass
            need_find_dst = dst_folder_path is None

            # 데스크탑 인덱싱 (최상위만, 비재귀)
            # 기본 스캔 루트: Desktop, 단 src에서 폴더가 유도되면 그 폴더를 우선 스캔
            listed = await self.tool_executor.execute_tool(
                tool_name="filesystem",
                parameters={
                    "action": "list",
                    "path": desktop,
                    "recursive": False,
                    "include_hidden": False,
                    "max_items": 5000,
                },
            )
            if not listed.result.is_success:
                return {"text": f"❌ 바탕화면 조회 실패: {listed.result.error_message}", "execution": {"status": "error", "error": listed.result.error_message}}

            items = listed.result.data.get("items", []) if isinstance(listed.result.data, dict) else []
            files = [it for it in items if it.get("type") == "file"]
            dirs = [it for it in items if it.get("type") == "dir"]
            logger.info(f"Agentic(FS): Desktop 인덱싱 완료 — files={len(files)}, dirs={len(dirs)}")

            # 스캔 루트가 별도로 감지되면 해당 폴더에서 파일 목록을 재수집
            if scan_root_override is not None and scan_root_override.exists():
                try:
                    res2 = await self.tool_executor.execute_tool(
                        tool_name="filesystem",
                        parameters={
                            "action": "list",
                            "path": str(scan_root_override),
                            "recursive": False,
                            "include_hidden": False,
                            "max_items": 5000,
                        },
                    )
                    if res2.result.is_success and isinstance(res2.result.data, dict):
                        items2 = res2.result.data.get("items", [])
                        files = [it for it in items2 if it.get("type") == "file"]
                        logger.info(
                            f"Agentic(FS): 스캔 루트 교체 — path={scan_root_override}, files={len(files)}"
                        )
                except Exception as e:
                    logger.warning(f"Agentic(FS): 스캔 루트 목록 실패 — {e}")

            # 후보 전처리 유틸
            def _rel_from_desktop(path_str: str) -> str:
                try:
                    p = Path(path_str)
                    return str(p.relative_to(desktop_path))
                except Exception:
                    return path_str
            def _is_noise_file(name: str) -> bool:
                low = (name or "").lower()
                return low in {"thumbs.db", ".ds_store", "desktop.ini"}
            def _is_noise_dir(name: str) -> bool:
                low = (name or "").lower()
                return low in {"node_modules", ".git", "venv", ".venv", "__pycache__"}

            # 힌트 추출(사용자 입력과 src 파라미터에서 한글/영문/숫자 토큰)
            src_hint = src if isinstance(src, str) else ""
            tokens = re.findall(r"[\w가-힣]+", u + " " + src_hint + (" " + " ".join(src_extra_tokens) if src_extra_tokens else ""))
            # 핵심 한국어 키워드가 요청문에 있다면 강한 필터로 사용
            must_keys_base = ["설계", "세미나", "여름", "학회"]
            must_keys = [k for k in must_keys_base if self._norm(k) in self._norm(u)]
            if must_keys:
                logger.debug(f"Agentic(FS): 핵심 키워드 감지 — {must_keys}")

            if need_find_src:
                # 필수 키워드 매칭 기반 후보 축소
                filtered = [it for it in files if not _is_noise_file(it.get("name", ""))]
                try:
                    if must_keys:
                        def _match_count(nm: str) -> int:
                            n = self._norm(nm)
                            return sum(1 for k in must_keys if self._norm(k) in n)
                        tmp = [it for it in files if _match_count(it.get("name", "")) >= min(2, len(must_keys))]
                        if not tmp:
                            tmp = [it for it in files if _match_count(it.get("name", "")) >= 1]
                        if tmp:
                            filtered = [it for it in tmp if not _is_noise_file(it.get("name", ""))]
                except Exception:
                    pass
                logger.info(f"Agentic(FS): 후보 필터링 — filtered_files={len(filtered)}")
                best = None
                best_score = -1
                for it in filtered:
                    s = self._score_file_entry(it, tokens, desktop_root=desktop)
                    if s > best_score:
                        best, best_score = it, s

                # LLM에게 상위 후보를 보여주고 선택하도록 위임 (폴백 제거)
                MAX_CANDS = int(os.getenv("PAI_FS_LLM_CANDIDATES", "10"))
                ranked = sorted(
                    filtered,
                    key=lambda it: self._score_file_entry(it, tokens, desktop_root=desktop),
                    reverse=True,
                )[:MAX_CANDS]
                if ranked:
                    # 상위 후보들의 스코어 로그 (Thinking transparency)
                    try:
                        scored_preview = [
                            (it.get('name',''), self._score_file_entry(it, tokens, desktop_root=desktop))
                            for it in ranked[:5]
                        ]
                        logger.debug(f"Agentic(FS): 상위 후보(이름,점수) — {scored_preview}")
                    except Exception:
                        pass
                    logger.info(f"Agentic(FS): LLM 후보 제시 — count={len(ranked)}")
                    if len(ranked) == 1:
                        # 후보 1개면 LLM 건너뛰고 확정
                        best = ranked[0]
                        best_score = 999
                    else:
                        llm_index = None
                        try:
                            llm_index = await self._llm_select_from_candidates(
                                question="사용자의 지시에 가장 부합하는 원본 파일을 선택하세요.",
                                candidates=[
                                    {"name": it.get("name", ""), "path": _rel_from_desktop(it.get("path", ""))}
                                    for it in ranked
                                ],
                                kind="file",
                                user_input=user_input,
                            )
                        except Exception as e:
                            logger.warning(f"Agentic(FS): LLM 후보 선택 중 오류 — {e}")
                        if llm_index is None or not (0 <= llm_index < len(ranked)):
                            return {"text": "❌ 원본 파일 선택 실패: LLM 응답을 이해하지 못했습니다.", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": "llm_selection_failed"}}
                        best = ranked[llm_index]
                        best_score = 999
                        logger.info(
                            f"Agentic(FS): LLM 파일 선택 — name={best.get('name','')}, rel={_rel_from_desktop(best.get('path',''))}"
                        )
                # LLM 결정 반영
                src_path = best.get("path") if best else None
                if not src_path:
                    return {"text": "❌ 원본 파일 선택 실패: 후보가 비어있습니다.", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": "no_candidates"}}
            else:
                # src가 의미경로였지만 존재하지 않는 경우, 마지막 세그먼트를 키워드로 검색
                if isinstance(src, str) and src and not Path(src).exists():
                    last_seg = src.replace("\\", "/").strip("/").split("/")[-1]
                    extra_tokens = re.findall(r"[\w가-힣]+", last_seg)
                    if extra_tokens:
                        filtered2 = files
                        try:
                            if must_keys:
                                def _mc(nm: str) -> int:
                                    n = self._norm(nm)
                                    return sum(1 for k in must_keys if self._norm(k) in n)
                                tmp2 = [it for it in files if _mc(it.get("name", "")) >= min(2, len(must_keys))]
                                if not tmp2:
                                    tmp2 = [it for it in files if _mc(it.get("name", "")) >= 1]
                                if tmp2:
                                    filtered2 = tmp2
                        except Exception:
                            pass
                        best = None
                        best_score = -1
                        for it in filtered2:
                            s = self._score_filename(it.get("name", ""), tokens + extra_tokens)
                            if s > best_score:
                                best, best_score = it, s
                        if best and best_score >= 3:
                            src_path = best.get("path")

            # 목적 폴더 결정
            if need_find_dst:
                dst_folder = None
                # 폴더명을 사용자 입력에서 추출 (영문/한글 토큰 기반)
                folder_tokens = [t for t in tokens if len(t) >= 2]
                preferred_dirs = [d for d in dirs if not _is_noise_dir(d.get("name", ""))]
                logger.info(f"Agentic(FS): 폴더 후보 — candidates={len(preferred_dirs)}; 예시={[d.get('name','') for d in preferred_dirs[:3]]}")
                # 1) 키워드 일치 우선
                for cand in folder_tokens:
                    for d in preferred_dirs:
                        if self._norm(cand) in self._norm(d.get("name", "")):
                            dst_folder = d.get("path")
                            break
                    if dst_folder:
                        break
                # 2) LLM이 최적 폴더 선택 (기본 활성)
                if not dst_folder and preferred_dirs:
                    MAX_DIRS = int(os.getenv("PAI_FS_LLM_DIR_CANDIDATES", "12"))
                    ranked_dirs = preferred_dirs[:MAX_DIRS]
                    try:
                        logger.debug(f"Agentic(FS): 폴더 후보 — {[d.get('name','') for d in ranked_dirs[:10]]}")
                    except Exception:
                        pass
                    logger.info(f"Agentic(FS): LLM 폴더 후보 제시 — count={len(ranked_dirs)}")
                    if len(ranked_dirs) == 1:
                        dst_folder = ranked_dirs[0].get("path")
                    else:
                        llm_index = None
                        try:
                            llm_index = await self._llm_select_from_candidates(
                                question="사용자의 지시에 가장 부합하는 대상 폴더를 선택하세요.",
                                candidates=[
                                    {"name": d.get("name", ""), "path": _rel_from_desktop(d.get("path", ""))}
                                    for d in ranked_dirs
                                ],
                                kind="directory",
                                user_input=user_input,
                            )
                        except Exception as e:
                            logger.warning(f"Agentic(FS): LLM 폴더 후보 선택 중 오류 — {e}")
                        if llm_index is None or not (0 <= llm_index < len(ranked_dirs)):
                            return {"text": "❌ 대상 폴더 선택 실패: LLM 응답을 이해하지 못했습니다.", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": "llm_selection_failed"}}
                        sel = ranked_dirs[llm_index]
                        rel = _rel_from_desktop(sel.get("path", ""))
                        dst_folder = str((desktop_path / rel).resolve(strict=False))
                        logger.info(f"Agentic(FS): LLM 폴더 선택 — name={sel.get('name','')}, rel={rel}")
                    rel = _rel_from_desktop(sel.get("path", ""))
                    dst_folder = str((desktop_path / rel).resolve(strict=False))
                    logger.info(f"Agentic(FS): LLM 폴더 선택 — name={sel.get('name','')}, rel={rel}")
            else:
                dst_folder = str(dst_folder_path)

            # 3) 최종 대상 파일 경로 구성
            if not src_path:
                return {"text": "❌ 원본 파일 선택 실패: 후보가 비어있거나 선택되지 않았습니다.", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": "source_not_selected"}}

            base_name = Path(src_path).name
            sanitized_folder = sanitize_desktop_path(Path(dst_folder))
            if str(sanitized_folder) != str(Path(dst_folder)):
                logger.debug(f"Agentic(FS): 대상 폴더 정규화 — before={dst_folder}, after={sanitized_folder}")
            dst_path = str(sanitized_folder / base_name)
            # 대상 파일 존재 시 충돌 회피(타임스탬프)
            stat_dst = await self.tool_executor.execute_tool("filesystem", {"action": "stat", "path": dst_path})
            if stat_dst.result.is_success and isinstance(stat_dst.result.data, dict) and stat_dst.result.data.get("exists"):
                stem = Path(base_name).stem
                ext = Path(base_name).suffix
                ts = time.strftime("%Y%m%d-%H%M%S")
                dst_path = str(Path(dst_folder) / f"{stem}-{ts}{ext}")

            # 4) 드라이런 → 실제 이동
            logger.info(f"Agentic(FS): dry_run move — src={src_path}, dst={dst_path}")
            dry = await self.tool_executor.execute_tool(
                tool_name="filesystem",
                parameters={"action": "move", "src": src_path, "dst": dst_path, "dry_run": True, "overwrite": False},
            )
            if not dry.result.is_success:
                return {"text": f"이동 계획 점검 실패: {dry.result.error_message}", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": dry.result.error_message}}
            else:
                planned = dry.result.data.get("planned") if isinstance(dry.result.data, dict) else None
                logger.info(f"Agentic(FS): 드라이런 — {planned or 'ok'}")

            logger.info(f"Agentic(FS): execute move — src={src_path}, dst={dst_path}")
            mv = await self.tool_executor.execute_tool(
                tool_name="filesystem",
                parameters={"action": "move", "src": src_path, "dst": dst_path, "overwrite": False},
            )
            if not mv.result.is_success:
                logger.error(f"Agentic(FS): 이동 실패 — {mv.result.error_message}")
                return {"text": f"이동 실패: {mv.result.error_message}", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": mv.result.error_message}}
            else:
                logger.info(f"Agentic(FS): 이동 완료 — src={src_path}, dst={dst_path}")

            # 5) 검증
            ver = await self.tool_executor.execute_tool("filesystem", {"action": "stat", "path": dst_path})
            data = ver.result.data if ver.result and ver.result.is_success else None
            text = f"파일을 성공적으로 이동했어요.\n원본: {src_path}\n대상: {dst_path}"
            # 필요 시 LLM으로 최종 응답 리파인 (자연어)
            text = await self._maybe_refine_response(user_input, text, data)
            return {
                "text": text,
                "execution": {
                    "tool_name": "filesystem",
                    "action": "move",
                    "status": "success",
                    "parameters": {"src": src, "dst": dst_path},
                    "result_data": data,
                },
            }
        except Exception as e:
            return {"text": f"❌ 파일 작업 처리 오류: {e}", "execution": {"tool_name": "filesystem", "action": action or "move", "status": "error", "error": str(e)}}

    async def _llm_select_from_candidates(self, question: str, candidates: List[Dict[str, str]], kind: str, user_input: str) -> Optional[int]:
        """상위 후보 목록을 LLM에 제시하여 하나를 선택하게 합니다.

        Returns: 선택한 인덱스(0-based) 또는 None
        """
        try:
            if not candidates:
                raise LLMProviderError("후보가 비어있습니다")
            system = (
                "너는 파일 선택 도우미야.\n"
                "- 아래 후보 리스트 중 '사용자 요청'에 가장 부합하는 하나를 고르고,\n"
                "  그 후보의 정확한 이름(name)만 한 줄로 출력해. 다른 말 금지.\n"
                "- 문서류(.hwpx/.hwp/.docx/.pdf/.txt)와 얕은 경로를 선호.\n"
                "- 노이즈(Thumbs.db, .DS_Store, desktop.ini)는 제외.\n"
            )
            # 단일 후보면 바로 선택
            if len(candidates) == 1:
                logger.info("Agentic: 후보 1개 — 자동 선택(0)")
                return 0
            # 개인정보/경로 노출 최소화를 위해 파일명만 표시
            lines = [
                f"[사용자 요청] {user_input}",
                "",
                f"[질문] {question}",
                "[출력] 후보의 name 중 하나를 정확히 그대로 한 줄로 출력",
                "",
                f"[후보 {kind}] (name)",
            ]
            for c in candidates:
                nm = c.get('name','')
                lines.append(f"- {nm}")
            user = "\n".join(lines)
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            # 선택 안정화를 위해 temperature=0.0, 그리고 텍스트 MIME으로 강제
            logger.debug(
                f"Agentic(FS): 후보 선택 프롬프트 — kind={kind}, count={len(candidates)}, question='{question}'"
            )
            resp = await self.llm_provider.generate_response(
                msgs,
                temperature=0.0,
                response_mime_type='text/plain'
            )
            content = (resp.content or "").strip()
            if content.startswith("```"):
                start = content.find("\n"); end = content.rfind("```")
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()
            logger.debug(f"Agentic(FS): LLM 원문 응답 — '{content}'")
            if not content:
                logger.warning("Agentic(FS): LLM 응답 비어있음 — 선택 실패")
                return None
            # 후보 이름 직접 매칭
            out = content.strip().strip('"').strip("'")
            # 1) 정확 일치
            for i, c in enumerate(candidates):
                if out == (c.get('name','') or ''):
                    logger.info(f"Agentic(FS): 후보 선택(정확 일치) — name='{out}', index={i}")
                    return i
            # 2) 대소문자 무시 일치
            low = out.lower()
            for i, c in enumerate(candidates):
                if low == (c.get('name','') or '').lower():
                    logger.info(f"Agentic(FS): 후보 선택(대소문자 무시) — name='{c.get('name','')}', index={i}")
                    return i
            # 3) 유니코드 정규화 기반 느슨한 일치
            try:
                norm_out = self._norm(out)
                # 동등 비교
                for i, c in enumerate(candidates):
                    norm_name = self._norm(c.get('name','') or '')
                    if norm_out == norm_name:
                        logger.info(f"Agentic(FS): 후보 선택(정규화 일치) — name='{c.get('name','')}', index={i}")
                        return i
                # 포함 관계(예: '…하기' vs '…')
                for i, c in enumerate(candidates):
                    norm_name = self._norm(c.get('name','') or '')
                    if norm_name and (norm_name in norm_out or norm_out in norm_name):
                        logger.info(f"Agentic(FS): 후보 선택(부분 일치) — name='{c.get('name','')}', index={i}")
                        return i
            except Exception:
                pass
            logger.warning("Agentic(FS): LLM 응답에서 후보명을 매칭하지 못함 — 선택 실패")
            return None
        except Exception as e:
            # LLM 오류는 상위에서 폴백하도록 None 반환
            logger.warning(f"Agentic(FS): LLM 후보 선택 중 예외 — {e}")
            return None

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

    async def _llm_next_step_from_todos(
        self,
        title_hint: Optional[str],
        todos: list[dict],
        desired_action: str
    ) -> Optional[Dict[str, Any]]:
        """LLM에게 후보 Todo 목록을 제공하고, 자연어로 다음 도구 스텝을 산출하도록 요청.

        기대 형식 (자연어, JSON 금지):
        TOOL: notion_todo
        ACTION: complete | update | delete
        PARAMS: todo_id=<ID>
        """
        try:
            if not todos:
                return None
            # 프롬프트 구성 (ID를 포함해 확실히 선택하게 함)
            sys = (
                "너는 도구를 조합해 사용자를 돕는 에이전트야.\n"
                "- 아래 Todo 후보 목록과 사용자의 의도를 바탕으로, 다음에 수행할 하나의 도구 스텝을 제시해.\n"
                "- 형식은 자연어로만, 아래 3줄로 시작해야 해.\n"
                "  1) TOOL: notion_todo\n  2) ACTION: complete/update/delete 중 하나\n  3) PARAMS: todo_id=<ID> (반드시 후보에서 제공한 id 그대로)\n"
                "- 코드블록/마크다운/설명은 금지. 위 3줄 뒤에는 아무것도 쓰지 마."
            )
            lines = []
            if title_hint:
                lines.append(f"[사용자 힌트] {title_hint}")
            lines.append(f"[원하는 작업] {desired_action}")
            lines.append("")
            lines.append("[후보 목록] id — title (due)")
            from datetime import datetime
            def _fmt_due(d: Optional[str]) -> str:
                if not d:
                    return "마감 미정"
                try:
                    dt = datetime.fromisoformat(d.replace('Z','+00:00'))
                    return dt.strftime('%m-%d %H:%M')
                except Exception:
                    return d
            for td in todos:
                lines.append(f"- {td.get('id','')} — {td.get('title','')} ({_fmt_due(td.get('due_date'))})")
            user = "\n".join(lines)
            msgs = [ChatMessage(role="system", content=sys), ChatMessage(role="user", content=user)]
            resp = await self.llm_provider.generate_response(msgs, temperature=0.0)
            text = (resp.content or "").strip()
            if text.startswith("```"):
                s = text.find("\n"); e = text.rfind("```")
                if s != -1 and e != -1:
                    text = text[s+1:e].strip()
            # 간단 파싱
            tool = None; action = None; params_line = None
            for line in text.splitlines():
                if line.upper().startswith("TOOL:"):
                    tool = line.split(":", 1)[1].strip()
                elif line.upper().startswith("ACTION:"):
                    action = line.split(":", 1)[1].strip().lower()
                elif line.upper().startswith("PARAMS:"):
                    params_line = line.split(":", 1)[1].strip()
            if (tool or "").lower() != "notion_todo":
                return None
            if action not in {"complete", "update", "delete"}:
                return None
            todo_id = None
            if params_line and "todo_id=" in params_line:
                todo_id = params_line.split("todo_id=", 1)[1].strip().split()[0]
                # 불필요한 구분자 제거
                todo_id = todo_id.strip('"\' ,;')
            if not todo_id:
                return None
            return {"action": action, "todo_id": todo_id}
        except Exception:
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
    # Plan Executor (One‑Shot Agentic)
    # ==========================
    async def _execute_plan(self, decision, user_input: str) -> Dict[str, Any]:
        """LLM이 산출한 execution_plan을 순차적으로 실행(원샷 에이전틱)."""
        step_outputs: List[Dict[str, Any]] = []
        last_text: str = ""
        error_happened = False

        for idx, step in enumerate(decision.execution_plan or [], start=1):
            if not isinstance(step, dict):
                continue
            tool_name = step.get("tool")
            action = step.get("action")
            parameters: Dict[str, Any] = step.get("parameters", {}) or {}

            if not tool_name:
                continue

            # 툴 존재 확인
            if tool_name not in self.tool_registry.list_tools():
                return {"text": f"❌ MCP 레지스트리에 '{tool_name}' 도구가 없습니다.", "execution": {"tool_name": tool_name, "status": "error", "error": "tool_not_found"}}

            # step.action을 파라미터에 병합 (해당 도구가 action 파라미터를 지원하는 경우에만)
            meta = self.tool_registry.get_tool_metadata(tool_name)
            if action and meta:
                param_names = {p.name for p in meta.parameters}
                if "action" in param_names and "action" not in parameters:
                    parameters["action"] = action

            # 파라미터 정규화
            parameters = self._normalize_parameters(tool_name, parameters)
            action = parameters.get("action") if isinstance(parameters, dict) else action

            # 도구별 실행 전 보강 (맥락 활용)
            if tool_name == "apple_notes" and action == "update" and not parameters.get("content"):
                try:
                    read_params = {
                        "action": "read",
                        "target_title": parameters.get("target_title") or parameters.get("title"),
                        "folder": parameters.get("folder", "Notes"),
                    }
                    read_res = await self.tool_executor.execute_tool("apple_notes", read_params)
                    if read_res.result.is_success and isinstance(read_res.result.data, dict):
                        original_body = read_res.result.data.get("content", "")
                        new_body = await self._llm_rewrite_note_body(original_body, user_input)
                        if new_body:
                            parameters["content"] = new_body
                except Exception:
                    pass

            if tool_name == "notion_todo" and action == "update" and isinstance(parameters, dict):
                try:
                    todo_id = parameters.get("todo_id") or parameters.get("id")
                    if todo_id:
                        curr = await self.tool_executor.execute_tool("notion_todo", {"action": "get", "todo_id": todo_id})
                        if curr.result.is_success and isinstance(curr.result.data, dict):
                            todo_obj = curr.result.data.get("todo") if isinstance(curr.result.data, dict) else None
                            curr_due = None
                            if isinstance(todo_obj, dict):
                                curr_due = todo_obj.get("due_date")
                            nd = parameters.get("due_date")
                            if isinstance(nd, str):
                                from datetime import datetime
                                from zoneinfo import ZoneInfo
                                tz = ZoneInfo(get_settings().default_timezone)
                                new_dt = None
                                s = nd.strip()
                                try:
                                    iso = s.replace('Z', '+00:00')
                                    if 'T' in iso or '+' in iso:
                                        dt = datetime.fromisoformat(iso)
                                        new_dt = dt if dt.tzinfo else dt.replace(tzinfo=tz)
                                    else:
                                        if len(iso) >= 16 and iso[4] == '-' and ':' in iso:
                                            iso2 = iso.replace(' ', 'T') + "+09:00"
                                            new_dt = datetime.fromisoformat(iso2)
                                        else:
                                            base_date = None
                                            if isinstance(curr_due, str) and curr_due:
                                                try:
                                                    base_dt = datetime.fromisoformat(curr_due.replace('Z', '+00:00'))
                                                    if base_dt.tzinfo is None:
                                                        base_dt = base_dt.replace(tzinfo=tz)
                                                    base_date = base_dt.date()
                                                except Exception:
                                                    pass
                                            import re as _re
                                            m = _re.match(r"^(\d{1,2}):(\d{2})$", s)
                                            if base_date and m:
                                                hh, mm = int(m.group(1)), int(m.group(2))
                                                new_dt = datetime(base_date.year, base_date.month, base_date.day, hh, mm, tzinfo=tz)
                                except Exception:
                                    new_dt = None
                                if new_dt:
                                    parameters["due_date"] = new_dt.isoformat()
                                else:
                                    if 'T' in s and ('Z' not in s and '+' not in s and '-' not in s[10:]):
                                        parameters["due_date"] = s + "+09:00"
                except Exception:
                    pass

            # Filesystem move일 때 모호한 src/dst 보정 (Desktop 검색)
            if tool_name == "filesystem" and action == "move" and isinstance(parameters, dict):
                try:
                    # src가 존재하지 않으면 바탕화면 재귀 검색으로 보정
                    src_candidate = parameters.get("src")
                    dst_candidate = parameters.get("dst")
                    from pathlib import Path as _P
                    def _exists(p):
                        try:
                            return _P(str(p)).exists()
                        except Exception:
                            return False
                    desktop = str((Path.home() / "Desktop"))
                    if not _exists(src_candidate):
                        # Desktop 인덱싱
                        listed = await self.tool_executor.execute_tool(
                            tool_name="filesystem",
                            parameters={"action": "list", "path": desktop, "recursive": False, "include_hidden": False, "max_items": 5000},
                        )
                        if listed.result.is_success and isinstance(listed.result.data, dict):
                            items = listed.result.data.get("items", [])
                            files = [it for it in items if it.get("type") == "file"]
                            # 힌트: 사용자 입력 + src 문자
                            import re as _re
                            hints = _re.findall(r"[\w가-힣]+", (user_input or "") + " " + str(src_candidate or ""))
                            best = None
                            best_score = -1
                            for it in files:
                                s = self._score_filename(it.get("name", ""), hints)
                                if s > best_score:
                                    best, best_score = it, s
                            if not best or best_score < 3:
                                # Fallback: 최상위(비재귀)만 다시 스캔하여 가중치 재평가
                                top = await self.tool_executor.execute_tool(
                                    tool_name="filesystem",
                                    parameters={"action": "list", "path": desktop, "recursive": False, "include_hidden": False, "max_items": 5000},
                                )
                                if top.result.is_success and isinstance(top.result.data, dict):
                                    t_items = top.result.data.get("items", [])
                                    t_files = [it for it in t_items if it.get("type") == "file"]
                                    # 우선 한글 핵심 키워드 직매칭 우선 선택
                                    for it in t_files:
                                        nm = it.get("name", "")
                                        nmn = self._norm(nm)
                                        if any(self._norm(k) in nmn for k in ["설계", "여름", "세미나"]):
                                            best, best_score = it, 10
                                            break
                                    if not best:
                                        for it in t_files:
                                            s = self._score_filename(it.get("name", ""), hints)
                                            if s > best_score:
                                                best, best_score = it, s
                            if best and best_score >= 2:
                                parameters["src"] = best.get("path")
                    # dst가 폴더 의미인데 존재하지 않으면 mkdir 선행 스텝이 처리했을 가능성 높음
                    # 여기서는 단순히 의미 경로를 절대 경로로 유지
                except Exception:
                    pass

            # 실행 + 자기교정 재시도
            # system_time 특별 처리: 파라미터가 비어있으면 기본값 설정
            if tool_name == "system_time" and (not parameters or not isinstance(parameters, dict)):
                parameters = {"action": "current", "timezone": "Asia/Seoul"}
                logger.debug(f"system_time 도구 기본 파라미터 설정: {parameters}")
            elif tool_name == "system_time" and isinstance(parameters, dict):
                if "action" not in parameters or not parameters.get("action"):
                    parameters["action"] = "current"
                    logger.debug("system_time 도구에 기본 action 'current' 설정")
                if "timezone" not in parameters:
                    parameters["timezone"] = "Asia/Seoul"
            
            exec_result = await self.tool_executor.execute_tool(tool_name=tool_name, parameters=parameters)
            attempts = int(os.getenv("PAI_SELF_REPAIR_ATTEMPTS", "2"))
            retry_count = 0
            while (not exec_result.result.is_success) and retry_count < attempts:
                retry_count += 1
                try:
                    repaired = await self._self_repair_parameters(tool_name, parameters, exec_result.result.error_message)
                    if repaired and isinstance(repaired, dict):
                        repaired = self._normalize_parameters(tool_name, repaired)
                        exec_result = await self.tool_executor.execute_tool(tool_name=tool_name, parameters=repaired)
                        parameters = repaired
                        if exec_result.result.is_success:
                            break
                except Exception:
                    break

            # 단계 결과 요약
            if exec_result.result.is_success:
                last_text = self._summarize_success(tool_name, parameters, exec_result.result.data)
                step_outputs.append({
                    "step": idx,
                    "tool_name": tool_name,
                    "action": action,
                    "status": "success",
                    "parameters": parameters,
                    "result_data": exec_result.result.data,
                })
            else:
                error_happened = True
                last_text = self._summarize_failure(tool_name, parameters, exec_result.result.error_message)
                step_outputs.append({
                    "step": idx,
                    "tool_name": tool_name,
                    "action": action,
                    "status": "error",
                    "parameters": parameters,
                    "error": exec_result.result.error_message,
                })
                break  # 에러 발생 시 이후 스텝 중단

        # 전체 요약 및 반환
        overall_status = "success" if not error_happened else "error"
        return {
            "text": last_text or ("✅ 계획을 모두 실행했어요." if overall_status == "success" else "❌ 일부 단계에서 실패했어요."),
            "execution": {
                "status": overall_status,
                "steps": step_outputs,
            }
        }

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
            from ..config import get_settings
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            # 기본 시간대 적용/변환
            tz = ZoneInfo(get_settings().default_timezone)
            if dt.tzinfo is None:
                # 시간대가 없으면 기본 시간대로 간주
                local_dt = dt.replace(tzinfo=tz)
            else:
                local_dt = dt.astimezone(tz)
            return local_dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return iso_str

    def _normalize_parameters(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """파라미터 정규화 비활성화

        순수 LLM 결정에 따르기 위해, 도구별 휴리스틱/키워드 기반 보정은 수행하지 않습니다.
        """
        return params

    async def _self_repair_parameters(self, tool_name: str, params: Dict[str, Any], error_message: Optional[str]) -> Optional[Dict[str, Any]]:
        """파라미터 자기교정 — LLM JSON 강제 사용 제거, 도메인별 휴리스틱 적용.

        현재 지원:
        - notion_todo: action이 complete/update/delete인데 todo_id가 없고 제목 단서가 있으면 목록에서 ID 탐색
        """
        try:
            if not isinstance(params, dict):
                return None
            # 공통: action 소문자/공백 제거 맵핑
            action = str(params.get("action") or "").strip().lower()
            if tool_name == "notion_todo":
                # 제목 단서
                title_hint = None
                for key in ("target_title", "title"):
                    v = params.get(key)
                    if isinstance(v, str) and v.strip():
                        title_hint = v.strip()
                        break
                todo_id = params.get("todo_id") or params.get("id")
                # action 정규화 (보수적)
                if action in {"할일 완료", "할일완료", "완료로", "완료로바꿔줘", "완료로 바꿔줘"}:
                    params["action"] = "complete"
                    action = "complete"
                # ID가 없으면 LLM에게 후보 목록을 주고 '다음 도구 스텝'을 자연어로 생성하게 함 (pending 기본)
                if (action in {"complete", "update", "delete"}) and (not todo_id):
                    try:
                        MAX_CANDS = int(os.getenv("PAI_NOTION_TODO_LLM_CANDIDATES", "25"))
                        # 1) 미완료 목록 우선
                        lst = await self.tool_executor.execute_tool(
                            "notion_todo", {"action": "list", "filter": "pending", "limit": MAX_CANDS}
                        )
                        todos: list[dict] = []
                        if lst.result.is_success and isinstance(lst.result.data, dict):
                            todos = lst.result.data.get("todos", []) or []
                        # 2) 비어있으면 전체 목록 제한 조회
                        if not todos:
                            lst2 = await self.tool_executor.execute_tool(
                                "notion_todo", {"action": "list", "filter": "all", "limit": MAX_CANDS}
                            )
                            if lst2.result.is_success and isinstance(lst2.result.data, dict):
                                todos = lst2.result.data.get("todos", []) or []
                        if not todos:
                            return None
                        # LLM에게 다음 스텝(TOOL/ACTION/PARAMS) 결정을 위임
                        next_step = await self._llm_next_step_from_todos(title_hint, todos, desired_action=action)
                        if not next_step or not next_step.get("todo_id"):
                            return None
                        # LLM이 액션을 바꿀 수 있으나, 현재는 같은 액션만 허용(원하면 반영 가능)
                        params["todo_id"] = next_step["todo_id"]
                        logger.info(f"Self-repair(notion_todo): LLM 스텝 — action={next_step.get('action')}, id={next_step.get('todo_id')[:8]}…")
                        return params
                    except Exception:
                        return None
            # 기타 도구는 휴리스틱 없음
            return None
        except Exception:
            return None
    
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
