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
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """매개변수 검증 - 더 명확한 에러 메시지 제공"""
        errors = super().validate_parameters(parameters)
        
        # action 매개변수 특별 검증
        action = parameters.get("action")
        if action:
            valid_actions = ["list", "create_dir", "copy", "move", "delete"]
            if action not in valid_actions:
                errors.append(
                    f"❌ 매개변수 'action'의 값이 유효하지 않습니다: '{action}'\n"
                    f"✅ 유효한 값들: {', '.join(valid_actions)}\n"
                    f"💡 힌트: 파일 삭제는 'delete'를 사용하세요 ('delete_file' 아님!)"
                )
        
        return errors

    def _auto_correct_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """매개변수 자동 정정"""
        corrected = parameters.copy()
        
        # 잘못된 action 값 자동 수정
        action_corrections = {
            "delete_file": "delete",
            "remove": "delete",
            "remove_file": "delete",
            "list_files": "list",
            "create_directory": "create_dir",
            "mkdir": "create_dir"
        }
        
        if "action" in corrected:
            original_action = corrected["action"]
            if original_action in action_corrections:
                corrected["action"] = action_corrections[original_action]
                logger.info(f"filesystem action 매개변수 자동 정정: '{original_action}' → '{corrected['action']}'")
        
        return corrected

    def _is_safe_path(self, path: str) -> bool:
        try:
            # 경로 정규화 및 확장
            expanded_path = os.path.expanduser(path)
            abs_path = os.path.abspath(expanded_path)
            return any(abs_path.startswith(os.path.abspath(allowed)) 
                      for allowed in self.allowed_paths)
        except Exception:
            return False

    def _normalize_path(self, path: str) -> str:
        """경로 정규화 - 상대경로를 절대경로로 변환"""
        # 틸드 확장
        expanded_path = os.path.expanduser(path)
        
        # 상대경로 감지 및 자동 변환
        if not os.path.isabs(expanded_path):
            # 일반적인 상대경로 패턴을 절대경로로 변환
            home_dir = os.path.expanduser("~")
            
            if expanded_path.startswith("Desktop"):
                converted_path = os.path.join(home_dir, expanded_path)
                logger.warning(f"🚨 상대경로 자동 변환: '{path}' → '{converted_path}'")
                logger.warning("💡 앞으로는 절대경로를 사용해주세요 (예: /Users/taesooa/Desktop/폴더명)")
                return converted_path
            elif expanded_path.startswith("Documents"):
                converted_path = os.path.join(home_dir, expanded_path)
                logger.warning(f"🚨 상대경로 자동 변환: '{path}' → '{converted_path}'")
                logger.warning("💡 앞으로는 절대경로를 사용해주세요 (예: /Users/taesooa/Documents/파일명)")
                return converted_path
            elif expanded_path.startswith("Downloads"):
                converted_path = os.path.join(home_dir, expanded_path)
                logger.warning(f"🚨 상대경로 자동 변환: '{path}' → '{converted_path}'")
                logger.warning("💡 앞으로는 절대경로를 사용해주세요 (예: /Users/taesooa/Downloads/파일명)")
                return converted_path
            else:
                # 기타 상대경로는 절대경로로 변환
                converted_path = os.path.abspath(expanded_path)
                logger.warning(f"🚨 상대경로 자동 변환: '{path}' → '{converted_path}'")
                logger.warning("💡 프로젝트 폴더가 아닌 사용자 디렉토리에 파일을 만드려면 절대경로를 사용하세요")
                return converted_path
        
        return expanded_path

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
            path = parameters["path"]
            destination = parameters.get("destination")
            
            # 경로 정규화
            path = self._normalize_path(path)
            if destination:
                destination = self._normalize_path(destination)
            
            # 경로 안전성 검증
            if not self._is_safe_path(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"허용되지 않은 경로입니다: {path}"
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
            # 경로가 디렉토리이고 "스크린샷" 관련 요청인 경우 특별 처리
            if os.path.isdir(path) and any(keyword in path.lower() for keyword in ["desktop", "바탕화면"]):
                # 스크린샷 파일 패턴
                screenshot_patterns = [
                    "스크린샷*.png", "스크린샷*.jpg", "스크린샷*.jpeg",
                    "Screenshot*.png", "Screenshot*.jpg", "Screenshot*.jpeg",
                    "Screen Shot*.png", "Screen Shot*.jpg", "Screen Shot*.jpeg"
                ]
                
                deleted_files = []
                import glob
                
                for pattern in screenshot_patterns:
                    files = glob.glob(os.path.join(path, pattern))
                    for file_path in files:
                        try:
                            os.remove(file_path)
                            deleted_files.append(os.path.basename(file_path))
                        except Exception as e:
                            logger.warning(f"파일 삭제 실패: {file_path} - {e}")
                
                if deleted_files:
                    return ToolResult(
                        status=ExecutionStatus.SUCCESS,
                        data={
                            "message": f"스크린샷 파일 {len(deleted_files)}개 삭제 완료",
                            "deleted_files": deleted_files,
                            "path": path
                        }
                    )
                else:
                    return ToolResult(
                        status=ExecutionStatus.SUCCESS,
                        data={
                            "message": "삭제할 스크린샷 파일이 없습니다",
                            "path": path
                        }
                    )
            
            # 일반적인 파일/디렉토리 삭제
            if not os.path.exists(path):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"삭제할 경로가 존재하지 않습니다: {path}"
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
