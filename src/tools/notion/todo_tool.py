"""
Notion 할일 관리 도구

Notion 할일 데이터베이스를 관리하는 MCP 도구입니다.
할일 추가, 수정, 삭제, 조회, 완료 처리 기능을 제공합니다.
"""

import asyncio
from datetime import datetime, timedelta
import re
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field

from ..base import BaseTool, ToolMetadata, ToolResult, ExecutionStatus, ToolCategory, ToolParameter, ParameterType
from ...config import Settings
from ...utils.logger import get_logger
from .client import NotionClient, NotionError, create_notion_property, create_text_block

logger = get_logger(__name__)


class TodoData(BaseModel):
    """할일 데이터"""
    title: str = Field(..., description="할일 제목")
    description: Optional[str] = Field(None, description="할일 설명")
    # 순수 LLM 원칙: LLM이 ISO 문자열을 생성하도록 하고, 여기서는 문자열/datetime 모두 허용
    due_date: Optional[Union[str, datetime]] = Field(None, description="마감일(ISO 문자열 또는 datetime)")
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
                description="수행할 작업: 'list'(할일목록조회), 'create'(할일생성), 'update'(할일수정), 'delete'(할일삭제), 'get'(특정할일조회), 'complete'(할일완료)",
                required=True,
                choices=["create", "update", "delete", "get", "list", "complete"]
            ),
            ToolParameter(
                name="target_title",
                type=ParameterType.STRING,
                description="대상 할일 제목 (todo_id가 없을 때 검색용)",
                required=False
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
                description="필터 조건 (기본: pending) — all | pending(완료 아님) | completed(완료) | overdue(기한 지남)",
                required=False
            ),
            ToolParameter(
                name="limit",
                type=ParameterType.INTEGER,
                description="조회할 최대 항목 수 (기본값: 5, 최대: 100)",
                required=False,
                default=5,
                min_value=1,
                max_value=100
            )
            ,
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="제목 부분 검색(contains) 토큰. 공백/단어 단위로 분해해 모두 포함하는 항목만 조회",
                required=False
            )
        ]
        
        return ToolMetadata(
            name="notion_todo",
            version="1.0.0",
            description="Notion 할일 데이터베이스에서 할일을 관리합니다. 할일 목록 조회시 action='list' 사용",
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
        """자연어나 ISO 형식의 날짜/시간을 파싱

        파싱 규칙(한국어 우선):
        - "오늘"/"내일"만 있으면 23:59가 아니라 기본 18:00로 설정하지 않고, 그대로 EOD 유지
        - "오늘 11시", "오전 11시", "오후 3시 30분", "11:20" 등 시간을 포함하면 해당 시각으로 설정(분 미지정시 00분)
        - 시간대 정보가 없으면 기본 시간대(Settings.default_timezone)
        """
        if not date_str:
            # 기본 시간대 (KST 등) 현재 시각 반환
            tz = ZoneInfo(self.settings.default_timezone)
            return datetime.now(tz)
        
        # ISO 형식 시도
        try:
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                # 시간대 정보가 없으면 기본 시간대 부여
                dt = dt.replace(tzinfo=ZoneInfo(self.settings.default_timezone))
            return dt
        except ValueError:
            pass
        
        # 자연어 파싱 (간단한 패턴들)
        now = datetime.now(ZoneInfo(self.settings.default_timezone))
        date_str_lower = date_str.lower().strip()
        import re

        # 시간 추출: 오전/오후, 시/분, 콜론 표기 지원
        ampm = None
        hour = None
        minute = 0

        # "오전/오후 HH시[MM분]" 패턴
        m = re.search(r'(오전|오후)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?', date_str_lower)
        if m:
            ampm = m.group(1)
            hour = int(m.group(2))
            if m.group(3):
                minute = int(m.group(3))
        # "HH:MM" 또는 "HH시[MM분]" 패턴
        if hour is None:
            m2 = re.search(r'(\d{1,2}):(\d{2})', date_str_lower)
            if m2:
                hour = int(m2.group(1))
                minute = int(m2.group(2))
        if hour is None:
            m3 = re.search(r'(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?', date_str_lower)
            if m3:
                hour = int(m3.group(1))
                if m3.group(2):
                    minute = int(m3.group(2))

        # 날짜 기준: 오늘/내일/다음 주
        base = now
        if '내일' in date_str_lower or 'tomorrow' in date_str_lower:
            base = now + timedelta(days=1)
        elif '다음 주' in date_str_lower or 'next week' in date_str_lower:
            base = now + timedelta(weeks=1)
        # '오늘'은 기본(now) 유지

        if hour is not None:
            # 오전/오후 보정
            if ampm == '오후' and hour != 12:
                hour += 12
            if ampm == '오전' and hour == 12:
                hour = 0
            return base.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # 시간 지정이 전혀 없으면 EOD로 설정 (기존 동작 유지)
        if date_str_lower in ['오늘', 'today']:
            return now.replace(hour=23, minute=59, second=0, microsecond=0)
        if date_str_lower in ['내일', 'tomorrow']:
            return (now + timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        if date_str_lower in ['다음 주', 'next week']:
            return (now + timedelta(weeks=1)).replace(hour=23, minute=59, second=0, microsecond=0)

        # 기타는 보수적으로 EOD
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
            
            # 순수 LLM 원칙: due_date는 ISO 문자열 또는 datetime으로 바로 사용
            due_date = params.get("due_date") if params.get("due_date") else None
            
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
            
            # due_date 안전한 처리
            due_date_str = None
            if due_date:
                if hasattr(due_date, 'isoformat'):
                    due_date_str = due_date.isoformat()
                else:
                    due_date_str = str(due_date)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "todo_id": page_id,
                    "title": title,
                    "due_date": due_date_str,
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
            # filter 기본은 'pending' (완료 아님)
            raw_filter = (params.get("filter") or "pending").strip().lower()
            # 한국어/자연어 동의어 매핑
            synonym_map = {
                "pending": {"pending", "미완료", "완료아님", "완료 아님", "예정", "진행중", "진행 중"},
                "completed": {"completed", "완료"},
                "overdue": {"overdue", "연체", "기한지남", "기한 지남", "지남"},
                "all": {"all", "전체", "모두"},
            }
            def _canon_filter(s: str) -> str:
                for k, vs in synonym_map.items():
                    if s in vs:
                        return k
                return s
            filter_type = _canon_filter(raw_filter)
            limit = params.get("limit", 5)  # 기본값을 5개로 설정
            query = (params.get("query") or "").strip()
            
            # limit 유효성 검사
            if isinstance(limit, str):
                try:
                    limit = int(limit)
                except ValueError:
                    limit = 5
            
            # 최대 100개로 제한
            limit = min(max(1, limit), 100)
            
            # 필터 조건 생성 (한국어 속성 기준)
            criteria: List[Dict[str, Any]] = []
            if filter_type == "pending":
                criteria.append({"property": "작업상태", "status": {"does_not_equal": "완료"}})
            elif filter_type == "completed":
                criteria.append({"property": "작업상태", "status": {"equals": "완료"}})
            elif filter_type == "overdue":
                now_local = datetime.now(ZoneInfo(self.settings.default_timezone))
                criteria.append({"property": "마감일", "date": {"before": now_local.isoformat()}})
                criteria.append({"property": "작업상태", "status": {"does_not_equal": "완료"}})

            # 제목 부분 검색(query): 공백/단어 단위 토큰 모두 포함
            if query:
                tokens = re.findall(r"[\w가-힣]+", query)
                for tk in tokens:
                    criteria.append({"property": "작업명", "title": {"contains": tk}})

            filter_criteria = {"and": criteria} if criteria else None

            # 정렬: 마감일 오름차순(있을 때)
            sorts = [{"property": "마감일", "direction": "ascending"}] if filter_type in {"pending", "overdue"} else None
            
            # 데이터베이스 쿼리
            if not self.database_id:
                raise NotionError("데이터베이스 ID가 설정되지 않았습니다")
            
            if not self.notion_client:
                raise NotionError("Notion 클라이언트가 초기화되지 않았습니다")
                
            result = await self.notion_client.query_database(
                database_id=self.database_id,
                filter_criteria=filter_criteria,
                sorts=sorts,
                page_size=limit  # 조회할 페이지 수 제한
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
            target_title = params.get("target_title")
            
            # ID가 없고 target_title이 있으면 제목으로 검색해서 ID 찾기
            if not todo_id and target_title:
                # 할일 목록 조회해서 매칭되는 것 찾기
                list_result = await self._list_todos({"filter": "pending"})
                if list_result.status == ExecutionStatus.SUCCESS and list_result.data:
                    todos = list_result.data.get("todos", [])
                    for todo in todos:
                        if target_title.lower() in todo.get("title", "").lower():
                            todo_id = todo.get("id")
                            logger.info(f"제목으로 할일 ID 찾음: {target_title} -> {todo_id}")
                            break
            
            if not todo_id:
                error_msg = "완료 처리할 할일 ID가 필요합니다"
                if target_title:
                    error_msg += f" ('{target_title}' 제목의 할일을 찾을 수 없습니다)"
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=error_msg
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
            
            # 상태 업데이트
            if "status" in params:
                try:
                    raw = str(params["status"]).strip().lower()
                    status_map = {
                        "진행중": "진행 중",
                        "진행 중": "진행 중",
                        "in progress": "진행 중",
                        "progress": "진행 중",
                        "완료": "완료",
                        "complete": "완료",
                        "completed": "완료",
                        "done": "완료",
                        "not started": "Not Started",
                        "미완료": "Not Started",
                        "시작 전": "Not Started",
                    }
                    status_name = status_map.get(raw, params["status"])  # 미지정 값은 그대로 시도
                    properties["작업상태"] = create_notion_property("status", status_name)
                except Exception as _e:
                    logger.warning(f"상태 업데이트 매핑 실패: {_e}")
            
            # 마감일 업데이트
            if "due_date" in params:
                # LLM이 제공한 값을 그대로 사용(ISO 문자열/ datetime 모두 지원)
                if params["due_date"]:
                    properties["마감일"] = create_notion_property("date", params["due_date"])
                else:
                    properties["마감일"] = create_notion_property("date", None)
            
            if not properties:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="업데이트할 내용이 없습니다. title, description, priority, due_date, status 중 하나 이상을 지정해주세요"
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
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """도구 실행"""
        try:
            await self._ensure_client()
            
            if not self.database_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="Notion 할일 데이터베이스 ID가 설정되지 않았습니다"
                )
            
            action = parameters.get("action", "").lower()
            
            if action == "create":
                return await self._create_todo(parameters)
            elif action == "list":
                return await self._list_todos(parameters)
            elif action == "get":
                return await self._get_todo(parameters)
            elif action == "update":
                return await self._update_todo(parameters)
            elif action == "delete":
                return await self._delete_todo(parameters)
            elif action == "complete":
                return await self._complete_todo(parameters)
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
