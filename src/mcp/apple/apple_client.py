#!/usr/bin/env python3
"""
Apple MCP Client
Python client for communicating with Apple MCP server via JSON-RPC
"""

import json
import asyncio
import aiohttp
import subprocess
import logging
import os
import signal
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AppleMCPManager:
    """Apple MCP 서버 생명주기 관리자"""

    def __init__(self, server_path: str = "external/apple-mcp", apple_mcp_port: int = 3000):
        self.server_path = Path(server_path)
        self.apple_mcp_port = apple_mcp_port
        # data 디렉토리는 프로젝트 루트의 data 폴더 사용
        self.pid_file = Path("data") / "apple-mcp.pid"
        self._started_by_us = False

    def is_running(self) -> bool:
        if not self.pid_file.exists():
            return False
        try:
            pid = int(self.pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except Exception:
            # 잘못된 PID 또는 이미 종료됨
            try:
                self.pid_file.unlink(missing_ok=True)
            except Exception:
                pass
            return False

    def start_background(self) -> bool:
        """Apple MCP 서버를 백그라운드에서 시작 (이미 실행 중이면 통과)"""
        if self.is_running():
            logger.info("Apple MCP 서버가 이미 실행 중입니다")
            return True

        if not self.server_path.exists():
            logger.warning(f"Apple MCP 서버 경로를 찾을 수 없습니다: {self.server_path}")
            return False

        # bun 존재 여부는 Popen 실패로 감지
        env = {**os.environ, "PORT": str(self.apple_mcp_port)}
        try:
            process = subprocess.Popen(
                ["bun", "run", "index.ts"],
                cwd=str(self.server_path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            self.pid_file.parent.mkdir(parents=True, exist_ok=True)
            self.pid_file.write_text(str(process.pid))
            self._started_by_us = True
            logger.info(f"Apple MCP 서버 시작: PID={process.pid}, PORT={self.apple_mcp_port}")
            return True
        except FileNotFoundError:
            logger.error("Bun이 설치되어 있지 않습니다. https://bun.sh 에서 설치 후 재시도하세요.")
            return False
        except Exception as e:
            logger.error(f"Apple MCP 서버 시작 실패: {e}")
            return False

    def stop_background(self) -> bool:
        """백그라운드 Apple MCP 서버 중지 (우리가 시작한 경우에만)"""
        if not self.pid_file.exists():
            return True
        try:
            pid = int(self.pid_file.read_text().strip())
        except Exception:
            try:
                self.pid_file.unlink(missing_ok=True)
            except Exception:
                pass
            return True

        if not self._started_by_us:
            # 외부에서 시작된 프로세스는 건드리지 않음
            return True

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning(f"프로세스 종료 시도 실패: {e}")

        try:
            self.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        logger.info("Apple MCP 서버 중지 처리 완료")
        return True


class AppleApp(Enum):
    """Apple 앱 종류"""
    CONTACTS = "contacts"
    NOTES = "notes"
    MESSAGES = "messages"
    MAIL = "mail"
    REMINDERS = "reminders"
    CALENDAR = "calendar"
    MAPS = "maps"


@dataclass
class MCPRequest:
    """MCP JSON-RPC 요청"""
    method: str
    params: Dict[str, Any]
    id: Optional[int] = None
    jsonrpc: str = "2.0"


@dataclass
class MCPResponse:
    """MCP JSON-RPC 응답"""
    id: Optional[int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"


class AppleMCPClient:
    """Apple MCP 서버와 통신하는 Python 클라이언트"""
    
    def __init__(self, server_path: str = "external/apple-mcp"):
        self.server_path = server_path
        self.server_process = None
        self.request_id = 0
        
    def _get_next_id(self) -> int:
        """다음 요청 ID 생성"""
        self.request_id += 1
        return self.request_id
    
    async def _send_request(self, method: str, params: Dict[str, Any]) -> MCPResponse:
        """JSON-RPC 요청을 Apple MCP 서버로 전송"""
        request = MCPRequest(
            method=method,
            params=params,
            id=self._get_next_id()
        )
        
        try:
            # subprocess를 통해 Apple MCP 서버와 통신
            cmd = ["bun", "run", "index.ts"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # JSON-RPC 요청 전송
            request_json = json.dumps({
                "jsonrpc": request.jsonrpc,
                "method": request.method,
                "params": request.params,
                "id": request.id
            }) + "\n"
            
            stdout, stderr = await process.communicate(request_json.encode())
            
            if stderr:
                logger.warning(f"Apple MCP stderr: {stderr.decode()}")
            
            # 응답 파싱 - 여러 줄로 나뉠 수 있으므로 마지막 유효한 JSON 라인 찾기
            if stdout:
                stdout_str = stdout.decode().strip()
                lines = stdout_str.split('\n')
                
                # 마지막부터 역순으로 JSON 응답 찾기
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith('{') and '"jsonrpc"' in line:
                        try:
                            response_data = json.loads(line)
                            return MCPResponse(
                                id=response_data.get("id"),
                                result=response_data.get("result"),
                                error=response_data.get("error")
                            )
                        except json.JSONDecodeError:
                            continue
                
                # JSON 응답을 찾지 못한 경우
                logger.error(f"유효한 JSON 응답을 찾을 수 없음: {stdout_str}")
                raise Exception("Invalid JSON response from Apple MCP server")
            else:
                raise Exception("No response from Apple MCP server")
                
        except Exception as e:
            logger.error(f"Apple MCP 통신 오류: {e}")
            return MCPResponse(
                id=request.id,
                error={"code": -1, "message": str(e)}
            )
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Apple MCP 도구 호출"""
        response = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if response.error:
            raise Exception(f"Apple MCP 오류: {response.error}")
        
        return response.result or {}
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록 조회"""
        response = await self._send_request("tools/list", {})
        
        if response.error:
            raise Exception(f"도구 목록 조회 오류: {response.error}")
        
        return response.result.get("tools", []) if response.result else []


class AppleContactsClient:
    """Apple Contacts 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def search_contacts(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """연락처 검색
        
        Args:
            name: 검색할 이름 (없으면 모든 연락처 반환)
        
        Returns:
            연락처 목록
        """
        arguments = {}
        if name:
            arguments["name"] = name
        
        result = await self.mcp.call_tool("contacts", arguments)
        return result.get("content", [])
    
    async def find_contact_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """전화번호로 연락처 찾기"""
        # 모든 연락처를 가져와서 전화번호로 필터링
        all_contacts = await self.search_contacts()
        for contact in all_contacts:
            if "phones" in contact:
                for contact_phone in contact["phones"]:
                    if phone in contact_phone or contact_phone in phone:
                        return contact
        return None


class AppleNotesClient:
    """Apple Notes 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def create_note(self, title: str, body: str, folder_name: str = "Claude") -> Dict[str, Any]:
        """노트 생성"""
        result = await self.mcp.call_tool("notes", {
            "operation": "create",
            "title": title,
            "body": body,
            "folderName": folder_name
        })
        return result
    
    async def search_notes(self, search_text: str) -> List[Dict[str, Any]]:
        """노트 검색"""
        result = await self.mcp.call_tool("notes", {
            "operation": "search",
            "searchText": search_text
        })
        return result.get("content", [])
    
    async def list_notes(self, folder_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """노트 목록 조회"""
        arguments = {"operation": "list"}
        if folder_name:
            arguments["folderName"] = folder_name
        
        result = await self.mcp.call_tool("notes", arguments)
        return result.get("content", [])


class AppleMessagesClient:
    """Apple Messages 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def send_message(self, phone_number: str, message: str) -> Dict[str, Any]:
        """메시지 전송"""
        result = await self.mcp.call_tool("messages", {
            "operation": "send",
            "phoneNumber": phone_number,
            "message": message
        })
        return result
    
    async def read_messages(self, phone_number: str, limit: int = 10) -> List[Dict[str, Any]]:
        """메시지 읽기"""
        result = await self.mcp.call_tool("messages", {
            "operation": "read",
            "phoneNumber": phone_number,
            "limit": limit
        })
        return result.get("content", [])
    
    async def get_unread_messages(self, limit: int = 10) -> List[Dict[str, Any]]:
        """읽지 않은 메시지 조회"""
        result = await self.mcp.call_tool("messages", {
            "operation": "unread",
            "limit": limit
        })
        return result.get("content", [])
    
    async def schedule_message(self, phone_number: str, message: str, scheduled_time: str) -> Dict[str, Any]:
        """메시지 예약 전송"""
        result = await self.mcp.call_tool("messages", {
            "operation": "schedule",
            "phoneNumber": phone_number,
            "message": message,
            "scheduledTime": scheduled_time
        })
        return result


class AppleMailClient:
    """Apple Mail 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def send_email(self, to: str, subject: str, body: str, 
                        cc: Optional[str] = None, bcc: Optional[str] = None) -> Dict[str, Any]:
        """이메일 전송"""
        arguments = {
            "operation": "send",
            "to": to,
            "subject": subject,
            "body": body
        }
        if cc:
            arguments["cc"] = cc
        if bcc:
            arguments["bcc"] = bcc
        
        result = await self.mcp.call_tool("mail", arguments)
        return result
    
    async def get_unread_emails(self, account: Optional[str] = None, 
                               mailbox: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """읽지 않은 이메일 조회"""
        arguments = {"operation": "unread", "limit": limit}
        if account:
            arguments["account"] = account
        if mailbox:
            arguments["mailbox"] = mailbox
        
        result = await self.mcp.call_tool("mail", arguments)
        return result.get("content", [])
    
    async def search_emails(self, search_term: str, account: Optional[str] = None, 
                           limit: int = 10) -> List[Dict[str, Any]]:
        """이메일 검색"""
        arguments = {
            "operation": "search",
            "searchTerm": search_term,
            "limit": limit
        }
        if account:
            arguments["account"] = account
        
        result = await self.mcp.call_tool("mail", arguments)
        return result.get("content", [])
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """이메일 계정 목록 조회"""
        result = await self.mcp.call_tool("mail", {"operation": "accounts"})
        return result.get("content", [])
    
    async def get_mailboxes(self, account: Optional[str] = None) -> List[Dict[str, Any]]:
        """메일박스 목록 조회"""
        arguments = {"operation": "mailboxes"}
        if account:
            arguments["account"] = account
        
        result = await self.mcp.call_tool("mail", arguments)
        return result.get("content", [])


class AppleRemindersClient:
    """Apple Reminders 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def create_reminder(self, name: str, list_name: Optional[str] = None, 
                             notes: Optional[str] = None, due_date: Optional[str] = None) -> Dict[str, Any]:
        """미리 알림 생성"""
        arguments = {"operation": "create", "name": name}
        if list_name:
            arguments["listName"] = list_name
        if notes:
            arguments["notes"] = notes
        if due_date:
            arguments["dueDate"] = due_date
        
        result = await self.mcp.call_tool("reminders", arguments)
        return result
    
    async def search_reminders(self, search_text: str) -> List[Dict[str, Any]]:
        """미리 알림 검색"""
        result = await self.mcp.call_tool("reminders", {
            "operation": "search",
            "searchText": search_text
        })
        return result.get("content", [])
    
    async def list_reminders(self) -> List[Dict[str, Any]]:
        """모든 미리 알림 목록 조회"""
        result = await self.mcp.call_tool("reminders", {"operation": "list"})
        return result.get("content", [])
    
    async def open_reminder(self, search_text: str) -> Dict[str, Any]:
        """미리 알림 열기"""
        result = await self.mcp.call_tool("reminders", {
            "operation": "open",
            "searchText": search_text
        })
        return result


class AppleCalendarClient:
    """Apple Calendar 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def create_event(self, title: str, start_date: str, end_date: str,
                          location: Optional[str] = None, notes: Optional[str] = None,
                          is_all_day: bool = False, calendar_name: Optional[str] = None) -> Dict[str, Any]:
        """캘린더 이벤트 생성"""
        arguments = {
            "operation": "create",
            "title": title,
            "startDate": start_date,
            "endDate": end_date,
            "isAllDay": is_all_day
        }
        if location:
            arguments["location"] = location
        if notes:
            arguments["notes"] = notes
        if calendar_name:
            arguments["calendarName"] = calendar_name
        
        result = await self.mcp.call_tool("calendar", arguments)
        return result
    
    async def search_events(self, search_text: str, from_date: Optional[str] = None,
                           to_date: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """이벤트 검색"""
        arguments = {
            "operation": "search",
            "searchText": search_text,
            "limit": limit
        }
        if from_date:
            arguments["fromDate"] = from_date
        if to_date:
            arguments["toDate"] = to_date
        
        result = await self.mcp.call_tool("calendar", arguments)
        return result.get("content", [])
    
    async def list_events(self, from_date: Optional[str] = None,
                         to_date: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """이벤트 목록 조회"""
        arguments = {"operation": "list", "limit": limit}
        if from_date:
            arguments["fromDate"] = from_date
        if to_date:
            arguments["toDate"] = to_date
        
        result = await self.mcp.call_tool("calendar", arguments)
        return result.get("content", [])
    
    async def open_event(self, event_id: str) -> Dict[str, Any]:
        """이벤트 열기"""
        result = await self.mcp.call_tool("calendar", {
            "operation": "open",
            "eventId": event_id
        })
        return result


class AppleMapsClient:
    """Apple Maps 앱 클라이언트"""
    
    def __init__(self, mcp_client: AppleMCPClient):
        self.mcp = mcp_client
    
    async def search_locations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """위치 검색"""
        result = await self.mcp.call_tool("maps", {
            "operation": "search",
            "query": query,
            "limit": limit
        })
        return result.get("content", [])
    
    async def save_location(self, name: str, address: str) -> Dict[str, Any]:
        """위치 즐겨찾기 저장"""
        result = await self.mcp.call_tool("maps", {
            "operation": "save",
            "name": name,
            "address": address
        })
        return result
    
    async def get_directions(self, from_address: str, to_address: str,
                           transport_type: str = "driving") -> Dict[str, Any]:
        """길찾기"""
        result = await self.mcp.call_tool("maps", {
            "operation": "directions",
            "fromAddress": from_address,
            "toAddress": to_address,
            "transportType": transport_type
        })
        return result
    
    async def drop_pin(self, name: str, address: str) -> Dict[str, Any]:
        """핀 드롭"""
        result = await self.mcp.call_tool("maps", {
            "operation": "pin",
            "name": name,
            "address": address
        })
        return result
    
    async def create_guide(self, guide_name: str) -> Dict[str, Any]:
        """가이드 생성"""
        result = await self.mcp.call_tool("maps", {
            "operation": "createGuide",
            "guideName": guide_name
        })
        return result
    
    async def add_to_guide(self, guide_name: str, address: str) -> Dict[str, Any]:
        """가이드에 위치 추가"""
        result = await self.mcp.call_tool("maps", {
            "operation": "addToGuide",
            "guideName": guide_name,
            "address": address
        })
        return result


class AppleAppsManager:
    """Apple 앱들을 통합 관리하는 클래스"""
    
    def __init__(self, server_path: str = "external/apple-mcp"):
        self.mcp_client = AppleMCPClient(server_path)
        
        # 각 앱별 클라이언트 초기화
        self.contacts = AppleContactsClient(self.mcp_client)
        self.notes = AppleNotesClient(self.mcp_client)
        self.messages = AppleMessagesClient(self.mcp_client)
        self.mail = AppleMailClient(self.mcp_client)
        self.reminders = AppleRemindersClient(self.mcp_client)
        self.calendar = AppleCalendarClient(self.mcp_client)
        self.maps = AppleMapsClient(self.mcp_client)
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록 조회"""
        return await self.mcp_client.list_tools()
    
    async def health_check(self) -> bool:
        """Apple MCP 서버 상태 확인"""
        try:
            tools = await self.get_available_tools()
            return len(tools) > 0
        except Exception:
            return False


# 편의를 위한 팩토리 함수
def create_apple_apps_manager(server_path: str = "external/apple-mcp") -> AppleAppsManager:
    """Apple Apps Manager 인스턴스 생성"""
    return AppleAppsManager(server_path)


# 사용 예시
async def example_usage():
    """사용 예시"""
    manager = create_apple_apps_manager()
    
    # 상태 확인
    if not await manager.health_check():
        print("Apple MCP 서버에 연결할 수 없습니다.")
        return
    
    # 연락처 검색
    contacts = await manager.contacts.search_contacts("John")
    print(f"검색된 연락처: {len(contacts)}개")
    
    # 노트 생성
    note_result = await manager.notes.create_note(
        title="테스트 노트",
        body="Python에서 생성한 노트입니다.",
        folder_name="Claude"
    )
    print(f"노트 생성 결과: {note_result}")
    
    # 캘린더 이벤트 생성
    event_result = await manager.calendar.create_event(
        title="Python 테스트 이벤트",
        start_date="2024-01-01T10:00:00",
        end_date="2024-01-01T11:00:00",
        location="테스트 장소"
    )
    print(f"이벤트 생성 결과: {event_result}")


def autostart_if_configured(settings) -> Optional[AppleMCPManager]:
    """설정에 따라 자동 시작 수행 후 매니저 반환 (미시작 시 None)"""
    # 설정에서 apple_mcp_autostart 확인 (기본값 False)
    autostart = getattr(settings, "apple_mcp_autostart", False)
    if not autostart:
        return None
    
    # Apple MCP 서버 경로와 포트 설정
    server_path = getattr(settings, "apple_mcp_server_path", "external/apple-mcp")
    port = getattr(settings, "apple_mcp_port", 3000)
    
    manager = AppleMCPManager(server_path, port)
    manager.start_background()
    return manager


if __name__ == "__main__":
    # 테스트 실행
    asyncio.run(example_usage())
