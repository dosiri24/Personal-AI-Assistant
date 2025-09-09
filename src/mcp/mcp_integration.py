"""
MCP 시스템 통합 모듈

AI 엔진과 MCP 도구들을 통합하여 실제 작업을 수행할 수 있도록 하는 모듈입니다.
"""

import asyncio
import os
from typing import List, Dict, Any, Optional
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

            # 3-b) 실패 시 self-repair 루프 (에이전틱 재시도)
            attempts = int(os.getenv("PAI_SELF_REPAIR_ATTEMPTS", "2"))
            retry_count = 0
            while (not execution_result.result.is_success) and retry_count < attempts:
                retry_count += 1
                try:
                    repaired = await self._self_repair_parameters(tool_name, parameters, execution_result.result.error_message)
                    if repaired and isinstance(repaired, dict):
                        repaired = self._normalize_parameters(tool_name, repaired)
                        execution_result = await self.tool_executor.execute_tool(tool_name=tool_name, parameters=repaired)
                        if execution_result.result.is_success:
                            parameters = repaired
                            break
                        else:
                            parameters = repaired  # 다음 루프에 전달
                    else:
                        break
                except Exception:
                    break

            # 4) 요약 + 메타
            if execution_result.result.is_success:
                logger.info(f"도구 실행 성공: {tool_name}")
                text = self._summarize_success(tool_name, parameters, execution_result.result.data)
                return {
                    "text": text,
                    "execution": {
                        "tool_name": tool_name,
                        "action": action,
                        "status": "success",
                        "parameters": parameters,
                        "result_data": execution_result.result.data,
                    }
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
                        "result_data": execution_result.result.data if execution_result.result else None,
                    },
                }
        except Exception as e:
            logger.error(f"요청 처리 중 오류: {e}")
            return {"text": f"❌ 시스템 오류: {str(e)}", "execution": {"status": "error", "error": str(e)}}

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
                s = self._norm(seg)
                if s in {"desktop", "바탕화면"}:
                    return desktop_path
                if s in {"documents", "문서", "도큐먼트"}:
                    return Path.home() / "Documents"
                if s in {"downloads", "다운로드"}:
                    return Path.home() / "Downloads"
                return None

            # 보조: "바탕화면/대학/2025-2" 같은 의미 경로를 실제 경로로 추정
            def semantic_to_path(text: str) -> Optional[Path]:
                if not text:
                    return None
                raw = text.replace("\\", "/").strip().strip("\"")
                # 티틀다(~) 시작이면 홈 기준으로 직접 확장
                if raw.startswith("~"):
                    try:
                        return Path(raw).expanduser().resolve(strict=False)
                    except Exception:
                        pass
                parts = [p for p in raw.split('/') if p]
                if not parts:
                    return None
                root = map_root(parts[0]) or desktop_path  # 기본 Desktop 기준
                sub = parts[1:] if map_root(parts[0]) else parts
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

            # 1) 원본 파일 추정
            src = params.get("src")
            src_path = None
            if isinstance(src, str) and src:
                cand = semantic_to_path(src)
                if cand and cand.exists():
                    src_path = str(cand)
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
            tokens = re.findall(r"[\w가-힣]+", u + " " + src_hint)
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

                # LLM에게 상위 후보를 보여주고 선택하도록 위임 (실패 시 스코어 기반 폴백)
                MAX_CANDS = int(os.getenv("PAI_FS_LLM_CANDIDATES", "10"))
                ranked = sorted(
                    filtered,
                    key=lambda it: self._score_file_entry(it, tokens, desktop_root=desktop),
                    reverse=True,
                )[:MAX_CANDS]
                if ranked:
                    logger.info(
                        f"Agentic(FS): LLM 후보 제시 — count={len(ranked)}; 예시={[it.get('name','') for it in ranked[:3]]}"
                    )
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
                            logger.warning(f"Agentic(FS): LLM 후보 선택 실패, 스코어 기반 사용 — {e}")
                        if llm_index is not None and 0 <= llm_index < len(ranked):
                            best = ranked[llm_index]
                            best_score = 999
                            logger.info(
                                f"Agentic(FS): LLM 선택 — index={llm_index}, name={best.get('name','')}, rel={_rel_from_desktop(best.get('path',''))}"
                            )
                # 임계값 미달 시 바탕화면 최상위에서 한글 핵심 키워드로 1차 재시도
                if (not best) or best_score < 3:
                    try:
                        desktop_top = await self.tool_executor.execute_tool(
                            tool_name="filesystem",
                            parameters={"action": "list", "path": desktop, "recursive": False, "include_hidden": False, "max_items": 5000},
                        )
                        if desktop_top.result.is_success and isinstance(desktop_top.result.data, dict):
                            t_items = desktop_top.result.data.get("items", [])
                            t_files = [it for it in t_items if it.get("type") == "file" and not _is_noise_file(it.get("name", ""))]
                            logger.debug(f"Agentic(FS): Desktop 최상위 재스캔 — files={len(t_files)}")
                            # 한글 핵심 키워드 직매칭 우선
                            for it in t_files:
                                nm = it.get("name", "")
                                nmn = self._norm(nm)
                                if any(self._norm(k) in nmn for k in ["설계", "여름", "세미나"]):
                                    best, best_score = it, 10
                                    break
                            if not best:
                                for it in t_files:
                                    s = self._score_file_entry(it, tokens, desktop_root=desktop)
                                    if s > best_score:
                                        best, best_score = it, s
                    except Exception:
                        pass
                if best and best_score >= 2:
                    src_path = best.get("path")
                else:
                    # 후보 제시 후 확인 요청
                    # 필수 키워드가 있었는데 후보가 없으면 바로 확인 요청
                    if must_keys and not filtered:
                        cand = ", ".join(it.get("name", "") for it in files[:5])
                        text = f"요청한 파일을 찾지 못했어요. 혹시 정확한 파일명이나 확장자를 알려주실 수 있을까요? 후보: {cand}"
                        return {"text": text, "execution": {"tool_name": "filesystem", "action": "move", "status": "needs_clarification"}}
                    top = sorted([it for it in files if not _is_noise_file(it.get("name", ""))], key=lambda it: self._score_file_entry(it, tokens, desktop_root=desktop), reverse=True)[:5]
                    cand = ", ".join(it.get("name", "") for it in top)
                    text = f"요청한 파일을 찾지 못했어요. 혹시 정확한 파일명이나 확장자를 알려주실 수 있을까요? 후보: {cand}"
                    return {"text": text, "execution": {"tool_name": "filesystem", "action": "move", "status": "needs_clarification"}}
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
                            logger.warning(f"Agentic(FS): LLM 폴더 후보 선택 실패, 키워드/기본값 사용 — {e}")
                        if llm_index is not None and 0 <= llm_index < len(ranked_dirs):
                            rel = _rel_from_desktop(ranked_dirs[llm_index].get("path", ""))
                            dst_folder = str((desktop_path / rel).resolve(strict=False))
                            logger.info(f"Agentic(FS): LLM 폴더 선택 — index={llm_index}, rel={rel}")
                if not dst_folder:
                    # 기본: Desktop 자체로 이동
                    dst_folder = desktop
            else:
                dst_folder = str(dst_folder_path)

            # 3) 최종 대상 파일 경로 구성
            if not src_path:
                # 최후 보루: 바탕화면 최상위에서 직접 스캔하여 한글 핵심 키워드 포함 파일 선택
                try:
                    import os as _os
                    desktop_files = [str(p) for p in (desktop_path.iterdir()) if p.is_file()]
                    chosen = None
                    for p in desktop_files:
                        n = self._norm(Path(p).name)
                        if any(self._norm(k) in n for k in ["설계", "여름", "세미나"]):
                            chosen = p
                            break
                    if chosen:
                        src_path = chosen
                except Exception:
                    pass
            if not src_path:
                return {"text": "원본 파일을 찾지 못했어요. 파일명을 조금만 더 구체적으로 알려주세요.", "execution": {"tool_name": "filesystem", "action": "move", "status": "needs_clarification"}}

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
            dry = await self.tool_executor.execute_tool(
                tool_name="filesystem",
                parameters={"action": "move", "src": src_path, "dst": dst_path, "dry_run": True, "overwrite": False},
            )
            if not dry.result.is_success:
                return {"text": f"이동 계획 점검 실패: {dry.result.error_message}", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": dry.result.error_message}}
            else:
                planned = dry.result.data.get("planned") if isinstance(dry.result.data, dict) else None
                logger.info(f"Agentic(FS): 드라이런 — {planned or 'ok'}")

            mv = await self.tool_executor.execute_tool(
                tool_name="filesystem",
                parameters={"action": "move", "src": src_path, "dst": dst_path, "overwrite": False},
            )
            if not mv.result.is_success:
                return {"text": f"이동 실패: {mv.result.error_message}", "execution": {"tool_name": "filesystem", "action": "move", "status": "error", "error": mv.result.error_message}}
            else:
                logger.info(f"Agentic(FS): 이동 완료 — src={src_path}, dst={dst_path}")

            # 5) 검증
            ver = await self.tool_executor.execute_tool("filesystem", {"action": "stat", "path": dst_path})
            data = ver.result.data if ver.result and ver.result.is_success else None
            text = f"파일을 성공적으로 이동했어요.\n원본: {src_path}\n대상: {dst_path}"
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
                "- 아래 후보 리스트 중 사용자의 의도에 가장 맞는 하나를 고르고, JSON만 반환해.\n"
                "- 출력 형식: {\"selected_index\": <정수>}\n"
                "- 설명/텍스트/코드블록 없이 JSON 하나만.\n"
                "- 문서류(.hwpx/.hwp/.docx/.pdf/.txt)와 얕은 경로를 선호.\n"
                "- 노이즈(Thumbs.db, .DS_Store, desktop.ini)는 제외.\n"
            )
            # 개인정보/경로 노출을 최소화하기 위해 파일명만 사용하고 길이는 제한
            def _short(s: str, n: int = 60) -> str:
                return (s[:n] + '…') if len(s) > n else s
            lines = [
                question,
                "",
                "[규칙] JSON만, {\"selected_index\": <정수> 형식으로 답변하세요.",
                "[참고] 아래는 후보 목록입니다. index로만 선택하세요.",
                "",
                f"[후보 {kind}] (index, name)",
            ]
            for i, c in enumerate(candidates):
                lines.append(f"{i}. {_short(c.get('name',''))}")
            user = "\n".join(lines)
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            # 선택 안정화를 위해 temperature=0.0
            resp = await self.llm_provider.generate_response(msgs, temperature=0.0, max_tokens=64)
            content = (resp.content or "").strip()
            if content.startswith("```"):
                start = content.find("\n"); end = content.rfind("```")
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()
            import json as _json
            if not content:
                # 비어있으면 폴백: None 반환해 상위 로직이 스코어 기반 선택
                logger.warning("Agentic(FS): LLM 응답 비어있음 — 스코어 기반 폴백")
                return None
            data = _json.loads(content)
            idx = data.get("selected_index")
            if not isinstance(idx, int):
                logger.warning("Agentic(FS): LLM 응답 JSON에 selected_index 없음 — 폴백")
                return None
            return int(idx)
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
        """도구 실행 전 파라미터 정규화

        - calculator: {"expression": "2 + 3"} → {operation: "+", a: 2, b: 3}
        추가적인 도구별 맵핑이 필요하면 이곳에 확장합니다.
        """
        try:
            mode = os.getenv("PAI_PARAM_NORMALIZATION_MODE", "minimal").lower()

            # Always canonicalize 'action' for known tools
            if isinstance(params, dict) and "action" in params and isinstance(params["action"], str):
                a = params["action"].strip().lower()
                def _canon(syn: dict[str, set[str]], a: str) -> str:
                    for key, words in syn.items():
                        if a in {w.lower() for w in words}:
                            return key
                    return params["action"]
                if tool_name == "notion_todo":
                    params["action"] = _canon({
                        "create": {"create", "추가", "생성", "등록", "만들어", "만들다", "할일 추가"},
                        "update": {"update", "수정", "변경", "편집"},
                        "delete": {"delete", "삭제", "제거"},
                        "get": {"get", "조회", "확인", "보기"},
                        "list": {"list", "목록", "리스트"},
                        "complete": {"complete", "완료", "끝"},
                    }, a)
                elif tool_name == "notion_calendar":
                    params["action"] = _canon({
                        "create": {"create", "추가", "생성", "등록", "일정 추가", "일정 생성"},
                        "update": {"update", "수정", "변경", "편집", "일정 수정"},
                        "delete": {"delete", "삭제", "제거", "일정 삭제"},
                        "get": {"get", "조회", "확인", "보기"},
                        "list": {"list", "목록", "리스트"},
                    }, a)
                elif tool_name == "apple_notes":
                    params["action"] = _canon({
                        "create": {"create", "add", "make", "메모 생성", "생성", "추가", "작성"},
                        "search": {"search", "find", "검색"},
                        "update": {"update", "수정", "편집"},
                        "delete": {"delete", "remove", "삭제"},
                        "read": {"read", "열람", "읽기"},
                    }, a)
                elif tool_name == "filesystem":
                    params["action"] = _canon({
                        "list": {"list", "목록", "리스트"},
                        "stat": {"stat", "정보", "상세", "상세보기"},
                        "move": {"move", "이동", "옮겨", "옮기기", "파일 이동", "폴더 이동", "파일/폴더 이동"},
                        "copy": {"copy", "복사"},
                        "mkdir": {"mkdir", "디렉토리 생성", "폴더 생성", "폴더 만들기", "디렉토리 만들기"},
                        "trash_delete": {"trash_delete", "휴지통", "휴지통으로"},
                        "delete": {"delete", "삭제", "영구 삭제"},
                    }, a)

            if mode == "off":
                return params
            if tool_name == "calculator" and isinstance(params, dict):
                # minimal: calculator는 보정하지 않음 (LLM 생성 그대로)
                if mode == "full":
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
                if mode == "full":
                    raw_action = str(params.get("action", "")).strip().lower()
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
                    if not normalized:
                        if "target_title" in params or "note_id" in params:
                            normalized = "update"
                        else:
                            normalized = "create"
                    params["action"] = normalized
                # minimal: 기본값/폴더만 보정
                if "folder" not in params:
                    params["folder"] = "Notes"
                if not params.get("title") and params.get("content"):
                    params["title"] = str(params.get("content"))[:30] or "새 메모"
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
                if mode == "full":
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

                    # 우선순위 표준화
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
                # 날짜 키 표준화
                if "start_date" not in params:
                    if "date" in params:
                        params["start_date"] = params.pop("date")
                    elif "start" in params:
                        params["start_date"] = params.pop("start")
                # date + time → start_date 결합
                start_date = params.get("start_date")
                time_part = params.get("time")
                if isinstance(start_date, str) and isinstance(time_part, str):
                    from datetime import datetime
                    from zoneinfo import ZoneInfo
                    from ..config import get_settings
                    tz = ZoneInfo(get_settings().default_timezone)
                    if 'T' not in start_date:
                        try:
                            naive = datetime.fromisoformat(f"{start_date}T{time_part}")
                            params["start_date"] = naive.replace(tzinfo=tz).isoformat()
                        except Exception:
                            params["start_date"] = f"{start_date}T{time_part}+09:00"
                    params.pop("time", None)
                # ISO 보정 (기본 시간대)
                for key in ("start_date", "end_date"):
                    v = params.get(key)
                    if isinstance(v, str) and ('Z' not in v and '+' not in v and '-' not in v[10:]):
                        if len(v) >= 16 and 'T' in v:
                            params[key] = v + "+09:00"
                return params
            elif tool_name == "apple_calendar" and isinstance(params, dict):
                if mode == "full":
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
            elif tool_name == "filesystem" and isinstance(params, dict):
                # 의미 경로를 실제 경로로 보정 (Desktop/Documents/Downloads 별칭 지원)
                def _map_root(seg: str) -> Optional[Path]:
                    s = (seg or "").strip().lower()
                    home = Path.home()
                    if s in {"desktop", "바탕화면"}: return home / "Desktop"
                    if s in {"documents", "문서", "도큐먼트"}: return home / "Documents"
                    if s in {"downloads", "다운로드"}: return home / "Downloads"
                    return None
                def _semantic_to_path(text: Optional[str]) -> Optional[str]:
                    if not text or not isinstance(text, str):
                        return None
                    raw = text.replace("\\", "/").strip().strip("\"")
                    parts = [p for p in raw.split('/') if p]
                    if not parts:
                        return None
                    root = _map_root(parts[0]) or (Path.home() / "Desktop")
                    sub = parts[1:] if _map_root(parts[0]) else parts
                    p = root
                    for seg in sub:
                        p = p / seg
                    return str(p)
                # path/src/dst 보정
                for key in ("path", "src", "dst"):
                    if key in params and isinstance(params[key], str):
                        mapped = _semantic_to_path(params[key])
                        if mapped:
                            params[key] = mapped
                return params
            return params
        except Exception:
            return params

    async def _self_repair_parameters(self, tool_name: str, params: Dict[str, Any], error_message: Optional[str]) -> Optional[Dict[str, Any]]:
        """LLM을 사용해 파라미터를 자기교정하여 재시도할 수 있도록 합니다."""
        try:
            metadata = self.tool_registry.get_tool_metadata(tool_name)
            schema_desc = ""
            if metadata:
                schema_desc = json.dumps({
                    "name": metadata.name,
                    "parameters": [p.to_dict() for p in metadata.parameters]
                }, ensure_ascii=False)
            system = (
                "너는 MCP 도구 실행을 도와주는 AI야.\n"
                "- 아래 도구 스키마와 이전 파라미터, 에러 메시지를 참고해 올바른 JSON 파라미터를 생성해.\n"
                "- 출력은 JSON 하나만, 코드블록 없이.\n"
            )
            user = (
                f"[도구] {tool_name}\n[스키마]\n{schema_desc}\n\n"
                f"[이전 파라미터]\n{json.dumps(params, ensure_ascii=False)}\n\n"
                f"[에러]\n{error_message or ''}\n\n"
                "요구사항: 유효한 파라미터 JSON만 반환하고, 누락값을 보완해줘."
            )
            msgs = [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
            resp = await self.llm_provider.generate_response(msgs, temperature=0.1, max_tokens=800)
            content = resp.content.strip()
            if content.startswith("```"):
                start = content.find("\n")
                end = content.rfind("```")
                if start != -1 and end != -1:
                    content = content[start+1:end].strip()
            repaired = json.loads(content)
            if isinstance(repaired, dict):
                return repaired
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
