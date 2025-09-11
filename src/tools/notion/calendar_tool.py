"""
Notion 캘린더 도구

Notion 캘린더 데이터베이스를 관리하는 MCP 도구입니다.
일정 추가, 수정, 삭제, 조회 기능을 제공합니다.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field
import re

from ..base import BaseTool, ToolMetadata, ToolResult, ExecutionStatus, ToolCategory, ToolParameter, ParameterType
from ...config import Settings
from ...utils.logger import get_logger
from .client import NotionClient, NotionError, create_notion_property, create_text_block

logger = get_logger(__name__)


class CalendarEventData(BaseModel):
    """캘린더 이벤트 데이터"""
    title: str = Field(..., description="이벤트 제목")
    start_date: datetime = Field(..., description="시작 날짜/시간")
    end_date: Optional[datetime] = Field(None, description="종료 날짜/시간")
    description: Optional[str] = Field(None, description="이벤트 설명")
    location: Optional[str] = Field(None, description="장소")
    attendees: Optional[List[str]] = Field(None, description="참석자 목록")
    priority: Optional[str] = Field("Medium", description="우선순위 (High, Medium, Low)")
    category: Optional[str] = Field("Other", description="카테고리")
    is_all_day: bool = Field(False, description="종일 이벤트 여부")
    reminder_minutes: Optional[int] = Field(None, description="알림 시간 (분 전)")


class CalendarTool(BaseTool):
    """
    Notion 캘린더 관리 도구
    
    캘린더 데이터베이스에서 일정을 추가, 수정, 삭제, 조회하는 기능을 제공합니다.
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        캘린더 도구 초기화
        
        Args:
            settings: 애플리케이션 설정
        """
        if settings is None:
            settings = Settings()
        
        self.settings = settings
        self.notion_client: Optional[NotionClient] = None
        self.database_id = None  # 캘린더 데이터베이스는 별도로 생성하지 않음
        
        super().__init__()
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        parameters = [
            ToolParameter(
                name="action",
                type=ParameterType.STRING,
                description="수행할 작업 (create, update, delete, get, list)",
                required=True,
                choices=["create", "update", "delete", "get", "list"]
            ),
            ToolParameter(
                name="title",
                type=ParameterType.STRING,
                description="이벤트 제목",
                required=False
            ),
            ToolParameter(
                name="start_date",
                type=ParameterType.STRING,
                description="시작 날짜/시간 (ISO 형식 또는 자연어)",
                required=False
            ),
            ToolParameter(
                name="end_date",
                type=ParameterType.STRING,
                description="종료 날짜/시간 (ISO 형식 또는 자연어)",
                required=False
            ),
            ToolParameter(
                name="description",
                type=ParameterType.STRING,
                description="이벤트 설명",
                required=False
            ),
            ToolParameter(
                name="location",
                type=ParameterType.STRING,
                description="장소",
                required=False
            ),
            ToolParameter(
                name="attendees",
                type=ParameterType.ARRAY,
                description="참석자 목록",
                required=False
            ),
            ToolParameter(
                name="priority",
                type=ParameterType.STRING,
                description="우선순위",
                required=False,
                choices=["High", "Medium", "Low"]
            ),
            ToolParameter(
                name="category",
                type=ParameterType.STRING,
                description="카테고리",
                required=False
            ),
            ToolParameter(
                name="is_all_day",
                type=ParameterType.BOOLEAN,
                description="종일 이벤트 여부",
                required=False
            ),
            ToolParameter(
                name="reminder_minutes",
                type=ParameterType.INTEGER,
                description="알림 시간 (분 전)",
                required=False
            ),
            ToolParameter(
                name="event_id",
                type=ParameterType.STRING,
                description="이벤트 ID (수정/삭제/조회용)",
                required=False
            ),
            ToolParameter(
                name="date_range",
                type=ParameterType.STRING,
                description="조회할 날짜 범위 (today, week, month, 또는 특정 날짜)",
                required=False
            )
        ]
        
        return ToolMetadata(
            name="notion_calendar",
            version="1.0.0",
            description="Notion 캘린더 데이터베이스에서 일정을 관리합니다",
            category=ToolCategory.PRODUCTIVITY,
            parameters=parameters,
            tags=["notion", "calendar", "schedule", "productivity"]
        )
    
    async def _ensure_client(self):
        """Notion 클라이언트 초기화"""
        if self.notion_client is None:
            from .client import NotionClient
            self.notion_client = NotionClient(use_async=True)
            
            # 연결 테스트
            if not await self.notion_client.test_connection():
                raise NotionError("Notion API 연결에 실패했습니다")
    
    def _parse_datetime(self, date_str: str) -> datetime:
        """자연어나 ISO 형식의 날짜/시간을 파싱"""
        if not date_str:
            tz = ZoneInfo(self.settings.default_timezone)
            return datetime.now(tz)
        
        # ISO 형식 시도
        try:
            # 'Z' 접미사 처리
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo(self.settings.default_timezone))
            return dt
        except ValueError:
            pass
        
        # 자연어 파싱 (간단한 패턴들)
        now = datetime.now(ZoneInfo(self.settings.default_timezone))
        date_str_lower = date_str.lower().strip()
        
        # 오늘, 내일, 모레
        if date_str_lower in ['오늘', 'today']:
            return now.replace(hour=9, minute=0, second=0, microsecond=0)
        elif date_str_lower in ['내일', 'tomorrow']:
            return (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        elif date_str_lower in ['모레', 'day after tomorrow']:
            return (now + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
        
        # 시간 패턴 매칭 (예: "오후 3시", "15:30")
        time_patterns = [
            (r'오후\s*(\d{1,2})시', lambda m: int(m.group(1)) + 12 if int(m.group(1)) != 12 else 12),
            (r'오전\s*(\d{1,2})시', lambda m: int(m.group(1)) if int(m.group(1)) != 12 else 0),
            (r'(\d{1,2})시', lambda m: int(m.group(1))),
            (r'(\d{1,2}):(\d{2})', lambda m: (int(m.group(1)), int(m.group(2))))
        ]
        
        result_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        
        for pattern, handler in time_patterns:
            match = re.search(pattern, date_str_lower)
            if match:
                if pattern.endswith(r':(\d{2})'):  # HH:MM 형식
                    hour, minute = handler(match)
                    result_time = result_time.replace(hour=hour, minute=minute)
                else:  # 시간만
                    hour = handler(match)
                    result_time = result_time.replace(hour=hour, minute=0)
                break
        
        # 날짜 패턴 매칭 (예: "다음 주", "다음 달")
        if '다음 주' in date_str_lower or 'next week' in date_str_lower:
            result_time += timedelta(weeks=1)
        elif '다음 달' in date_str_lower or 'next month' in date_str_lower:
            if result_time.month == 12:
                result_time = result_time.replace(year=result_time.year + 1, month=1)
            else:
                result_time = result_time.replace(month=result_time.month + 1)
        
        return result_time
    
    def _create_calendar_properties(self, event: CalendarEventData) -> Dict[str, Any]:
        """캘린더 이벤트를 Notion 속성으로 변환"""
        properties = {
            "Name": create_notion_property("title", event.title)
        }
        
        # 날짜 처리
        if event.is_all_day:
            properties["Date"] = {
                "date": {
                    "start": event.start_date.date().isoformat(),
                    "end": event.end_date.date().isoformat() if event.end_date else None
                }
            }
        else:
            properties["Date"] = {
                "date": {
                    "start": event.start_date.isoformat(),
                    "end": event.end_date.isoformat() if event.end_date else None
                }
            }
        
        # 선택적 속성들
        if event.description:
            properties["Description"] = create_notion_property("rich_text", event.description)
        
        if event.location:
            properties["Location"] = create_notion_property("rich_text", event.location)
        
        if event.priority:
            properties["Priority"] = create_notion_property("select", event.priority)
        
        if event.category:
            properties["Category"] = create_notion_property("select", event.category)
        
        if event.attendees:
            properties["Attendees"] = create_notion_property("multi_select", event.attendees)
        
        properties["All Day"] = create_notion_property("checkbox", event.is_all_day)
        
        if event.reminder_minutes is not None:
            properties["Reminder (minutes)"] = create_notion_property("number", event.reminder_minutes)
        
        return properties
    
    async def _create_event(self, params: Dict[str, Any]) -> ToolResult:
        """새 일정 생성"""
        try:
            # 필수 파라미터 확인
            title = params.get("title")
            if not title:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="제목이 필요합니다"
                )
            
            # 날짜 파싱
            start_date_str = params.get("start_date", "")
            start_date = self._parse_datetime(start_date_str)
            
            end_date = None
            if params.get("end_date"):
                end_date = self._parse_datetime(params["end_date"])
            elif not params.get("is_all_day", False):
                # 종료 시간이 없으면 1시간 후로 설정
                end_date = start_date + timedelta(hours=1)
            
            # 이벤트 데이터 생성
            event = CalendarEventData(
                title=title,
                start_date=start_date,
                end_date=end_date,
                description=params.get("description"),
                location=params.get("location"),
                attendees=params.get("attendees"),
                priority=params.get("priority", "Medium"),
                category=params.get("category", "Other"),
                is_all_day=params.get("is_all_day", False),
                reminder_minutes=params.get("reminder_minutes")
            )
            
            # Notion 속성 생성
            properties = self._create_calendar_properties(event)
            
            # 설명이 있으면 페이지 내용으로 추가
            children = []
            if event.description:
                children.append(create_text_block(event.description))
            
            # 페이지 생성
            if not self.database_id:
                raise NotionError("데이터베이스 ID가 설정되지 않았습니다")
            
            if not self.notion_client:
                raise NotionError("Notion 클라이언트가 초기화되지 않았습니다")
            
            result = await self.notion_client.create_page(
                parent_id=self.database_id,
                title=title,
                properties=properties,
                children=children if children else None
            )
            
            page_id = result.get("id", "")
            page_url = result.get("url", "")
            
            logger.info(f"캘린더 이벤트 생성 완료: {title} ({page_id})")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "event_id": page_id,
                    "title": title,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat() if end_date else None,
                    "url": page_url,
                    "message": f"일정 '{title}'이 성공적으로 생성되었습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"일정 생성 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"일정 생성 중 오류 발생: {e}"
            )
    
    async def _list_events(self, params: Dict[str, Any]) -> ToolResult:
        """일정 목록 조회"""
        try:
            date_range = params.get("date_range", "week").lower()
            now = datetime.now(timezone.utc)
            
            # 날짜 범위 계산
            if date_range == "today":
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
            elif date_range == "week":
                # 이번 주 (월요일부터)
                days_since_monday = now.weekday()
                start_date = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=7)
            elif date_range == "month":
                # 이번 달
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if now.month == 12:
                    end_date = start_date.replace(year=now.year + 1, month=1)
                else:
                    end_date = start_date.replace(month=now.month + 1)
            else:
                # 특정 날짜 또는 기본값 (일주일)
                try:
                    target_date = self._parse_datetime(date_range)
                    start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = start_date + timedelta(days=1)
                except:
                    start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_date = start_date + timedelta(days=7)
            
            # 날짜 필터 생성
            filter_criteria = {
                "and": [
                    {
                        "property": "Date",
                        "date": {
                            "on_or_after": start_date.isoformat()
                        }
                    },
                    {
                        "property": "Date", 
                        "date": {
                            "before": end_date.isoformat()
                        }
                    }
                ]
            }
            
            # 정렬 (시작 날짜순)
            sorts = [
                {
                    "property": "Date",
                    "direction": "ascending"
                }
            ]
            
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
            
            events = []
            for page in result.get("results", []):
                properties = page.get("properties", {})
                
                # 이벤트 정보 추출
                title = ""
                if "Name" in properties and properties["Name"].get("title"):
                    title = properties["Name"]["title"][0]["text"]["content"]
                
                date_info = properties.get("Date", {}).get("date", {})
                start_date_str = date_info.get("start", "")
                end_date_str = date_info.get("end", "")
                
                description = ""
                if "Description" in properties and properties["Description"].get("rich_text"):
                    description = properties["Description"]["rich_text"][0]["text"]["content"]
                
                location = ""
                if "Location" in properties and properties["Location"].get("rich_text"):
                    location = properties["Location"]["rich_text"][0]["text"]["content"]
                
                priority = ""
                if "Priority" in properties and properties["Priority"].get("select"):
                    priority = properties["Priority"]["select"]["name"]
                
                category = ""
                if "Category" in properties and properties["Category"].get("select"):
                    category = properties["Category"]["select"]["name"]
                
                events.append({
                    "id": page.get("id", ""),
                    "title": title,
                    "start_date": start_date_str,
                    "end_date": end_date_str,
                    "description": description,
                    "location": location,
                    "priority": priority,
                    "category": category,
                    "url": page.get("url", "")
                })
            
            logger.info(f"일정 목록 조회 완료: {len(events)}개 이벤트 ({date_range})")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "events": events,
                    "count": len(events),
                    "date_range": date_range,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "message": f"{date_range} 기간의 일정 {len(events)}개를 조회했습니다"
                }
            )
            
        except Exception as e:
            logger.error(f"일정 목록 조회 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"일정 목록 조회 중 오류 발생: {e}"
            )
    
    async def execute(self, **params) -> ToolResult:
        """도구 실행"""
        try:
            await self._ensure_client()
            
            if not self.database_id:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="Notion 캘린더 데이터베이스 ID가 설정되지 않았습니다"
                )
            
            action = params.get("action", "").lower()
            
            if action == "create":
                return await self._create_event(params)
            elif action == "list":
                return await self._list_events(params)
            elif action == "get":
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="단일 이벤트 조회 기능은 아직 구현되지 않았습니다"
                )
            elif action == "update":
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="이벤트 수정 기능은 아직 구현되지 않았습니다"
                )
            elif action == "delete":
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="이벤트 삭제 기능은 아직 구현되지 않았습니다"
                )
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 작업: {action}"
                )
                
        except Exception as e:
            logger.error(f"캘린더 도구 실행 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"캘린더 도구 실행 중 오류 발생: {e}"
            )
