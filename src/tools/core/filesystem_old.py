"""
간단한 파일시스템 도구

안전하고 단순화된 파일시스템 조작 도구입니다.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, List

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import BaseTool, ToolResult


class SimpleFilesystemTool(BaseTool):
    """간단한 파일시스템 도구"""
    
    def __init__(self):
        super().__init__(
            name="filesystem", 
            description="안전한 파일시스템 조작 도구",
            category="system"
        )
        
        # 허용된 경로들 (보안을 위해 제한)
        self.allowed_paths = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"), 
            os.path.expanduser("~/Downloads"),
            os.path.join(os.getcwd(), "data"),  # 프로젝트 데이터 디렉토리만
            os.path.join(os.getcwd(), "temp")   # 임시 디렉토리
        ]
        
        # 매개변수 정의
        self.add_parameter("action", "str", "수행할 작업 (list, create_dir, copy, move, delete)", required=True)
        self.add_parameter("path", "str", "대상 경로", required=True)
        self.add_parameter("destination", "str", "목적지 경로 (copy, move 시 필요)", required=False)
    
    def _is_safe_path(self, path: str) -> bool:
        """경로 안전성 검증"""
        try:
            abs_path = os.path.abspath(path)
            return any(abs_path.startswith(os.path.abspath(allowed)) 
                      for allowed in self.allowed_paths)
        except:
            return False
    
    async def _execute_impl(self, parameters: Dict[str, Any]) -> ToolResult:
        """파일시스템 작업 실행"""
        action = parameters["action"]
        path = parameters["path"]
        destination = parameters.get("destination")
        
        # 경로 안전성 검증
        if not self._is_safe_path(path):
            return ToolResult(
                success=False,
                message=f"허용되지 않는 경로: {path}",
                errors=["Path not allowed"]
            )
        
        if destination and not self._is_safe_path(destination):
            return ToolResult(
                success=False,
                message=f"허용되지 않는 목적지 경로: {destination}",
                errors=["Destination path not allowed"]
            )
        
        try:
            if action == "list":
                return await self._list_directory(path)
            elif action == "create_dir":
                return await self._create_directory(path)
            elif action == "copy":
                return await self._copy_item(path, destination)
            elif action == "move":
                return await self._move_item(path, destination)
            elif action == "delete":
                return await self._delete_item(path)
            else:
                return ToolResult(
                    success=False,
                    message=f"지원되지 않는 작업: {action}",
                    errors=[f"Unsupported action: {action}"]
                )
        
        except Exception as e:
            return ToolResult(
                success=False,
                message=f"파일시스템 작업 오류: {str(e)}",
                errors=[str(e)]
            )
    
    async def _list_directory(self, path: str) -> ToolResult:
        """디렉토리 목록 조회"""
        if not os.path.exists(path):
            return ToolResult(
                success=False,
                message=f"경로가 존재하지 않음: {path}",
                errors=["Path does not exist"]
            )
        
        if not os.path.isdir(path):
            return ToolResult(
                success=False,
                message=f"디렉토리가 아님: {path}",
                errors=["Not a directory"]
            )
        
        items = []
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            items.append({
                "name": item,
                "type": "directory" if os.path.isdir(item_path) else "file",
                "size": os.path.getsize(item_path) if os.path.isfile(item_path) else 0
            })
        
        return ToolResult(
            success=True,
            message=f"디렉토리 목록 조회 완료: {len(items)}개 항목",
            data={"items": items}
        )
    
    async def _create_directory(self, path: str) -> ToolResult:
        """디렉토리 생성"""
        os.makedirs(path, exist_ok=True)
        return ToolResult(
            success=True,
            message=f"디렉토리 생성 완료: {path}"
        )
    
    async def _copy_item(self, source: str, destination: str) -> ToolResult:
        """파일/디렉토리 복사"""
        if not destination:
            return ToolResult(
                success=False,
                message="목적지 경로가 필요합니다",
                errors=["Destination path required"]
            )
        
        if os.path.isfile(source):
            shutil.copy2(source, destination)
        elif os.path.isdir(source):
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            return ToolResult(
                success=False,
                message=f"소스가 존재하지 않음: {source}",
                errors=["Source does not exist"]
            )
        
        return ToolResult(
            success=True,
            message=f"복사 완료: {source} -> {destination}"
        )
    
    async def _move_item(self, source: str, destination: str) -> ToolResult:
        """파일/디렉토리 이동"""
        if not destination:
            return ToolResult(
                success=False,
                message="목적지 경로가 필요합니다",
                errors=["Destination path required"]
            )
        
        shutil.move(source, destination)
        return ToolResult(
            success=True,
            message=f"이동 완료: {source} -> {destination}"
        )
    
    async def _delete_item(self, path: str) -> ToolResult:
        """파일/디렉토리 삭제"""
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        else:
            return ToolResult(
                success=False,
                message=f"항목이 존재하지 않음: {path}",
                errors=["Item does not exist"]
            )
        
        return ToolResult(
            success=True,
            message=f"삭제 완료: {path}"
        )


def create_filesystem_tool() -> SimpleFilesystemTool:
    """파일시스템 도구 생성 함수"""
    return SimpleFilesystemTool()