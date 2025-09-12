"""
시스템 탐색 도구

LLM이 스스로 파일 시스템을 탐색하고 구조를 파악할 수 있도록 하는 도구입니다.
Mac, Windows, Linux 크로스 플랫폼 지원.
"""

import os
import platform
import subprocess
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import (
    BaseTool, ToolResult, ToolMetadata, ToolParameter, 
    ParameterType, ToolCategory, ExecutionStatus
)
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SystemExplorerTool(BaseTool):
    """시스템 탐색 도구 - LLM이 스스로 파일 구조를 파악하게 도움"""
    
    def __init__(self):
        super().__init__()
        self.system = platform.system().lower()
        self.home_dir = os.path.expanduser("~")
        
        # 보안을 위한 탐색 허용 경로
        self.allowed_base_paths = [
            self.home_dir,
            os.path.join(self.home_dir, "Desktop"),
            os.path.join(self.home_dir, "Documents"),
            os.path.join(self.home_dir, "Downloads"),
            os.path.join(self.home_dir, "Pictures"),
            "/tmp" if self.system != "windows" else "C:\\temp"
        ]
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return ToolMetadata(
            name="system_explorer",
            version="1.0.0",
            description="시스템 파일 구조를 탐색하고 분석하는 도구. tree, find, locate 등의 기능 제공",
            category=ToolCategory.SYSTEM,
            parameters=[
                ToolParameter(
                    name="action",
                    type=ParameterType.STRING,
                    description="수행할 탐색 작업",
                    required=True,
                    choices=["tree", "find", "locate", "explore_common", "get_structure", "search_files"]
                ),
                ToolParameter(
                    name="path",
                    type=ParameterType.STRING,
                    description="탐색할 경로 (기본값: 홈 디렉토리)",
                    required=False,
                    default="~"
                ),
                ToolParameter(
                    name="pattern",
                    type=ParameterType.STRING,
                    description="검색할 파일 패턴 (find, locate, search_files에서 사용)",
                    required=False
                ),
                ToolParameter(
                    name="depth",
                    type=ParameterType.INTEGER,
                    description="탐색 깊이 (1-5, 기본값: 2)",
                    required=False,
                    default=2
                ),
                ToolParameter(
                    name="show_hidden",
                    type=ParameterType.BOOLEAN,
                    description="숨김 파일 포함 여부",
                    required=False,
                    default=False
                )
            ],
            timeout=30
        )
    
    def _is_safe_path(self, path: str) -> bool:
        """경로 안전성 검증"""
        try:
            expanded_path = os.path.expanduser(path)
            abs_path = os.path.abspath(expanded_path)
            return any(abs_path.startswith(os.path.abspath(allowed)) 
                      for allowed in self.allowed_base_paths)
        except Exception:
            return False

    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """매개변수 검증 강화"""
        errors = super().validate_parameters(parameters)
        
        # action 매개변수 특별 검증
        action = parameters.get("action")
        if action:
            valid_actions = ["tree", "find", "locate", "explore_common", "get_structure", "search_files"]
            if action not in valid_actions:
                errors.append(
                    f"❌ 매개변수 'action'의 값이 유효하지 않습니다: '{action}'\n"
                    f"✅ 유효한 값들: {', '.join(valid_actions)}\n"
                    f"💡 힌트: 파일 검색은 'search_files' 또는 'find'를 사용하세요 ('find_files' 아님!)"
                )
        
        return errors

    def _auto_correct_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """매개변수 자동 정정"""
        corrected = parameters.copy()
        
        # 잘못된 action 값 자동 수정
        action_corrections = {
            "find_files": "search_files",
            "list_files": "find", 
            "search": "search_files",
            "list": "find"
        }
        
        if "action" in corrected:
            original_action = corrected["action"]
            if original_action in action_corrections:
                corrected["action"] = action_corrections[original_action]
                logger.info(f"action 매개변수 자동 정정: '{original_action}' → '{corrected['action']}'")
        
        # 지원되지 않는 매개변수 제거 및 매핑
        unsupported_params = ["recursive"]
        for param in unsupported_params:
            if param in corrected:
                if param == "recursive" and corrected[param]:
                    # recursive=True인 경우 depth를 더 크게 설정
                    corrected["depth"] = 3
                    logger.info(f"recursive 매개변수를 depth=3으로 변환")
                del corrected[param]
                logger.info(f"지원되지 않는 매개변수 '{param}' 제거")
        
        return corrected

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """도구 실행"""
        try:
            # 매개변수 자동 정정
            parameters = self._auto_correct_parameters(parameters)
            
            # 매개변수 검증
            validation_errors = self.validate_parameters(parameters)
            if validation_errors:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"매개변수 검증 실패: {', '.join(validation_errors)}"
                )
            
            action = parameters["action"]
            path = parameters.get("path", "~")
            pattern = parameters.get("pattern", "*")
            depth = min(int(parameters.get("depth", 2)), 5)  # 최대 깊이 제한
            show_hidden = parameters.get("show_hidden", False)
            
            # 경로 정규화
            path = os.path.expanduser(path)
            
            # 경로 안전성 검증
            if not self._is_safe_path(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"허용되지 않은 경로입니다: {path}"
                )
            
            # 작업별 실행
            if action == "tree":
                return await self._tree_command(path, depth, show_hidden)
            elif action == "find":
                return await self._find_files(path, pattern, depth)
            elif action == "locate":
                return await self._locate_files(pattern)
            elif action == "explore_common":
                return await self._explore_common_locations()
            elif action == "get_structure":
                return await self._get_directory_structure(path, depth)
            elif action == "search_files":
                return await self._search_files_by_pattern(path, pattern, depth)
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 작업입니다: {action}"
                )
                
        except Exception as e:
            logger.error(f"시스템 탐색 실행 중 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"실행 중 오류 발생: {str(e)}"
            )

    async def _tree_command(self, path: str, depth: int, show_hidden: bool) -> ToolResult:
        """Tree 명령어 실행 (크로스 플랫폼)"""
        try:
            result_data = {"path": path, "structure": [], "summary": {}}
            
            if self.system == "windows":
                # Windows tree 명령어
                cmd = ["tree", path, "/F"] if show_hidden else ["tree", path]
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    output = result.stdout
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    # tree 명령어가 없으면 dir 사용
                    output = await self._windows_dir_tree(path, depth)
            else:
                # Mac/Linux
                if shutil.which("tree"):
                    # tree 명령어가 있는 경우
                    cmd = ["tree", "-L", str(depth), path]
                    if show_hidden:
                        cmd.insert(-1, "-a")
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    output = result.stdout
                else:
                    # tree가 없으면 ls를 이용해 구조 생성
                    output = await self._unix_ls_tree(path, depth, show_hidden)
            
            # 구조화된 데이터 생성
            structure = self._parse_tree_output(output, path)
            result_data["structure"] = structure
            result_data["raw_output"] = output
            result_data["summary"] = self._generate_summary(structure)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=result_data
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Tree 명령어 실행 실패: {str(e)}"
            )

    async def _find_files(self, path: str, pattern: str, depth: int) -> ToolResult:
        """파일 검색 (find 명령어 사용)"""
        try:
            found_files = []
            
            if self.system == "windows":
                # Windows에서는 PowerShell Get-ChildItem 사용
                cmd = [
                    "powershell", "-Command",
                    f"Get-ChildItem -Path '{path}' -Recurse -Depth {depth} -Filter '{pattern}' | Select-Object FullName, Length, LastWriteTime"
                ]
            else:
                # Unix 계열에서는 find 사용
                cmd = ["find", path, "-maxdepth", str(depth), "-name", pattern, "-type", "f"]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if line:
                            file_path = line.strip()
                            if os.path.exists(file_path):
                                stat = os.stat(file_path)
                                found_files.append({
                                    "path": file_path,
                                    "name": os.path.basename(file_path),
                                    "size": stat.st_size,
                                    "modified": stat.st_mtime
                                })
            except subprocess.TimeoutExpired:
                logger.warning("Find 명령어 타임아웃")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "search_path": path,
                    "pattern": pattern,
                    "found_files": found_files,
                    "count": len(found_files)
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"파일 검색 실패: {str(e)}"
            )

    async def _explore_common_locations(self) -> ToolResult:
        """일반적인 위치들 탐색"""
        try:
            common_locations = []
            
            # 플랫폼별 일반적인 위치들
            if self.system == "windows":
                potential_paths = [
                    os.path.join(self.home_dir, "Desktop"),
                    os.path.join(self.home_dir, "Documents"),
                    os.path.join(self.home_dir, "Downloads"),
                    os.path.join(self.home_dir, "Pictures"),
                    "C:\\Users\\Public\\Desktop"
                ]
            else:
                potential_paths = [
                    os.path.join(self.home_dir, "Desktop"),
                    os.path.join(self.home_dir, "Documents"),
                    os.path.join(self.home_dir, "Downloads"),
                    os.path.join(self.home_dir, "Pictures"),
                    "/Users/Shared" if self.system == "darwin" else "/home"
                ]
            
            for path in potential_paths:
                if os.path.exists(path) and os.path.isdir(path):
                    try:
                        items = os.listdir(path)
                        common_locations.append({
                            "path": path,
                            "exists": True,
                            "item_count": len(items),
                            "sample_items": items[:5]  # 처음 5개만
                        })
                    except PermissionError:
                        common_locations.append({
                            "path": path,
                            "exists": True,
                            "accessible": False,
                            "error": "권한 없음"
                        })
                else:
                    common_locations.append({
                        "path": path,
                        "exists": False
                    })
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "system": self.system,
                    "home_directory": self.home_dir,
                    "common_locations": common_locations
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"일반 위치 탐색 실패: {str(e)}"
            )

    async def _search_files_by_pattern(self, path: str, pattern: str, depth: int) -> ToolResult:
        """패턴으로 파일 검색 (스크린샷, 이미지 등)"""
        try:
            # 일반적인 파일 패턴들
            patterns = {
                "screenshot": ["*스크린샷*", "*Screenshot*", "*Screen Shot*", "*.png", "*.jpg"],
                "image": ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.bmp"],
                "document": ["*.pdf", "*.doc", "*.docx", "*.txt"],
                "archive": ["*.zip", "*.rar", "*.7z", "*.tar.gz"]
            }
            
            search_patterns = patterns.get(pattern.lower(), [pattern])
            all_found_files = []
            
            for search_pattern in search_patterns:
                result = await self._find_files(path, search_pattern, depth)
                if result.status == ExecutionStatus.SUCCESS and result.data:
                    all_found_files.extend(result.data.get("found_files", []))
            
            # 중복 제거
            unique_files = []
            seen_paths = set()
            for file_info in all_found_files:
                if file_info["path"] not in seen_paths:
                    unique_files.append(file_info)
                    seen_paths.add(file_info["path"])
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "search_path": path,
                    "pattern_type": pattern,
                    "found_files": unique_files,
                    "count": len(unique_files),
                    "by_extension": self._group_by_extension(unique_files)
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"패턴 검색 실패: {str(e)}"
            )

    def _group_by_extension(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """파일을 확장자별로 그룹화"""
        grouped = {}
        for file_info in files:
            ext = os.path.splitext(file_info["name"])[1].lower()
            if ext not in grouped:
                grouped[ext] = []
            grouped[ext].append(file_info)
        return grouped

    def _parse_tree_output(self, output: str, base_path: str) -> List[Dict]:
        """Tree 출력을 구조화된 데이터로 변환"""
        structure = []
        lines = output.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('├') and not line.startswith('└'):
                continue
            
            # 간단한 파싱 (실제 구현에서는 더 정교하게)
            if '├' in line or '└' in line:
                name = line.split('──')[-1].strip() if '──' in line else line.strip()
                if name:
                    structure.append({
                        "name": name,
                        "type": "directory" if not '.' in name else "file",
                        "level": len(line) - len(line.lstrip())
                    })
        
        return structure

    def _generate_summary(self, structure: List[Dict]) -> Dict:
        """구조 요약 생성"""
        total_items = len(structure)
        directories = len([item for item in structure if item.get("type") == "directory"])
        files = total_items - directories
        
        return {
            "total_items": total_items,
            "directories": directories,
            "files": files
        }

    async def _unix_ls_tree(self, path: str, depth: int, show_hidden: bool) -> str:
        """Unix 계열에서 ls를 이용한 tree 대체"""
        try:
            cmd = ["ls", "-la" if show_hidden else "-l", path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return result.stdout
        except Exception as e:
            return f"ls 명령어 실행 실패: {e}"

    async def _windows_dir_tree(self, path: str, depth: int) -> str:
        """Windows에서 dir를 이용한 tree 대체"""
        try:
            cmd = ["dir", path, "/S" if depth > 1 else ""]
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            return result.stdout
        except Exception as e:
            return f"dir 명령어 실행 실패: {e}"

    async def _locate_files(self, pattern: str) -> ToolResult:
        """locate 명령어로 파일 검색 (Unix만)"""
        if self.system == "windows":
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message="locate 명령어는 Windows에서 지원되지 않습니다"
            )
        
        try:
            cmd = ["locate", pattern]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="locate 명령어가 설치되어 있지 않거나 데이터베이스가 없습니다"
                )
            
            files = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "pattern": pattern,
                    "found_files": files[:50],  # 최대 50개만
                    "total_count": len(files),
                    "truncated": len(files) > 50
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"locate 실행 실패: {str(e)}"
            )

    async def _get_directory_structure(self, path: str, depth: int) -> ToolResult:
        """디렉토리 구조를 재귀적으로 탐색"""
        try:
            def scan_directory(dir_path: str, current_depth: int = 0) -> Dict:
                if current_depth >= depth:
                    return {"name": os.path.basename(dir_path), "type": "directory", "children": []}
                
                try:
                    items = []
                    for item in os.listdir(dir_path):
                        if item.startswith('.'):  # 숨김 파일 스킵
                            continue
                        
                        item_path = os.path.join(dir_path, item)
                        if os.path.isdir(item_path):
                            items.append(scan_directory(item_path, current_depth + 1))
                        else:
                            stat = os.stat(item_path)
                            items.append({
                                "name": item,
                                "type": "file",
                                "size": stat.st_size,
                                "extension": os.path.splitext(item)[1]
                            })
                    
                    return {
                        "name": os.path.basename(dir_path),
                        "type": "directory",
                        "children": items[:20]  # 최대 20개 아이템만
                    }
                except PermissionError:
                    return {
                        "name": os.path.basename(dir_path),
                        "type": "directory",
                        "error": "접근 권한 없음"
                    }
            
            structure = scan_directory(path)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "path": path,
                    "structure": structure,
                    "depth": depth
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"디렉토리 구조 탐색 실패: {str(e)}"
            )
