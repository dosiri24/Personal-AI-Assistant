#!/usr/bin/env python3
"""
Apple MCP Tools
Apple 앱들을 MCP 도구로 등록하여 AI 에이전트가 사용할 수 있게 함
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from .base_tool import BaseTool, ToolMetadata, ToolCategory, ToolResult, ExecutionStatus
from .apple_client import AppleAppsManager


class AppleContactsTool(BaseTool):
    """Apple Contacts MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_contacts",
            version="1.0.0",
            description="Apple Contacts 앱과 상호작용하여 연락처를 검색하고 조회합니다.",
            category=ToolCategory.COMMUNICATION,
            tags=["apple", "contacts", "search"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "search":
                name = parameters.get("name")
                contacts = await self.apple_manager.contacts.search_contacts(name)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "contacts": contacts,
                        "count": len(contacts),
                        "message": f"연락처 {len(contacts)}개를 찾았습니다."
                    }
                )
            
            elif action == "find_by_phone":
                phone = parameters.get("phone")
                if not phone:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="전화번호가 필요합니다."
                    )
                
                contact = await self.apple_manager.contacts.find_contact_by_phone(phone)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "contact": contact,
                        "found": contact is not None,
                        "message": "연락처를 찾았습니다." if contact else "해당 전화번호의 연락처를 찾을 수 없습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Contacts 오류: {str(e)}"
            )


class AppleNotesTool(BaseTool):
    """Apple Notes MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_notes",
            version="1.0.0",
            description="Apple Notes 앱과 상호작용하여 노트를 생성, 검색, 조회합니다.",
            category=ToolCategory.PRODUCTIVITY,
            tags=["apple", "notes", "create", "search"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "create":
                title = parameters.get("title")
                body = parameters.get("body")
                folder_name = parameters.get("folder_name", "Claude")
                
                if not title or not body:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="제목과 내용이 필요합니다."
                    )
                
                result = await self.apple_manager.notes.create_note(title, body, folder_name)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "title": title,
                        "folder": folder_name,
                        "message": f"노트 '{title}'를 생성했습니다."
                    }
                )
            
            elif action == "search":
                search_text = parameters.get("search_text")
                if not search_text:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색 텍스트가 필요합니다."
                    )
                
                notes = await self.apple_manager.notes.search_notes(search_text)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "notes": notes,
                        "count": len(notes),
                        "search_text": search_text,
                        "message": f"'{search_text}' 검색 결과: {len(notes)}개 노트"
                    }
                )
            
            elif action == "list":
                folder_name = parameters.get("folder_name")
                notes = await self.apple_manager.notes.list_notes(folder_name)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "notes": notes,
                        "count": len(notes),
                        "folder": folder_name,
                        "message": f"노트 목록: {len(notes)}개"
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Notes 오류: {str(e)}"
            )


class AppleMessagesTool(BaseTool):
    """Apple Messages MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_messages",
            version="1.0.0",
            description="Apple Messages 앱과 상호작용하여 메시지를 전송, 읽기, 예약합니다.",
            category=ToolCategory.COMMUNICATION,
            tags=["apple", "messages", "send", "read"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "send":
                phone_number = parameters.get("phone_number")
                message = parameters.get("message")
                
                if not phone_number or not message:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="전화번호와 메시지가 필요합니다."
                    )
                
                result = await self.apple_manager.messages.send_message(phone_number, message)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "phone_number": phone_number,
                        "message": message,
                        "message": f"{phone_number}로 메시지를 전송했습니다."
                    }
                )
            
            elif action == "read":
                phone_number = parameters.get("phone_number")
                limit = parameters.get("limit", 10)
                
                if not phone_number:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="전화번호가 필요합니다."
                    )
                
                messages = await self.apple_manager.messages.read_messages(phone_number, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "messages": messages,
                        "count": len(messages),
                        "phone_number": phone_number,
                        "message": f"{phone_number}와의 메시지 {len(messages)}개를 조회했습니다."
                    }
                )
            
            elif action == "unread":
                limit = parameters.get("limit", 10)
                messages = await self.apple_manager.messages.get_unread_messages(limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "messages": messages,
                        "count": len(messages),
                        "message": f"읽지 않은 메시지 {len(messages)}개를 조회했습니다."
                    }
                )
            
            elif action == "schedule":
                phone_number = parameters.get("phone_number")
                message = parameters.get("message")
                scheduled_time = parameters.get("scheduled_time")
                
                if not phone_number or not message or not scheduled_time:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="전화번호, 메시지, 예약 시간이 필요합니다."
                    )
                
                result = await self.apple_manager.messages.schedule_message(phone_number, message, scheduled_time)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "phone_number": phone_number,
                        "scheduled_time": scheduled_time,
                        "message": f"{phone_number}로 {scheduled_time}에 메시지를 예약했습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Messages 오류: {str(e)}"
            )


class AppleMailTool(BaseTool):
    """Apple Mail MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_mail",
            version="1.0.0",
            description="Apple Mail 앱과 상호작용하여 이메일을 전송, 검색, 조회합니다.",
            category=ToolCategory.COMMUNICATION,
            tags=["apple", "mail", "email", "send"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "send":
                to = parameters.get("to")
                subject = parameters.get("subject")
                body = parameters.get("body")
                cc = parameters.get("cc")
                bcc = parameters.get("bcc")
                
                if not to or not subject or not body:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="수신자, 제목, 내용이 필요합니다."
                    )
                
                result = await self.apple_manager.mail.send_email(to, subject, body, cc, bcc)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "to": to,
                        "subject": subject,
                        "message": f"{to}로 이메일을 전송했습니다."
                    }
                )
            
            elif action == "unread":
                account = parameters.get("account")
                mailbox = parameters.get("mailbox")
                limit = parameters.get("limit", 10)
                
                emails = await self.apple_manager.mail.get_unread_emails(account, mailbox, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "emails": emails,
                        "count": len(emails),
                        "account": account,
                        "mailbox": mailbox,
                        "message": f"읽지 않은 이메일 {len(emails)}개를 조회했습니다."
                    }
                )
            
            elif action == "search":
                search_term = parameters.get("search_term")
                account = parameters.get("account")
                limit = parameters.get("limit", 10)
                
                if not search_term:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색어가 필요합니다."
                    )
                
                emails = await self.apple_manager.mail.search_emails(search_term, account, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "emails": emails,
                        "count": len(emails),
                        "search_term": search_term,
                        "message": f"'{search_term}' 검색 결과: {len(emails)}개 이메일"
                    }
                )
            
            elif action == "accounts":
                accounts = await self.apple_manager.mail.get_accounts()
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "accounts": accounts,
                        "count": len(accounts),
                        "message": f"이메일 계정 {len(accounts)}개를 조회했습니다."
                    }
                )
            
            elif action == "mailboxes":
                account = parameters.get("account")
                mailboxes = await self.apple_manager.mail.get_mailboxes(account)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "mailboxes": mailboxes,
                        "count": len(mailboxes),
                        "account": account,
                        "message": f"메일박스 {len(mailboxes)}개를 조회했습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Mail 오류: {str(e)}"
            )


class AppleRemindersTool(BaseTool):
    """Apple Reminders MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_reminders",
            version="1.0.0",
            description="Apple Reminders 앱과 상호작용하여 미리 알림을 생성, 검색, 조회합니다.",
            category=ToolCategory.PRODUCTIVITY,
            tags=["apple", "reminders", "create", "search"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "create":
                name = parameters.get("name")
                list_name = parameters.get("list_name")
                notes = parameters.get("notes")
                due_date = parameters.get("due_date")
                
                if not name:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="미리 알림 이름이 필요합니다."
                    )
                
                result = await self.apple_manager.reminders.create_reminder(name, list_name, notes, due_date)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "name": name,
                        "list_name": list_name,
                        "due_date": due_date,
                        "message": f"미리 알림 '{name}'을 생성했습니다."
                    }
                )
            
            elif action == "search":
                search_text = parameters.get("search_text")
                if not search_text:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색 텍스트가 필요합니다."
                    )
                
                reminders = await self.apple_manager.reminders.search_reminders(search_text)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "reminders": reminders,
                        "count": len(reminders),
                        "search_text": search_text,
                        "message": f"'{search_text}' 검색 결과: {len(reminders)}개 미리 알림"
                    }
                )
            
            elif action == "list":
                reminders = await self.apple_manager.reminders.list_reminders()
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "reminders": reminders,
                        "count": len(reminders),
                        "message": f"미리 알림 목록: {len(reminders)}개"
                    }
                )
            
            elif action == "open":
                search_text = parameters.get("search_text")
                if not search_text:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색 텍스트가 필요합니다."
                    )
                
                result = await self.apple_manager.reminders.open_reminder(search_text)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "search_text": search_text,
                        "message": f"미리 알림을 열었습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Reminders 오류: {str(e)}"
            )


class AppleCalendarTool(BaseTool):
    """Apple Calendar MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_calendar",
            version="1.0.0",
            description="Apple Calendar 앱과 상호작용하여 이벤트를 생성, 검색, 조회합니다.",
            category=ToolCategory.PRODUCTIVITY,
            tags=["apple", "calendar", "events", "create"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "create":
                title = parameters.get("title")
                start_date = parameters.get("start_date")
                end_date = parameters.get("end_date")
                location = parameters.get("location")
                notes = parameters.get("notes")
                is_all_day = parameters.get("is_all_day", False)
                calendar_name = parameters.get("calendar_name")
                
                if not title or not start_date or not end_date:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="제목, 시작 시간, 종료 시간이 필요합니다."
                    )
                
                result = await self.apple_manager.calendar.create_event(
                    title, start_date, end_date, location, notes, is_all_day, calendar_name
                )
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "title": title,
                        "start_date": start_date,
                        "end_date": end_date,
                        "location": location,
                        "message": f"이벤트 '{title}'를 생성했습니다."
                    }
                )
            
            elif action == "search":
                search_text = parameters.get("search_text")
                from_date = parameters.get("from_date")
                to_date = parameters.get("to_date")
                limit = parameters.get("limit", 10)
                
                if not search_text:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색 텍스트가 필요합니다."
                    )
                
                events = await self.apple_manager.calendar.search_events(search_text, from_date, to_date, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "events": events,
                        "count": len(events),
                        "search_text": search_text,
                        "message": f"'{search_text}' 검색 결과: {len(events)}개 이벤트"
                    }
                )
            
            elif action == "list":
                from_date = parameters.get("from_date")
                to_date = parameters.get("to_date")
                limit = parameters.get("limit", 10)
                
                events = await self.apple_manager.calendar.list_events(from_date, to_date, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "events": events,
                        "count": len(events),
                        "from_date": from_date,
                        "to_date": to_date,
                        "message": f"이벤트 목록: {len(events)}개"
                    }
                )
            
            elif action == "open":
                event_id = parameters.get("event_id")
                if not event_id:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="이벤트 ID가 필요합니다."
                    )
                
                result = await self.apple_manager.calendar.open_event(event_id)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "event_id": event_id,
                        "message": f"이벤트를 열었습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Calendar 오류: {str(e)}"
            )


class AppleMapsTool(BaseTool):
    """Apple Maps MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        super().__init__()
        self.apple_manager = apple_manager
    
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="apple_maps",
            version="1.0.0",
            description="Apple Maps 앱과 상호작용하여 위치 검색, 길찾기, 가이드 관리를 합니다.",
            category=ToolCategory.SYSTEM,
            tags=["apple", "maps", "location", "directions"]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        action = parameters.get("action")
        
        try:
            if action == "search":
                query = parameters.get("query")
                limit = parameters.get("limit", 10)
                
                if not query:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="검색어가 필요합니다."
                    )
                
                locations = await self.apple_manager.maps.search_locations(query, limit)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "locations": locations,
                        "count": len(locations),
                        "query": query,
                        "message": f"'{query}' 검색 결과: {len(locations)}개 위치"
                    }
                )
            
            elif action == "save":
                name = parameters.get("name")
                address = parameters.get("address")
                
                if not name or not address:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="위치 이름과 주소가 필요합니다."
                    )
                
                result = await self.apple_manager.maps.save_location(name, address)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "name": name,
                        "address": address,
                        "message": f"위치 '{name}'을 저장했습니다."
                    }
                )
            
            elif action == "directions":
                from_address = parameters.get("from_address")
                to_address = parameters.get("to_address")
                transport_type = parameters.get("transport_type", "driving")
                
                if not from_address or not to_address:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="출발지와 목적지 주소가 필요합니다."
                    )
                
                result = await self.apple_manager.maps.get_directions(from_address, to_address, transport_type)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "from_address": from_address,
                        "to_address": to_address,
                        "transport_type": transport_type,
                        "message": f"{from_address}에서 {to_address}로의 길찾기 결과"
                    }
                )
            
            elif action == "pin":
                name = parameters.get("name")
                address = parameters.get("address")
                
                if not name or not address:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="핀 이름과 주소가 필요합니다."
                    )
                
                result = await self.apple_manager.maps.drop_pin(name, address)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "name": name,
                        "address": address,
                        "message": f"'{name}' 핀을 드롭했습니다."
                    }
                )
            
            elif action == "create_guide":
                guide_name = parameters.get("guide_name")
                
                if not guide_name:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="가이드 이름이 필요합니다."
                    )
                
                result = await self.apple_manager.maps.create_guide(guide_name)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "guide_name": guide_name,
                        "message": f"가이드 '{guide_name}'을 생성했습니다."
                    }
                )
            
            elif action == "add_to_guide":
                guide_name = parameters.get("guide_name")
                address = parameters.get("address")
                
                if not guide_name or not address:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="가이드 이름과 주소가 필요합니다."
                    )
                
                result = await self.apple_manager.maps.add_to_guide(guide_name, address)
                return ToolResult(
                    status=ExecutionStatus.SUCCESS,
                    data={
                        "result": result,
                        "guide_name": guide_name,
                        "address": address,
                        "message": f"가이드 '{guide_name}'에 위치를 추가했습니다."
                    }
                )
            
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 작업: {action}"
                )
        
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Apple Maps 오류: {str(e)}"
            )


def register_apple_tools(apple_manager: AppleAppsManager) -> List[BaseTool]:
    """Apple MCP 도구들을 등록"""
    return [
        AppleContactsTool(apple_manager),
        AppleNotesTool(apple_manager),
        AppleMessagesTool(apple_manager),
        AppleMailTool(apple_manager),
        AppleRemindersTool(apple_manager),
        AppleCalendarTool(apple_manager),
        AppleMapsTool(apple_manager)
    ]


# 편의를 위한 팩토리 함수
def create_apple_tools_with_manager(server_path: str = "external/apple-mcp") -> tuple[AppleAppsManager, List[BaseTool]]:
    """Apple Apps Manager와 도구들을 함께 생성"""
    apple_manager = AppleAppsManager(server_path)
    tools = register_apple_tools(apple_manager)
    return apple_manager, tools
