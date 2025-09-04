"""
Notion 할일 관리 도구

Notion 할일 데이터베이스를 관리하는 MCP 도구입니다.
할일 추가, 수정, 삭제, 조회, 완료 처리 기능을 제공합니다.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

from ...mcp.base_tool import BaseTool, ToolMetadata, ToolResult, ExecutionStatus, ToolCategory, ToolParameter, ParameterType
from ...config import Settings
from ...utils.logger import get_logger
from .client import NotionClient, NotionError, create_notion_property, create_text_block

logger = get_logger(__name__)


class TodoData(BaseModel):
    """할일 데이터"""
    title: str = Field(..., description="할일 제목")
    description: Optional[str] = Field(None, description="할일 설명")
    due_date: Optional[datetime] = Field(None, description="마감일")
    priority: Optional[str] = Field("중간", description="우선순위 (높음, 중간, 낮음)")
    category: Optional[str] = Field("Personal", description="카테고리")
    tags: Optional[List[str]] = Field(None, description="태그 목록")
    status: str = Field("Not Started", description="상태")
    assignee: Optional[str] = Field(None, description="담당자")
    estimated_hours: Optional[float] = Field(None, description="예상 소요 시간")


class TodoTool(BaseTool):
    """
    Notion 할일 관리 도구
    
    할일 데이터베이스에서 할일을 추가, 수정, 삭제, 조회, 완료 처리하는 기능을 제공합니다.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        할일 도구 초기화
        
        Args:
            settings: 애플리케이션 설정
        """
        if settings is None:
            settings = Settings()
        
        self.settings = settings
        self.notion_client: Optional[NotionClient] = None
        self.database_id = settings.notion_todo_database_id
        
        if not self.database_id:
            logger.warning("Notion 할일 데이터베이스 ID가 설정되지 않았습니다")
        
        super().__init__()
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        parameters = [
            ToolParameter(
                name="action",
                type=ParameterType.STRING,
                description="수행할 작업 (create, update, delete, get, list, complete)",
                required=True,
                choices=["create", "update", "delete", "get", "list", "complete"]
            ),
            ToolParameter(
                name="title",
                type=ParameterType.STRING,
                description="할일 제목",
                required=False
            ),
            ToolParameter(
                name="description",
                type=ParameterType.STRING,
                description="할일 설명",
                required=False
            ),
            ToolParameter(
                name="due_date",
                type=ParameterType.STRING,
                description="마감일 (ISO 형식 또는 자연어)",
                required=False
            ),
            ToolParameter(
                name="priority",
                type=ParameterType.STRING,
                description="우선순위",
                required=False,
                choices=["높음", "중간", "낮음"]
            ),
            ToolParameter(
                name="category",
                type=ParameterType.STRING,
                description="카테고리",
                required=False
            ),
            ToolParameter(
                name="tags",
                type=ParameterType.ARRAY,
                description="태그 목록",
                required=False
            ),
            ToolParameter(
                name="status",
                type=ParameterType.STRING,
                description="상태",
                required=False,
                choices=["Not Started", "In Progress", "Completed", "Cancelled"]
            ),
            ToolParameter(
                name="assignee",
                type=ParameterType.STRING,
                description="담당자",
                required=False
            ),
            ToolParameter(
                name="estimated_hours",
                type=ParameterType.NUMBER,
                description="예상 소요 시간",
                required=False
            ),
            ToolParameter(
                name="todo_id",
                type=ParameterType.STRING,
                description="할일 ID (수정/삭제/조회/완료용)",
                required=False
            ),
            ToolParameter(
                name="filter",
                type=ParameterType.STRING,
                description="필터 조건 (all, pending, completed, overdue)",
                required=False
            )
        ]
        
        return ToolMetadata(
            name="notion_todo",
            version="1.0.0",
            description="Notion 할일 데이터베이스에서 할일을 관리합니다",
            category=ToolCategory.PRODUCTIVITY,
            parameters=parameters,
            tags=["notion", "todo", "task", "productivity"]
        )
    
    async def _ensure_client(self):
        """Notion 클라이언트 초기화"""
        if self.notion_client is None:
            from .client import NotionClient
            self.notion_client = NotionClient(use_async=True)
            
            # 연결 테스트
            if not await self.notion_client.test_connection():
                raise NotionError("Notion API 연결에 실패했습니다")
        
        # 타입 체커를 위한 assert
        assert self.notion_client is not None, "Notion 클라이언트가 초기화되지 않았습니다"
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """자연어나 ISO 형식의 날짜/시간을 파싱"""
        if not date_str:
            return datetime.now(timezone.utc)
        
        # ISO 형식 시도
        try:
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            pass
        
        # 자연어 파싱 (간단한 패턴들)
        now = datetime.now(timezone.utc)
        date_str_lower = date_str.lower().strip()
        
        if date_str_lower in ['오늘', 'today']:
            return now.replace(hour=23, minute=59, second=0, microsecond=0)
        elif date_str_lower in ['내일', 'tomorrow']:
            return (now + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        elif date_str_lower in ['다음 주', 'next week']:
            return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        
        return now.replace(hour=23, minute=59, second=0, microsecond=0)
    
    def _create_todo_properties(self, todo: TodoData) -> Dict[str, Any]:
        """Todo 속성을 Notion 형식으로 변환"""
        properties = {
            "작업명": create_notion_property("title", todo.title)
        }
        
        # 선택적 속성들
        if todo.description:
            properties["작업설명"] = create_notion_property("rich_text", todo.description)
        
        if todo.priority:
            properties["우선순위"] = create_notion_property("select", todo.priority)
        
        if todo.due_date:
            properties["마감일"] = create_notion_property("date", todo.due_date)
        
        return properties
    
    async def _create_todo(self, params: Dict[str, Any]) -> ToolResult:
        """새 할일 생성"""
        try:
            # 필수 파라미터 확인
            title = params.get("title")
            if not title:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="제목이 필요합니다"
                )
            
            # 마감일 파싱
            due_date = None
            if params.get("due_date"):
                due_date = self._parse_datetime(params["due_date"])
            
            # 할일 데이터 생성
            todo = TodoData(
                title=title,
                description=params.get("description"),
                due_date=due_date,
                priority=params.get("priority", "중간"),
                category=params.get("category", "Personal"),
                tags=params.get("tags"),
                status=params.get("status", "Not Started"),
                assignee=params.get("assignee"),
                estimated_hours=params.get("estimated_hours")
            )
            
            # Notion 속성 생성
            properties = self._create_todo_properties(todo)
            
            # 설명이 있으면 페이지 내용으로 추가
            children = []
            if todo.description:
                children.append(create_text_block(todo.description))
            
            # 페이지 생성
            if not self.database_id:
                raise NotionError("데이터베이스 ID가 설정되지 않았습니다")
            
            if not self.notion_client:
                raise NotionError("Notion 클라이언트가 초기화되지 않았습니다")
            
            result = await self.notion_client.create_page(
                parent_id=self.database_id,
                properties=properties,
                children=children if children else None
            )
            
            page_id = result.get("id", "")
            page_url = result.get("url", "")
            
            logger.info(f"할일 생성 완료: {title} ({page_id})")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo_id": page_id,
                    "title": title,
                    "due_date": due_date.isoformat() if due_date else None,
                    "priority": todo.priority,
                    "status": todo.status,
                    "url": page_url,
                    "message": f"할일 '{title}'이 성공적으로 생성되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 생성 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 생성 중 오류 발생: {e}"
            )
    
    async def _list_todos(self, params: Dict[str, Any]) -> ToolResult:
        """할일 목록 조회"""
        try:
            filter_type = params.get("filter", "all").lower()
            
            # 필터 조건 생성
            filter_criteria = None
            if filter_type == "pending":
                filter_criteria = {
                    "and": [
                        {
                            "property": "Status",
                            "select": {
                                "does_not_equal": "Completed"
                            }
                        },
                        {
                            "property": "Status", 
                            "select": {
                                "does_not_equal": "Cancelled"
                            }
                        }
                    ]
                }
            elif filter_type == "completed":
                filter_criteria = {
                    "property": "Status",
                    "select": {
                        "equals": "Completed"
                    }
                }
            elif filter_type == "overdue":
                now = datetime.now(timezone.utc)
                filter_criteria = {
                    "and": [
                        {
                            "property": "Due Date",
                            "date": {
                                "before": now.isoformat()
                            }
                        },
                        {
                            "property": "Status",
                            "select": {
                                "does_not_equal": "Completed"
                            }
                        }
                    ]
                }
            
            # 정렬 제거 (데이터베이스에 Priority 속성이 없을 수 있음)
            sorts = None
            
            # 데이터베이스 쿼리
            if not self.database_id:
                raise NotionError("데이터베이스 ID가 설정되지 않았습니다")
            
            if not self.notion_client:
                raise NotionError("Notion 클라이언트가 초기화되지 않았습니다")
                
            result = await self.notion_client.query_database(
                database_id=self.database_id,
                filter_criteria=filter_criteria,
                sorts=sorts
            )
            
            todos = []
            for page in result.get("results", []):
                properties = page.get("properties", {})
                
                # 할일 정보 추출
                title = ""
                if "작업명" in properties and properties["작업명"].get("title"):
                    title_list = properties["작업명"]["title"]
                    if title_list and len(title_list) > 0 and title_list[0].get("text"):
                        title = title_list[0]["text"]["content"]
                
                description = ""
                if "작업설명" in properties and properties["작업설명"].get("rich_text"):
                    rich_text_list = properties["작업설명"]["rich_text"]
                    if rich_text_list and len(rich_text_list) > 0 and rich_text_list[0].get("text"):
                        description = rich_text_list[0]["text"]["content"]
                
                due_date = ""
                if "마감일" in properties and properties["마감일"].get("date"):
                    due_date = properties["마감일"]["date"]["start"]
                
                priority = ""
                if "우선순위" in properties and properties["우선순위"].get("select"):
                    priority = properties["우선순위"]["select"]["name"]
                
                status = ""
                completed = False
                if "작업상태" in properties and properties["작업상태"].get("status"):
                    status = properties["작업상태"]["status"]["name"]
                    completed = status == "완료"
                
                # 관계형 속성 - 경험/프로젝트 처리
                projects = []
                if "경험/프로젝트" in properties and properties["경험/프로젝트"].get("relation"):
                    relations = properties["경험/프로젝트"]["relation"]
                    for relation in relations:
                        relation_id = relation.get("id")
                        if relation_id:
                            try:
                                # 관계된 페이지의 제목 가져오기
                                page_info = await self.notion_client.get_page(relation_id)
                                page_props = page_info.get("properties", {})
                                
                                # 제목 속성 찾기 (여러 가능한 속성명 확인)
                                page_title = ""
                                for prop_name, prop_data in page_props.items():
                                    if prop_data.get("type") == "title":
                                        title_list = prop_data.get("title", [])
                                        if title_list and len(title_list) > 0 and title_list[0].get("text"):
                                            page_title = title_list[0]["text"]["content"]
                                        break
                                
                                if page_title:
                                    projects.append(page_title)
                            except Exception as e:
                                logger.warning(f"관계 페이지 조회 실패 ({relation_id}): {e}")
                
                todos.append({
                    "id": page.get("id", ""),
                    "title": title,
                    "description": description,
                    "due_date": due_date,
                    "priority": priority,
                    "status": status,
                    "completed": completed,
                    "projects": projects,  # 관계형 속성 추가
                    "url": page.get("url", "")
                })
            
            logger.info(f"할일 목록 조회 완료: {len(todos)}개 할일 ({filter_type})")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todos": todos,
                    "count": len(todos),
                    "filter": filter_type,
                    "message": f"{filter_type} 조건의 할일 {len(todos)}개를 조회했습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 목록 조회 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 목록 조회 중 오류 발생: {e}"
            )
    
    async def _get_todo(self, params: Dict[str, Any]) -> ToolResult:
        """단일 할일 조회"""
        try:
            await self._ensure_client()
            if self.notion_client is None:
                raise NotionError("Notion 클라이언트 초기화 실패")
            
            todo_id = params.get("todo_id") or params.get("id")
            if not todo_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="조회할 할일 ID가 필요합니다"
                )
            
            # 페이지 정보 조회
            page_info = await self.notion_client.get_page(todo_id)
            properties = page_info.get("properties", {})
            
            # 할일 정보 추출
            title = ""
            if "작업명" in properties and properties["작업명"].get("title"):
                title_list = properties["작업명"]["title"]
                if title_list and len(title_list) > 0 and title_list[0].get("text"):
                    title = title_list[0]["text"]["content"]
            
            description = ""
            if "작업설명" in properties and properties["작업설명"].get("rich_text"):
                rich_text_list = properties["작업설명"]["rich_text"]
                if rich_text_list and len(rich_text_list) > 0 and rich_text_list[0].get("text"):
                    description = rich_text_list[0]["text"]["content"]
            
            due_date = ""
            if "마감일" in properties and properties["마감일"].get("date"):
                due_date = properties["마감일"]["date"]["start"]
            
            priority = ""
            if "우선순위" in properties and properties["우선순위"].get("select"):
                priority = properties["우선순위"]["select"]["name"]
            
            status = ""
            completed = False
            if "작업상태" in properties and properties["작업상태"].get("status"):
                status = properties["작업상태"]["status"]["name"]
                completed = status == "완료"
            
            # 프로젝트 정보 추출
            projects = []
            if "경험/프로젝트" in properties and properties["경험/프로젝트"].get("relation"):
                relations = properties["경험/프로젝트"]["relation"]
                for relation in relations:
                    relation_id = relation.get("id")
                    if relation_id:
                        try:
                            project_page = await self.notion_client.get_page(relation_id)
                            project_props = project_page.get("properties", {})
                            
                            project_title = ""
                            for prop_name, prop_data in project_props.items():
                                if prop_data.get("type") == "title":
                                    title_list = prop_data.get("title", [])
                                    if title_list and len(title_list) > 0 and title_list[0].get("text"):
                                        project_title = title_list[0]["text"]["content"]
                                    break
                            
                            if project_title:
                                projects.append(project_title)
                        except Exception as e:
                            logger.warning(f"프로젝트 정보 조회 실패 ({relation_id}): {e}")
            
            todo_data = {
                "id": todo_id,
                "title": title,
                "description": description,
                "due_date": due_date,
                "priority": priority,
                "status": status,
                "completed": completed,
                "projects": projects,
                "url": page_info.get("url", ""),
                "created_time": page_info.get("created_time", ""),
                "last_edited_time": page_info.get("last_edited_time", "")
            }
            
            logger.info(f"할일 조회 완료: {title} (ID: {todo_id[:8]}...)")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo": todo_data,
                    "message": f"할일 '{title}' 조회가 완료되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 조회 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 조회 중 오류 발생: {e}"
            )
    
    async def _complete_todo(self, params: Dict[str, Any]) -> ToolResult:
        """할일 완료 처리"""
        try:
            await self._ensure_client()
            if self.notion_client is None:
                raise NotionError("Notion 클라이언트 초기화 실패")
            
            todo_id = params.get("todo_id") or params.get("id")
            if not todo_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="완료 처리할 할일 ID가 필요합니다"
                )
            
            # 완료 상태 설정 (기본값: 완료)
            completed = params.get("completed", True)
            if isinstance(completed, str):
                completed = completed.lower() in ["true", "1", "yes", "완료"]
            
            # 상태 업데이트할 속성 구성
            status_name = "완료" if completed else "진행 중"
            
            properties = {
                "작업상태": create_notion_property("status", status_name)
            }
            
            # 페이지 업데이트
            await self.notion_client.update_page(todo_id, properties=properties)
            
            # 업데이트된 할일 정보 조회
            updated_page = await self.notion_client.get_page(todo_id)
            title = ""
            if "작업명" in updated_page.get("properties", {}):
                title_prop = updated_page["properties"]["작업명"]
                if title_prop.get("title"):
                    title_list = title_prop["title"]
                    if title_list and len(title_list) > 0 and title_list[0].get("text"):
                        title = title_list[0]["text"]["content"]
            
            action_text = "완료 처리" if completed else "미완료로 변경"
            logger.info(f"할일 {action_text} 완료: {title} (ID: {todo_id[:8]}...)")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo_id": todo_id,
                    "title": title,
                    "completed": completed,
                    "status": status_name,
                    "message": f"할일 '{title}'이(가) {action_text}되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 완료 처리 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 완료 처리 중 오류 발생: {e}"
            )
    
    async def _update_todo(self, params: Dict[str, Any]) -> ToolResult:
        """할일 수정"""
        try:
            await self._ensure_client()
            if self.notion_client is None:
                raise NotionError("Notion 클라이언트 초기화 실패")
            
            todo_id = params.get("todo_id") or params.get("id")
            if not todo_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="수정할 할일 ID가 필요합니다"
                )
            
            # 업데이트할 속성들 구성
            properties = {}
            
            # 제목 업데이트
            if "title" in params:
                properties["작업명"] = create_notion_property("title", params["title"])
            
            # 설명 업데이트
            if "description" in params:
                properties["작업설명"] = create_notion_property("rich_text", params["description"])
            
            # 우선순위 업데이트
            if "priority" in params:
                priority_map = {"high": "높음", "medium": "중간", "low": "낮음"}
                priority_korean = priority_map.get(params["priority"].lower(), params["priority"])
                properties["우선순위"] = create_notion_property("select", priority_korean)
            
            # 마감일 업데이트
            if "due_date" in params:
                if params["due_date"]:
                    # 날짜 문자열 파싱
                    try:
                        if isinstance(params["due_date"], str):
                            # ISO 형식 시도
                            try:
                                due_date = datetime.fromisoformat(params["due_date"].replace('Z', '+00:00'))
                            except:
                                # 다른 형식들 시도
                                from dateutil import parser
                                due_date = parser.parse(params["due_date"])
                        else:
                            due_date = params["due_date"]
                        
                        properties["마감일"] = create_notion_property("date", due_date.isoformat())
                    except Exception as e:
                        logger.warning(f"날짜 파싱 실패: {e}, 원본값 사용")
                        properties["마감일"] = create_notion_property("date", str(params["due_date"]))
                else:
                    # 마감일 제거
                    properties["마감일"] = create_notion_property("date", None)
            
            if not properties:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="업데이트할 내용이 없습니다. title, description, priority, due_date 중 하나 이상을 지정해주세요"
                )
            
            # 페이지 업데이트
            await self.notion_client.update_page(todo_id, properties=properties)
            
            # 업데이트된 할일 정보 조회
            updated_page = await self.notion_client.get_page(todo_id)
            title = ""
            if "작업명" in updated_page.get("properties", {}):
                title_prop = updated_page["properties"]["작업명"]
                if title_prop.get("title"):
                    title_list = title_prop["title"]
                    if title_list and len(title_list) > 0 and title_list[0].get("text"):
                        title = title_list[0]["text"]["content"]
            
            updated_fields = list(properties.keys())
            logger.info(f"할일 수정 완료: {title} (ID: {todo_id[:8]}...), 수정된 필드: {updated_fields}")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo_id": todo_id,
                    "title": title,
                    "updated_fields": updated_fields,
                    "message": f"할일 '{title}'이(가) 성공적으로 수정되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 수정 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 수정 중 오류 발생: {e}"
            )
    
    async def _delete_todo(self, params: Dict[str, Any]) -> ToolResult:
        """할일 삭제"""
        try:
            await self._ensure_client()
            if self.notion_client is None:
                raise NotionError("Notion 클라이언트 초기화 실패")
            
            todo_id = params.get("todo_id") or params.get("id")
            if not todo_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="삭제할 할일 ID가 필요합니다"
                )
            
            # 삭제 전 할일 정보 조회 (로그용)
            try:
                page_info = await self.notion_client.get_page(todo_id)
                title = ""
                if "작업명" in page_info.get("properties", {}):
                    title_prop = page_info["properties"]["작업명"]
                    if title_prop.get("title"):
                        title_list = title_prop["title"]
                        if title_list and len(title_list) > 0 and title_list[0].get("text"):
                            title = title_list[0]["text"]["content"]
            except:
                title = "Unknown"
            
            # 페이지 삭제 (archived=True로 설정)
            await self.notion_client.update_page(todo_id, archived=True)
            
            logger.info(f"할일 삭제 완료: {title} (ID: {todo_id[:8]}...)")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo_id": todo_id,
                    "title": title,
                    "message": f"할일 '{title}'이(가) 성공적으로 삭제되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"할일 삭제 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 삭제 중 오류 발생: {e}"
            )
    
    async def execute(self, **params) -> ToolResult:
        """도구 실행"""
        try:
            await self._ensure_client()
            
            if not self.database_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="Notion 할일 데이터베이스 ID가 설정되지 않았습니다"
                )
            
            action = params.get("action", "").lower()
            
            if action == "create":
                return await self._create_todo(params)
            elif action == "list":
                return await self._list_todos(params)
            elif action == "get":
                return await self._get_todo(params)
            elif action == "update":
                return await self._update_todo(params)
            elif action == "delete":
                return await self._delete_todo(params)
            elif action == "complete":
                return await self._complete_todo(params)
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 작업: {action}"
                )
                
        except Exception as e:
            logger.error(f"할일 도구 실행 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"할일 도구 실행 중 오류 발생: {e}"
            )
