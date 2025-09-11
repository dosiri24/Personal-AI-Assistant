"""
안전한 파일시스템 조작 도구

보안을 고려한 파일/디렉토리 조작 기능을 제공합니다.
"""

import os
import shutil
import json
from pathlib import Path
from typing import Dict, Any, List
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import (
    BaseTool, ToolResult, ToolMetadata, ToolParameter, 
    ParameterType, ToolCategory, ExecutionStatus
)


class SimpleFilesystemTool(BaseTool):
    """간단한 파일시스템 도구"""
    
    def __init__(self):
        super().__init__()
        
        # 허용된 경로들 (보안을 위해 제한)
        self.allowed_paths = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"), 
            os.path.expanduser("~/Downloads"),
            os.path.join(os.getcwd(), "data"),  # 프로젝트 데이터 디렉토리만
            os.path.join(os.getcwd(), "temp")   # 임시 디렉토리
        ]
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return ToolMetadata(
            name="filesystem",
            version="1.0.0",
            description="안전한 파일시스템 조작 도구",
            category=ToolCategory.FILE_MANAGEMENT,
            parameters=[
                ToolParameter(
                    name="action",
                    type=ParameterType.STRING,
                    description="수행할 작업 (list, create_dir, copy, move, delete)",
                    required=True,
                    choices=["list", "create_dir", "copy", "move", "delete"]
                ),
                ToolParameter(
                    name="path",
                    type=ParameterType.STRING,
                    description="대상 경로",
                    required=True
                ),
                ToolParameter(
                    name="destination",
                    type=ParameterType.STRING,
                    description="목적지 경로 (copy, move 시 필요)",
                    required=False
                )
            ],
            timeout=30
        )
    
    def _is_safe_path(self, path: str) -> bool:
        """경로 안전성 검증"""
        try:
            abs_path = os.path.abspath(path)
            return any(abs_path.startswith(os.path.abspath(allowed)) 
                      for allowed in self.allowed_paths)
        except Exception:
            return False

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """도구 실행"""
        try:
            # 매개변수 검증
            validation_errors = self.validate_parameters(parameters)
            if validation_errors:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"매개변수 검증 실패: {', '.join(validation_errors)}"
                )
            
            action = parameters["action"]
            path = parameters["path"]
            destination = parameters.get("destination")
            
            # 경로 안전성 검증
            if not self._is_safe_path(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="허용되지 않은 경로입니다"
                )
            
            # 작업별 실행
            if action == "list":
                return await self._list_directory(path)
            elif action == "create_dir":
                return await self._create_directory(path)
            elif action == "copy":
                if not destination:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="copy 작업에는 destination 매개변수가 필요합니다"
                    )
                return await self._copy_item(path, destination)
            elif action == "move":
                if not destination:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="move 작업에는 destination 매개변수가 필요합니다"
                    )
                return await self._move_item(path, destination)
            elif action == "delete":
                return await self._delete_item(path)
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 작업입니다: {action}"
                )
                
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"실행 중 오류 발생: {str(e)}"
            )

    async def _list_directory(self, path: str) -> ToolResult:
        """디렉토리 내용 조회"""
        try:
            if not os.path.exists(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="경로가 존재하지 않습니다"
                )
            
            if not os.path.isdir(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="지정된 경로가 디렉토리가 아닙니다"
                )
            
            items = []
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                is_dir = os.path.isdir(item_path)
                size = os.path.getsize(item_path) if not is_dir else None
                
                items.append({
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "size": size,
                    "path": item_path
                })
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "path": path,
                    "items": items,
                    "count": len(items)
                }
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"디렉토리 조회 실패: {str(e)}"
            )

    async def _create_directory(self, path: str) -> ToolResult:
        """디렉토리 생성"""
        try:
            os.makedirs(path, exist_ok=True)
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={"message": f"디렉토리가 생성되었습니다: {path}"}
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"디렉토리 생성 실패: {str(e)}"
            )

    async def _copy_item(self, source: str, destination: str) -> ToolResult:
        """파일/디렉토리 복사"""
        try:
            # 목적지 경로도 안전성 검증
            if not self._is_safe_path(destination):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="목적지 경로가 허용되지 않습니다"
                )
            
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                # 목적지 디렉토리 생성
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copy2(source, destination)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={"message": f"복사 완료: {source} -> {destination}"}
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"복사 실패: {str(e)}"
            )

    async def _move_item(self, source: str, destination: str) -> ToolResult:
        """파일/디렉토리 이동"""
        try:
            # 목적지 경로도 안전성 검증
            if not self._is_safe_path(destination):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="목적지 경로가 허용되지 않습니다"
                )
            
            # 목적지 디렉토리 생성
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.move(source, destination)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={"message": f"이동 완료: {source} -> {destination}"}
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"이동 실패: {str(e)}"
            )

    async def _delete_item(self, path: str) -> ToolResult:
        """파일/디렉토리 삭제"""
        try:
            if not os.path.exists(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="삭제할 경로가 존재하지 않습니다"
                )
            
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={"message": f"삭제 완료: {path}"}
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"삭제 실패: {str(e)}"
            )
