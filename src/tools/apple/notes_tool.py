"""
Apple Notes MCP 도구

Apple Notes 앱을 통해 메모를 생성, 검색, 관리하는 도구입니다.
현재는 시뮬레이션 모드로 동작하며, 향후 실제 Apple MCP 서버와 연동될 예정입니다.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.mcp.base_tool import BaseTool, ToolResult, ExecutionStatus, ToolMetadata, ToolCategory, ToolParameter, ParameterType

logger = logging.getLogger(__name__)

class AppleNotesTool(BaseTool):
    """Apple Notes 앱 MCP 도구"""

    def __init__(self):
        """Apple Notes 도구 초기화"""
        super().__init__()
        logger.info("Apple Notes 도구 초기화 완료")

    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return ToolMetadata(
            name="apple_notes",
            version="1.0.0",
            description="Apple Notes 앱을 통한 메모 생성 및 관리",
            category=ToolCategory.PRODUCTIVITY,
            parameters=[
                ToolParameter(
                    name="action",
                    type=ParameterType.STRING,
                    description="수행할 작업",
                    required=True,
                    choices=["create", "search", "update", "delete"]
                ),
                ToolParameter(
                    name="title",
                    type=ParameterType.STRING,
                    description="노트 제목",
                    required=False
                ),
                ToolParameter(
                    name="content",
                    type=ParameterType.STRING,
                    description="노트 내용",
                    required=False
                ),
                ToolParameter(
                    name="folder",
                    type=ParameterType.STRING,
                    description="폴더 이름",
                    required=False,
                    default="Notes"
                ),
                ToolParameter(
                    name="search_query",
                    type=ParameterType.STRING,
                    description="검색어",
                    required=False
                ),
                ToolParameter(
                    name="note_id",
                    type=ParameterType.STRING,
                    description="노트 ID",
                    required=False
                )
            ],
            tags=["apple", "notes", "memo", "productivity"],
            timeout=10
        )

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        Apple Notes 작업 실행
        
        Args:
            parameters: 작업 파라미터
                - action: 작업 유형 ('create', 'search', 'update', 'delete')
                - title: 노트 제목 (create, update에서 사용)
                - content: 노트 내용 (create, update에서 사용)
                - folder: 폴더 이름 (선택사항)
                - search_query: 검색어 (search에서 사용)
                - note_id: 노트 ID (update, delete에서 사용)
        
        Returns:
            ToolResult: 실행 결과
        """
        try:
            action = parameters.get("action", "create")
            
            if action == "create":
                return await self._create_note(parameters)
            elif action == "search":
                return await self._search_notes(parameters)
            elif action == "update":
                return await self._update_note(parameters)
            elif action == "delete":
                return await self._delete_note(parameters)
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            logger.error(f"Apple Notes 도구 실행 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Notes 도구 실행 실패: {str(e)}"
            )

    async def _create_note(self, parameters: Dict[str, Any]) -> ToolResult:
        """새 노트 생성 (실제 Notes 앱 호출)"""
        import subprocess
        import shlex
        
        title = parameters.get("title", "새 메모")
        content = parameters.get("content", "")
        folder = parameters.get("folder", "Notes")
        
        logger.info(f"Apple Notes에 메모 생성: {title}")
        
        # AppleScript를 사용해 실제 Notes에 노트 생성
        # 특수문자 이스케이프 처리
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        
        as_title = esc(title)
        as_content = esc(content)
        as_folder = esc(folder)
        
        applescript = f'''
        tell application "Notes"
            set targetFolder to folder "{as_folder}" of default account
            make new note at targetFolder with properties {{name:"{as_title}", body:"{as_content}"}}
        end tell
        '''
        
        try:
            result = subprocess.run(
                ["osascript", "-e", applescript],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"Notes 생성 실패: {result.stderr.strip() or result.stdout.strip()}"
                )
            
            # osascript는 note id를 직접 반환하지 않음 -> 타임스탬프 기반 임시 ID
            note_id = f"notes_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "action": "create",
                    "note_id": note_id,
                    "title": title,
                    "content": content,
                    "folder": folder,
                    "created_at": datetime.now().isoformat(),
                    "message": f"Apple Notes에 메모를 추가했습니다: {title}"
                }
            )
        except FileNotFoundError:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message="osascript를 찾을 수 없습니다. macOS 환경인지 확인하세요."
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Notes 생성 중 예외: {e}"
            )

    async def _search_notes(self, parameters: Dict[str, Any]) -> ToolResult:
        """노트 검색"""
        search_query = parameters.get("search_query", "")
        
        logger.info(f"Apple Notes 검색 시뮬레이션: {search_query}")
        
        # 시뮬레이션된 검색 결과
        results = [
            {
                "note_id": "note_20240101_120000",
                "title": "쇼핑 목록",
                "content": "사과 3개, 바나나 2개",
                "folder": "Notes",
                "modified_at": "2024-01-01T12:00:00"
            }
        ]
        
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            data={
                "action": "search",
                "query": search_query,
                "results": results,
                "count": len(results)
            }
        )

    async def _update_note(self, parameters: Dict[str, Any]) -> ToolResult:
        """노트 업데이트"""
        note_id = parameters.get("note_id")
        title = parameters.get("title")
        content = parameters.get("content")
        
        if not note_id:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message="노트 ID가 필요합니다"
            )
        
        logger.info(f"Apple Notes 업데이트 시뮬레이션: {note_id}")
        
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            data={
                "action": "update",
                "note_id": note_id,
                "title": title,
                "content": content,
                "updated_at": datetime.now().isoformat(),
                "message": f"Apple Notes 메모를 업데이트했습니다: {title or note_id}"
            }
        )

    async def _delete_note(self, parameters: Dict[str, Any]) -> ToolResult:
        """노트 삭제"""
        note_id = parameters.get("note_id")
        
        if not note_id:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message="노트 ID가 필요합니다"
            )
        
        logger.info(f"Apple Notes 삭제 시뮬레이션: {note_id}")
        
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            data={
                "action": "delete",
                "note_id": note_id,
                "deleted_at": datetime.now().isoformat(),
                "message": f"Apple Notes 메모를 삭제했습니다: {note_id}"
            }
        )

    def get_schema(self) -> Dict[str, Any]:
        """도구 스키마 반환"""
        return self.metadata.to_dict()
