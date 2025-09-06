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
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "find_by_phone"],
                    "description": "수행할 작업: search (이름으로 검색), find_by_phone (전화번호로 찾기)"
                },
                "name": {
                    "type": "string",
                    "description": "검색할 연락처 이름 (action이 search인 경우)"
                },
                "phone": {
                    "type": "string",
                    "description": "검색할 전화번호 (action이 find_by_phone인 경우)"
                }
            },
            "required": ["action"]
        }
    
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
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_notes",
            description="Apple Notes 앱과 상호작용하여 노트를 생성, 검색, 조회합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "search", "list"],
                    "description": "수행할 작업: create (생성), search (검색), list (목록 조회)"
                },
                "title": {
                    "type": "string",
                    "description": "노트 제목 (action이 create인 경우 필수)"
                },
                "body": {
                    "type": "string",
                    "description": "노트 내용 (action이 create인 경우 필수)"
                },
                "folder_name": {
                    "type": "string",
                    "description": "폴더 이름 (기본값: Claude)",
                    "default": "Claude"
                },
                "search_text": {
                    "type": "string",
                    "description": "검색할 텍스트 (action이 search인 경우 필수)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "create":
                title = arguments.get("title")
                body = arguments.get("body")
                folder_name = arguments.get("folder_name", "Claude")
                
                if not title or not body:
                    return {"success": False, "error": "제목과 내용이 필요합니다."}
                
                result = await self.apple_manager.notes.create_note(title, body, folder_name)
                return {
                    "success": True,
                    "data": result,
                    "message": f"노트 '{title}'를 생성했습니다."
                }
            
            elif action == "search":
                search_text = arguments.get("search_text")
                if not search_text:
                    return {"success": False, "error": "검색 텍스트가 필요합니다."}
                
                notes = await self.apple_manager.notes.search_notes(search_text)
                return {
                    "success": True,
                    "data": notes,
                    "message": f"'{search_text}' 검색 결과: {len(notes)}개 노트"
                }
            
            elif action == "list":
                folder_name = arguments.get("folder_name")
                notes = await self.apple_manager.notes.list_notes(folder_name)
                return {
                    "success": True,
                    "data": notes,
                    "message": f"노트 목록: {len(notes)}개"
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Notes 오류: {str(e)}"}


class AppleMessagesTool(BaseTool):
    """Apple Messages MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_messages",
            description="Apple Messages 앱과 상호작용하여 메시지를 전송, 읽기, 예약합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send", "read", "unread", "schedule"],
                    "description": "수행할 작업: send (전송), read (읽기), unread (읽지 않은 메시지), schedule (예약 전송)"
                },
                "phone_number": {
                    "type": "string",
                    "description": "전화번호 (send, read, schedule 작업에 필수)"
                },
                "message": {
                    "type": "string",
                    "description": "전송할 메시지 (send, schedule 작업에 필수)"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 메시지 수 (기본값: 10)",
                    "default": 10
                },
                "scheduled_time": {
                    "type": "string",
                    "description": "예약 시간 ISO 형식 (schedule 작업에 필수)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "send":
                phone_number = arguments.get("phone_number")
                message = arguments.get("message")
                
                if not phone_number or not message:
                    return {"success": False, "error": "전화번호와 메시지가 필요합니다."}
                
                result = await self.apple_manager.messages.send_message(phone_number, message)
                return {
                    "success": True,
                    "data": result,
                    "message": f"{phone_number}로 메시지를 전송했습니다."
                }
            
            elif action == "read":
                phone_number = arguments.get("phone_number")
                limit = arguments.get("limit", 10)
                
                if not phone_number:
                    return {"success": False, "error": "전화번호가 필요합니다."}
                
                messages = await self.apple_manager.messages.read_messages(phone_number, limit)
                return {
                    "success": True,
                    "data": messages,
                    "message": f"{phone_number}와의 메시지 {len(messages)}개를 조회했습니다."
                }
            
            elif action == "unread":
                limit = arguments.get("limit", 10)
                messages = await self.apple_manager.messages.get_unread_messages(limit)
                return {
                    "success": True,
                    "data": messages,
                    "message": f"읽지 않은 메시지 {len(messages)}개를 조회했습니다."
                }
            
            elif action == "schedule":
                phone_number = arguments.get("phone_number")
                message = arguments.get("message")
                scheduled_time = arguments.get("scheduled_time")
                
                if not phone_number or not message or not scheduled_time:
                    return {"success": False, "error": "전화번호, 메시지, 예약 시간이 필요합니다."}
                
                result = await self.apple_manager.messages.schedule_message(phone_number, message, scheduled_time)
                return {
                    "success": True,
                    "data": result,
                    "message": f"{phone_number}로 {scheduled_time}에 메시지를 예약했습니다."
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Messages 오류: {str(e)}"}


class AppleMailTool(BaseTool):
    """Apple Mail MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_mail",
            description="Apple Mail 앱과 상호작용하여 이메일을 전송, 검색, 조회합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["send", "unread", "search", "accounts", "mailboxes"],
                    "description": "수행할 작업: send (전송), unread (읽지 않은 메일), search (검색), accounts (계정 목록), mailboxes (메일박스 목록)"
                },
                "to": {
                    "type": "string",
                    "description": "수신자 이메일 (send 작업에 필수)"
                },
                "subject": {
                    "type": "string",
                    "description": "이메일 제목 (send 작업에 필수)"
                },
                "body": {
                    "type": "string",
                    "description": "이메일 내용 (send 작업에 필수)"
                },
                "cc": {
                    "type": "string",
                    "description": "참조 이메일 (send 작업 선택사항)"
                },
                "bcc": {
                    "type": "string",
                    "description": "숨은 참조 이메일 (send 작업 선택사항)"
                },
                "search_term": {
                    "type": "string",
                    "description": "검색어 (search 작업에 필수)"
                },
                "account": {
                    "type": "string",
                    "description": "이메일 계정 (선택사항)"
                },
                "mailbox": {
                    "type": "string",
                    "description": "메일박스 (선택사항)"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 이메일 수 (기본값: 10)",
                    "default": 10
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "send":
                to = arguments.get("to")
                subject = arguments.get("subject")
                body = arguments.get("body")
                cc = arguments.get("cc")
                bcc = arguments.get("bcc")
                
                if not to or not subject or not body:
                    return {"success": False, "error": "수신자, 제목, 내용이 필요합니다."}
                
                result = await self.apple_manager.mail.send_email(to, subject, body, cc, bcc)
                return {
                    "success": True,
                    "data": result,
                    "message": f"{to}로 이메일을 전송했습니다."
                }
            
            elif action == "unread":
                account = arguments.get("account")
                mailbox = arguments.get("mailbox")
                limit = arguments.get("limit", 10)
                
                emails = await self.apple_manager.mail.get_unread_emails(account, mailbox, limit)
                return {
                    "success": True,
                    "data": emails,
                    "message": f"읽지 않은 이메일 {len(emails)}개를 조회했습니다."
                }
            
            elif action == "search":
                search_term = arguments.get("search_term")
                account = arguments.get("account")
                limit = arguments.get("limit", 10)
                
                if not search_term:
                    return {"success": False, "error": "검색어가 필요합니다."}
                
                emails = await self.apple_manager.mail.search_emails(search_term, account, limit)
                return {
                    "success": True,
                    "data": emails,
                    "message": f"'{search_term}' 검색 결과: {len(emails)}개 이메일"
                }
            
            elif action == "accounts":
                accounts = await self.apple_manager.mail.get_accounts()
                return {
                    "success": True,
                    "data": accounts,
                    "message": f"이메일 계정 {len(accounts)}개를 조회했습니다."
                }
            
            elif action == "mailboxes":
                account = arguments.get("account")
                mailboxes = await self.apple_manager.mail.get_mailboxes(account)
                return {
                    "success": True,
                    "data": mailboxes,
                    "message": f"메일박스 {len(mailboxes)}개를 조회했습니다."
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Mail 오류: {str(e)}"}


class AppleRemindersTool(BaseTool):
    """Apple Reminders MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_reminders",
            description="Apple Reminders 앱과 상호작용하여 미리 알림을 생성, 검색, 조회합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "search", "list", "open"],
                    "description": "수행할 작업: create (생성), search (검색), list (목록), open (열기)"
                },
                "name": {
                    "type": "string",
                    "description": "미리 알림 이름 (create 작업에 필수)"
                },
                "list_name": {
                    "type": "string",
                    "description": "목록 이름 (create 작업 선택사항)"
                },
                "notes": {
                    "type": "string",
                    "description": "메모 (create 작업 선택사항)"
                },
                "due_date": {
                    "type": "string",
                    "description": "마감일 ISO 형식 (create 작업 선택사항)"
                },
                "search_text": {
                    "type": "string",
                    "description": "검색 텍스트 (search, open 작업에 필수)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "create":
                name = arguments.get("name")
                list_name = arguments.get("list_name")
                notes = arguments.get("notes")
                due_date = arguments.get("due_date")
                
                if not name:
                    return {"success": False, "error": "미리 알림 이름이 필요합니다."}
                
                result = await self.apple_manager.reminders.create_reminder(name, list_name, notes, due_date)
                return {
                    "success": True,
                    "data": result,
                    "message": f"미리 알림 '{name}'을 생성했습니다."
                }
            
            elif action == "search":
                search_text = arguments.get("search_text")
                if not search_text:
                    return {"success": False, "error": "검색 텍스트가 필요합니다."}
                
                reminders = await self.apple_manager.reminders.search_reminders(search_text)
                return {
                    "success": True,
                    "data": reminders,
                    "message": f"'{search_text}' 검색 결과: {len(reminders)}개 미리 알림"
                }
            
            elif action == "list":
                reminders = await self.apple_manager.reminders.list_reminders()
                return {
                    "success": True,
                    "data": reminders,
                    "message": f"미리 알림 목록: {len(reminders)}개"
                }
            
            elif action == "open":
                search_text = arguments.get("search_text")
                if not search_text:
                    return {"success": False, "error": "검색 텍스트가 필요합니다."}
                
                result = await self.apple_manager.reminders.open_reminder(search_text)
                return {
                    "success": True,
                    "data": result,
                    "message": f"미리 알림을 열었습니다."
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Reminders 오류: {str(e)}"}


class AppleCalendarTool(BaseTool):
    """Apple Calendar MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_calendar",
            description="Apple Calendar 앱과 상호작용하여 이벤트를 생성, 검색, 조회합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "search", "list", "open"],
                    "description": "수행할 작업: create (생성), search (검색), list (목록), open (열기)"
                },
                "title": {
                    "type": "string",
                    "description": "이벤트 제목 (create 작업에 필수)"
                },
                "start_date": {
                    "type": "string",
                    "description": "시작 시간 ISO 형식 (create 작업에 필수)"
                },
                "end_date": {
                    "type": "string",
                    "description": "종료 시간 ISO 형식 (create 작업에 필수)"
                },
                "location": {
                    "type": "string",
                    "description": "장소 (create 작업 선택사항)"
                },
                "notes": {
                    "type": "string",
                    "description": "메모 (create 작업 선택사항)"
                },
                "is_all_day": {
                    "type": "boolean",
                    "description": "종일 이벤트 여부 (기본값: false)",
                    "default": False
                },
                "calendar_name": {
                    "type": "string",
                    "description": "캘린더 이름 (create 작업 선택사항)"
                },
                "search_text": {
                    "type": "string",
                    "description": "검색 텍스트 (search 작업에 필수)"
                },
                "event_id": {
                    "type": "string",
                    "description": "이벤트 ID (open 작업에 필수)"
                },
                "from_date": {
                    "type": "string",
                    "description": "검색 시작 날짜 ISO 형식 (선택사항)"
                },
                "to_date": {
                    "type": "string",
                    "description": "검색 종료 날짜 ISO 형식 (선택사항)"
                },
                "limit": {
                    "type": "integer",
                    "description": "조회할 이벤트 수 (기본값: 10)",
                    "default": 10
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "create":
                title = arguments.get("title")
                start_date = arguments.get("start_date")
                end_date = arguments.get("end_date")
                location = arguments.get("location")
                notes = arguments.get("notes")
                is_all_day = arguments.get("is_all_day", False)
                calendar_name = arguments.get("calendar_name")
                
                if not title or not start_date or not end_date:
                    return {"success": False, "error": "제목, 시작 시간, 종료 시간이 필요합니다."}
                
                result = await self.apple_manager.calendar.create_event(
                    title, start_date, end_date, location, notes, is_all_day, calendar_name
                )
                return {
                    "success": True,
                    "data": result,
                    "message": f"이벤트 '{title}'를 생성했습니다."
                }
            
            elif action == "search":
                search_text = arguments.get("search_text")
                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")
                limit = arguments.get("limit", 10)
                
                if not search_text:
                    return {"success": False, "error": "검색 텍스트가 필요합니다."}
                
                events = await self.apple_manager.calendar.search_events(search_text, from_date, to_date, limit)
                return {
                    "success": True,
                    "data": events,
                    "message": f"'{search_text}' 검색 결과: {len(events)}개 이벤트"
                }
            
            elif action == "list":
                from_date = arguments.get("from_date")
                to_date = arguments.get("to_date")
                limit = arguments.get("limit", 10)
                
                events = await self.apple_manager.calendar.list_events(from_date, to_date, limit)
                return {
                    "success": True,
                    "data": events,
                    "message": f"이벤트 목록: {len(events)}개"
                }
            
            elif action == "open":
                event_id = arguments.get("event_id")
                if not event_id:
                    return {"success": False, "error": "이벤트 ID가 필요합니다."}
                
                result = await self.apple_manager.calendar.open_event(event_id)
                return {
                    "success": True,
                    "data": result,
                    "message": f"이벤트를 열었습니다."
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Calendar 오류: {str(e)}"}


class AppleMapsTool(BaseTool):
    """Apple Maps MCP 도구"""
    
    def __init__(self, apple_manager: AppleAppsManager):
        self.apple_manager = apple_manager
        super().__init__(
            name="apple_maps",
            description="Apple Maps 앱과 상호작용하여 위치 검색, 길찾기, 가이드 관리를 합니다."
        )
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "save", "directions", "pin", "create_guide", "add_to_guide"],
                    "description": "수행할 작업: search (검색), save (저장), directions (길찾기), pin (핀), create_guide (가이드 생성), add_to_guide (가이드 추가)"
                },
                "query": {
                    "type": "string",
                    "description": "검색어 (search 작업에 필수)"
                },
                "limit": {
                    "type": "integer",
                    "description": "검색 결과 수 (기본값: 10)",
                    "default": 10
                },
                "name": {
                    "type": "string",
                    "description": "위치 이름 (save, pin 작업에 필수)"
                },
                "address": {
                    "type": "string",
                    "description": "주소 (save, pin, add_to_guide 작업에 필수)"
                },
                "from_address": {
                    "type": "string",
                    "description": "출발지 주소 (directions 작업에 필수)"
                },
                "to_address": {
                    "type": "string",
                    "description": "목적지 주소 (directions 작업에 필수)"
                },
                "transport_type": {
                    "type": "string",
                    "enum": ["driving", "walking", "transit"],
                    "description": "교통 수단 (기본값: driving)",
                    "default": "driving"
                },
                "guide_name": {
                    "type": "string",
                    "description": "가이드 이름 (create_guide, add_to_guide 작업에 필수)"
                }
            },
            "required": ["action"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        action = arguments.get("action")
        
        try:
            if action == "search":
                query = arguments.get("query")
                limit = arguments.get("limit", 10)
                
                if not query:
                    return {"success": False, "error": "검색어가 필요합니다."}
                
                locations = await self.apple_manager.maps.search_locations(query, limit)
                return {
                    "success": True,
                    "data": locations,
                    "message": f"'{query}' 검색 결과: {len(locations)}개 위치"
                }
            
            elif action == "save":
                name = arguments.get("name")
                address = arguments.get("address")
                
                if not name or not address:
                    return {"success": False, "error": "위치 이름과 주소가 필요합니다."}
                
                result = await self.apple_manager.maps.save_location(name, address)
                return {
                    "success": True,
                    "data": result,
                    "message": f"위치 '{name}'을 저장했습니다."
                }
            
            elif action == "directions":
                from_address = arguments.get("from_address")
                to_address = arguments.get("to_address")
                transport_type = arguments.get("transport_type", "driving")
                
                if not from_address or not to_address:
                    return {"success": False, "error": "출발지와 목적지 주소가 필요합니다."}
                
                result = await self.apple_manager.maps.get_directions(from_address, to_address, transport_type)
                return {
                    "success": True,
                    "data": result,
                    "message": f"{from_address}에서 {to_address}로의 길찾기 결과"
                }
            
            elif action == "pin":
                name = arguments.get("name")
                address = arguments.get("address")
                
                if not name or not address:
                    return {"success": False, "error": "핀 이름과 주소가 필요합니다."}
                
                result = await self.apple_manager.maps.drop_pin(name, address)
                return {
                    "success": True,
                    "data": result,
                    "message": f"'{name}' 핀을 드롭했습니다."
                }
            
            elif action == "create_guide":
                guide_name = arguments.get("guide_name")
                
                if not guide_name:
                    return {"success": False, "error": "가이드 이름이 필요합니다."}
                
                result = await self.apple_manager.maps.create_guide(guide_name)
                return {
                    "success": True,
                    "data": result,
                    "message": f"가이드 '{guide_name}'을 생성했습니다."
                }
            
            elif action == "add_to_guide":
                guide_name = arguments.get("guide_name")
                address = arguments.get("address")
                
                if not guide_name or not address:
                    return {"success": False, "error": "가이드 이름과 주소가 필요합니다."}
                
                result = await self.apple_manager.maps.add_to_guide(guide_name, address)
                return {
                    "success": True,
                    "data": result,
                    "message": f"가이드 '{guide_name}'에 위치를 추가했습니다."
                }
            
            else:
                return {"success": False, "error": f"지원하지 않는 작업: {action}"}
        
        except Exception as e:
            return {"success": False, "error": f"Apple Maps 오류: {str(e)}"}


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
