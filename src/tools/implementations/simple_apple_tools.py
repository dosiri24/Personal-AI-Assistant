"""
Apple 시스템 통합 도구 (Python 전용)

TypeScript 의존성을 제거하고 Python으로 Apple 기능을 구현합니다.
macOS에서만 작동하며, AppleScript를 통해 시스템 기능에 접근합니다.
"""

import os
import platform
import subprocess
from typing import Dict, Any, Optional
from ..base import BaseTool, ExecutionResult


class SimpleAppleNotesTool(BaseTool):
    """간단한 Apple Notes 도구"""
    
    def __init__(self):
        super().__init__(
            name="apple_notes",
            description="Apple Notes에 메모를 작성하거나 검색하는 도구",
            category="apple"
        )
        
        self.add_parameter("action", "str", "수행할 작업 (create, search)", required=True)
        self.add_parameter("title", "str", "노트 제목", required=False)
        self.add_parameter("content", "str", "노트 내용", required=False)
        self.add_parameter("query", "str", "검색할 내용", required=False)
    
    def _is_macos(self) -> bool:
        """macOS인지 확인"""
        return platform.system() == "Darwin"
    
    def _run_applescript(self, script: str) -> str:
        """AppleScript 실행"""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                raise Exception(f"AppleScript error: {result.stderr}")
        except Exception as e:
            raise Exception(f"AppleScript execution failed: {str(e)}")
    
    async def _execute_impl(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """Apple Notes 작업 실행"""
        if not self._is_macos():
            return ExecutionResult(
                success=False,
                message="Apple Notes는 macOS에서만 사용할 수 있습니다",
                errors=["Not running on macOS"]
            )
        
        action = parameters["action"]
        
        try:
            if action == "create":
                return await self._create_note(parameters)
            elif action == "search":
                return await self._search_notes(parameters)
            else:
                return ExecutionResult(
                    success=False,
                    message=f"지원되지 않는 작업: {action}",
                    errors=[f"Unsupported action: {action}"]
                )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"Apple Notes 작업 실패: {str(e)}",
                errors=[str(e)]
            )
    
    async def _create_note(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """새 노트 생성"""
        title = parameters.get("title", "새 노트")
        content = parameters.get("content", "")
        
        script = f'''
        tell application "Notes"
            make new note with properties {{name:"{title}", body:"{content}"}}
        end tell
        '''
        
        try:
            self._run_applescript(script)
            return ExecutionResult(
                success=True,
                message=f"노트 '{title}' 생성 완료"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"노트 생성 실패: {str(e)}",
                errors=[str(e)]
            )
    
    async def _search_notes(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """노트 검색"""
        query = parameters.get("query", "")
        
        if not query:
            return ExecutionResult(
                success=False,
                message="검색어가 필요합니다",
                errors=["Query is required for search"]
            )
        
        # 간단한 검색 구현 (실제로는 더 복잡한 AppleScript 필요)
        script = f'''
        tell application "Notes"
            set noteList to every note whose body contains "{query}"
            set noteNames to {{}}
            repeat with aNote in noteList
                set noteNames to noteNames & {{name of aNote}}
            end repeat
            return noteNames as string
        end tell
        '''
        
        try:
            result = self._run_applescript(script)
            return ExecutionResult(
                success=True,
                message=f"'{query}' 검색 완료",
                data={"results": result.split(", ") if result else []}
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"노트 검색 실패: {str(e)}",
                errors=[str(e)]
            )


def create_apple_notes_tool() -> SimpleAppleNotesTool:
    """Apple Notes 도구 생성 함수"""
    return SimpleAppleNotesTool()


# macOS가 아닌 경우를 위한 스텁 구현
class AppleToolStub(BaseTool):
    """Apple 도구 스텁 (macOS가 아닌 환경용)"""
    
    def __init__(self, name: str, description: str):
        super().__init__(name, description, "apple")
    
    async def _execute_impl(self, parameters: Dict[str, Any]) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="Apple 도구는 macOS에서만 사용할 수 있습니다",
            errors=["Apple tools are only available on macOS"]
        )


def create_apple_tools():
    """사용 가능한 Apple 도구들 생성"""
    if platform.system() == "Darwin":
        return [create_apple_notes_tool()]
    else:
        # macOS가 아닌 경우 스텁 도구들 반환
        return [
            AppleToolStub("apple_notes", "Apple Notes 도구 (macOS 전용)"),
        ]