"""
로컬 파일시스템 MCP 도구 (안전 가드레일 포함)

지원 액션
- list: 디렉토리 목록 조회
- stat: 파일/디렉토리 정보 조회
- move: 파일/디렉토리 이동
- copy: 파일/디렉토리 복사(크기 제한, 재귀 옵션)
- mkdir: 디렉토리 생성
- trash_delete: 휴지통으로 이동(macOS: ~/.Trash)
- delete: 영구 삭제(강제 플래그 필요)

보안/안전
- 허용된 루트 디렉토리 내에서만 작업(PAI_FS_ALLOWED_DIRS 환경변수 또는 기본 홈 하위 폴더/프로젝트 data,logs)
- 경로 정규화/상위 경로 차단(resolve)
- copy 크기 제한(기본 50MB, PAI_FS_MAX_COPY_MB로 조정)
- delete는 force=true 필수, 디렉토리 삭제는 recursive=true 필수
- dry_run 지원
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from ..mcp.base_tool import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolResult,
    ParameterType,
    ToolCategory,
    ExecutionStatus,
)
from ..utils.logger import get_logger
from ..config import get_settings


logger = get_logger(__name__)


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def _resolve_safe(p: Path) -> Path:
    # 존재하지 않아도 절대경로화(부모까지 resolve)
    try:
        return p.expanduser().resolve(strict=False)
    except Exception:
        return (Path.cwd() / p).resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path = _resolve_safe(path)
        root = _resolve_safe(root)
        return path == root or root in path.parents
    except Exception:
        return False


def _dir_size_bytes(p: Path, max_items: int = 20000) -> int:
    total = 0
    count = 0
    for root, dirs, files in os.walk(p):
        for f in files:
            try:
                fp = Path(root) / f
                total += fp.stat().st_size
            except Exception:
                pass
            count += 1
            if count > max_items:
                return total
    return total


class FilesystemTool(BaseTool):
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="filesystem",
            version="1.0.0",
            description="로컬 파일시스템에서 안전 가드레일을 적용해 파일/디렉토리 작업을 수행합니다.",
            category=ToolCategory.FILE_MANAGEMENT,
            parameters=[
                ToolParameter(
                    name="action",
                    type=ParameterType.STRING,
                    description="수행할 작업",
                    required=True,
                    choices=[
                        "list",
                        "stat",
                        "move",
                        "copy",
                        "mkdir",
                        "trash_delete",
                        "delete",
                    ],
                ),
                ToolParameter(
                    name="path",
                    type=ParameterType.STRING,
                    description="대상 경로(list/stat/mkdir/delete/trash_delete)",
                    required=False,
                ),
                ToolParameter(
                    name="src",
                    type=ParameterType.STRING,
                    description="원본 경로(move/copy)",
                    required=False,
                ),
                ToolParameter(
                    name="dst",
                    type=ParameterType.STRING,
                    description="대상 경로(move/copy)",
                    required=False,
                ),
                ToolParameter(
                    name="recursive",
                    type=ParameterType.BOOLEAN,
                    description="재귀적으로 처리 여부(list/copy/delete)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="overwrite",
                    type=ParameterType.BOOLEAN,
                    description="대상 경로가 존재할 때 덮어쓰기(move/copy)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="include_hidden",
                    type=ParameterType.BOOLEAN,
                    description="숨김 파일 포함(list)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="max_items",
                    type=ParameterType.INTEGER,
                    description="목록 최대 반환 개수(list)",
                    required=False,
                    default=200,
                    min_value=1,
                    max_value=5000,
                ),
                ToolParameter(
                    name="parents",
                    type=ParameterType.BOOLEAN,
                    description="부모 디렉토리까지 생성(mkdir)",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="force",
                    type=ParameterType.BOOLEAN,
                    description="영구 삭제(delete) 강제 실행 플래그",
                    required=False,
                    default=False,
                ),
                ToolParameter(
                    name="dry_run",
                    type=ParameterType.BOOLEAN,
                    description="실제 실행 없이 계획만 반환",
                    required=False,
                    default=False,
                ),
            ],
            tags=[
                "filesystem",
                "files",
                "move",
                "copy",
                "delete",
                "trash",
                "list",
                "stat",
            ],
            requires_auth=False,
            timeout=20,
        )

    async def _initialize(self) -> None:
        self.settings = get_settings()
        self.allowed_roots: List[Path] = self._compute_allowed_roots()
        self.max_copy_mb = float(os.getenv("PAI_FS_MAX_COPY_MB", "50"))
        logger.info(
            f"FilesystemTool 초기화: roots={[str(p) for p in self.allowed_roots]}, max_copy_mb={self.max_copy_mb}"
        )

    def _compute_allowed_roots(self) -> List[Path]:
        roots: List[Path] = []
        env = os.getenv("PAI_FS_ALLOWED_DIRS", "").strip()
        sep = ":" if os.name != "nt" else ";"
        if env:
            for raw in env.split(sep):
                p = _resolve_safe(_expand(raw))
                if p.exists():
                    roots.append(p)

        # 기본 허용 루트(존재하는 경우만)
        home = Path.home()
        defaults = [
            home / "Documents",
            home / "Downloads",
            home / "Desktop",
            self.settings.get_data_dir(),
            self.settings.get_logs_dir(),
        ]
        for d in defaults:
            if d.exists():
                roots.append(_resolve_safe(d))

        # 중복 제거
        uniq: List[Path] = []
        for r in roots:
            if not any(r == u for u in uniq):
                uniq.append(r)
        return uniq

    def _ensure_allowed(self, *paths: Path) -> Optional[str]:
        for p in paths:
            if not any(_is_within(p, root) for root in self.allowed_roots):
                return f"허용되지 않은 경로입니다: {str(_resolve_safe(p))}"
        return None

    def _to_json_entry(self, p: Path) -> Dict[str, Any]:
        st = None
        try:
            st = p.stat()
        except Exception:
            pass
        return {
            "name": p.name,
            "path": str(p),
            "type": "dir" if p.is_dir() else ("file" if p.is_file() else "other"),
            "size": st.st_size if st else None,
            "modified": datetime.fromtimestamp(st.st_mtime).isoformat() if st else None,
            "created": datetime.fromtimestamp(st.st_ctime).isoformat() if st else None,
            "hidden": p.name.startswith("."),
        }

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = (parameters.get("action") or "").lower()
        dry_run = bool(parameters.get("dry_run", False))

        try:
            if action == "list":
                path = parameters.get("path")
                if not path:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="path가 필요합니다")
                dir_path = _resolve_safe(_expand(path))
                err = self._ensure_allowed(dir_path)
                if err:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message=err)
                if not dir_path.exists() or not dir_path.is_dir():
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="디렉토리가 아닙니다")

                include_hidden = bool(parameters.get("include_hidden", False))
                max_items = int(parameters.get("max_items", 200))
                recursive = bool(parameters.get("recursive", False))

                items: List[Dict[str, Any]] = []
                if recursive:
                    for root, dirs, files in os.walk(dir_path):
                        entries = [Path(root) / d for d in dirs] + [Path(root) / f for f in files]
                        for e in entries:
                            if not include_hidden and e.name.startswith("."):
                                continue
                            items.append(self._to_json_entry(e))
                            if len(items) >= max_items:
                                break
                        if len(items) >= max_items:
                            break
                else:
                    for e in list(dir_path.iterdir())[: max_items * 2]:  # 여유 버퍼 후 필터
                        if not include_hidden and e.name.startswith("."):
                            continue
                        items.append(self._to_json_entry(e))
                        if len(items) >= max_items:
                            break

                return ToolResult(status=ExecutionStatus.SUCCESS, data={"count": len(items), "items": items})

            if action == "stat":
                path = parameters.get("path")
                if not path:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="path가 필요합니다")
                p = _resolve_safe(_expand(path))
                err = self._ensure_allowed(p)
                if err:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message=err)
                info = self._to_json_entry(p)
                info["exists"] = p.exists()
                return ToolResult(status=ExecutionStatus.SUCCESS, data=info)

            if action == "mkdir":
                path = parameters.get("path")
                if not path:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="path가 필요합니다")
                p = _resolve_safe(_expand(path))
                err = self._ensure_allowed(p)
                if err:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message=err)
                parents = bool(parameters.get("parents", False))
                if dry_run:
                    return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"mkdir {'-p ' if parents else ''}{str(p)}"})
                p.mkdir(parents=parents, exist_ok=True)
                return ToolResult(status=ExecutionStatus.SUCCESS, data={"message": f"디렉토리 생성: {str(p)}"})

            if action in {"move", "copy"}:
                src = parameters.get("src")
                dst = parameters.get("dst")
                if not src or not dst:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="src, dst가 필요합니다")
                s = _resolve_safe(_expand(src))
                d = _resolve_safe(_expand(dst))
                err = self._ensure_allowed(s, d)
                if err:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message=err)
                if not s.exists():
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="원본 경로가 존재하지 않습니다")
                overwrite = bool(parameters.get("overwrite", False))
                recursive = bool(parameters.get("recursive", False))

                if d.exists():
                    if not overwrite:
                        return ToolResult(status=ExecutionStatus.ERROR, error_message="대상 경로가 이미 존재합니다 (overwrite=false)")
                else:
                    d.parent.mkdir(parents=True, exist_ok=True)

                if action == "copy":
                    # 크기 제한 검증
                    max_bytes = int(self.max_copy_mb * 1024 * 1024)
                    if s.is_dir():
                        if not recursive:
                            return ToolResult(status=ExecutionStatus.ERROR, error_message="디렉토리 복사는 recursive=true 필요")
                        total = _dir_size_bytes(s)
                        if total > max_bytes:
                            return ToolResult(status=ExecutionStatus.ERROR, error_message=f"복사 용량 초과: {total} bytes > {max_bytes} bytes")
                        if dry_run:
                            return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"copy -r {str(s)} -> {str(d)}", "bytes": total})
                        if d.exists():
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        size = s.stat().st_size
                        if size > max_bytes:
                            return ToolResult(status=ExecutionStatus.ERROR, error_message=f"복사 용량 초과: {size} bytes > {max_bytes} bytes")
                        if dry_run:
                            return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"copy {str(s)} -> {str(d)}", "bytes": size})
                        shutil.copy2(s, d)

                    return ToolResult(status=ExecutionStatus.SUCCESS, data={"message": f"복사 완료: {str(s)} -> {str(d)}"})

                else:  # move
                    if dry_run:
                        return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"move {str(s)} -> {str(d)}"})
                    shutil.move(str(s), str(d))
                    return ToolResult(status=ExecutionStatus.SUCCESS, data={"message": f"이동 완료: {str(s)} -> {str(d)}"})

            if action in {"trash_delete", "delete"}:
                path = parameters.get("path")
                if not path:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="path가 필요합니다")
                p = _resolve_safe(_expand(path))
                err = self._ensure_allowed(p)
                if err:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message=err)
                if not p.exists():
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="경로가 존재하지 않습니다")

                recursive = bool(parameters.get("recursive", False))
                if p.is_dir() and not recursive:
                    return ToolResult(status=ExecutionStatus.ERROR, error_message="디렉토리 작업은 recursive=true 필요")

                if action == "trash_delete":
                    trash_dir = _resolve_safe(Path.home() / ".Trash")
                    if not trash_dir.exists():
                        try:
                            trash_dir.mkdir(exist_ok=True)
                        except Exception:
                            pass
                    target = trash_dir / p.name
                    if dry_run:
                        return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"trash {str(p)} -> {str(target)}"})
                    # 이름 충돌 시 접미사 부여
                    base_target = target
                    i = 1
                    while target.exists():
                        target = base_target.with_name(f"{base_target.stem}_{i}{base_target.suffix}")
                        i += 1
                    shutil.move(str(p), str(target))
                    return ToolResult(status=ExecutionStatus.SUCCESS, data={"message": f"휴지통으로 이동: {str(p)}"})

                else:  # delete
                    force = bool(parameters.get("force", False))
                    if not force:
                        return ToolResult(status=ExecutionStatus.ERROR, error_message="영구 삭제는 force=true가 필요합니다")
                    if dry_run:
                        return ToolResult(status=ExecutionStatus.SUCCESS, data={"planned": f"rm {'-r ' if p.is_dir() else ''}{str(p)}"})
                    try:
                        if p.is_dir():
                            shutil.rmtree(p)
                        else:
                            p.unlink()
                    except Exception as e:
                        return ToolResult(status=ExecutionStatus.ERROR, error_message=f"삭제 실패: {e}")
                    return ToolResult(status=ExecutionStatus.SUCCESS, data={"message": f"삭제 완료: {str(p)}"})

            return ToolResult(status=ExecutionStatus.ERROR, error_message=f"지원하지 않는 작업: {action}")

        except Exception as e:
            logger.error(f"FilesystemTool 실행 실패: {e}")
            return ToolResult(status=ExecutionStatus.ERROR, error_message=str(e))

