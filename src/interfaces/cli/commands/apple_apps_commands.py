#!/usr/bin/env python3
"""
Apple 앱 관련 CLI 명령어 확장
자연어로 Apple 앱들을 제어할 수 있는 명령어들
"""

import click
import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ...mcp.apple_tools import create_apple_tools_with_manager


@click.group()
def apple_apps():
    """Apple 앱들과 상호작용하는 명령어들"""
    pass


@apple_apps.command()
@click.option('--name', '-n', help='검색할 연락처 이름')
@click.option('--phone', '-p', help='검색할 전화번호')
@click.option('--action', '-a', type=click.Choice(['search', 'find_by_phone']), default='search', help='수행할 작업')
async def contacts(name: Optional[str], phone: Optional[str], action: str):
    """연락처 검색 및 조회"""
    try:
        apple_manager, tools = create_apple_tools_with_manager()
        contacts_tool = tools[0]  # AppleContactsTool
        
        parameters = {"action": action}
        if action == "search" and name:
            parameters["name"] = name
        elif action == "find_by_phone" and phone:
            parameters["phone"] = phone
        elif action == "find_by_phone" and not phone:
            click.echo("❌ 전화번호를 입력해주세요.")
            return
        
        result = await contacts_tool.execute(parameters)
        
        if result.is_success and result.data:
            click.echo("✅ 연락처 조회 성공")
            if action == "search":
                contacts_data = result.data.get("contacts", [])
                click.echo(f"📱 연락처 {len(contacts_data)}개 발견:")
                for contact in contacts_data[:10]:  # 최대 10개만 표시
                    name = contact.get("name", "이름 없음")
                    phones = contact.get("phones", [])
                    click.echo(f"  • {name}: {', '.join(phones) if phones else '전화번호 없음'}")
            elif action == "find_by_phone":
                contact = result.data.get("contact")
                if contact:
                    click.echo(f"  • 이름: {contact.get('name', '이름 없음')}")
                    click.echo(f"  • 전화번호: {', '.join(contact.get('phones', []))}")
                else:
                    click.echo("  해당 전화번호의 연락처를 찾을 수 없습니다.")
        else:
            click.echo(f"❌ 오류: {result.error_message}")
    
    except Exception as e:
        click.echo(f"❌ 예상치 못한 오류: {str(e)}")


@apple_apps.command()
@click.option('--action', '-a', type=click.Choice(['create', 'search', 'list']), required=True, help='수행할 작업')
@click.option('--title', '-t', help='노트 제목 (create 시 필수)')
@click.option('--body', '-b', help='노트 내용 (create 시 필수)')
@click.option('--folder', '-f', default='Claude', help='폴더 이름 (기본값: Claude)')
@click.option('--search', '-s', help='검색할 텍스트 (search 시 필수)')
async def notes(action: str, title: Optional[str], body: Optional[str], folder: str, search: Optional[str]):
    """노트 생성, 검색, 조회"""
    try:
        apple_manager, tools = create_apple_tools_with_manager()
        notes_tool = tools[1]  # AppleNotesTool
        
        parameters = {"action": action}
        
        if action == "create":
            if not title or not body:
                click.echo("❌ 노트 생성에는 제목(--title)과 내용(--body)이 필요합니다.")
                return
            parameters.update({"title": title, "body": body, "folder_name": folder})
        
        elif action == "search":
            if not search:
                click.echo("❌ 검색에는 검색어(--search)가 필요합니다.")
                return
            parameters["search_text"] = search
        
        elif action == "list":
            parameters["folder_name"] = folder
        
        result = await notes_tool.execute(parameters)
        
        if result.is_success:
            click.echo("✅ 노트 작업 성공")
            
            if action == "create":
                click.echo(f"📝 노트 '{title}'를 '{folder}' 폴더에 생성했습니다.")
            
            elif action in ["search", "list"]:
                if result.data:
                    notes_data = result.data.get("notes", [])
                    count = result.data.get("count", 0)
                else:
                    notes_data = []
                    count = 0
                click.echo(f"📝 노트 {count}개 발견:")
                
                for note in notes_data[:10]:  # 최대 10개만 표시
                    note_name = note.get("name", "제목 없음")
                    content = note.get("content", "")
                    # 내용이 길면 요약해서 표시
                    if len(content) > 100:
                        content = content[:100] + "..."
                    click.echo(f"  • {note_name}")
                    if content:
                        click.echo(f"    {content}")
        else:
            click.echo(f"❌ 오류: {result.error_message}")
    
    except Exception as e:
        click.echo(f"❌ 예상치 못한 오류: {str(e)}")


@apple_apps.command()
@click.option('--action', '-a', type=click.Choice(['send', 'read', 'unread']), required=True, help='수행할 작업')
@click.option('--phone', '-p', help='전화번호 (send, read 시 필수)')
@click.option('--message', '-m', help='전송할 메시지 (send 시 필수)')
@click.option('--limit', '-l', default=10, help='조회할 메시지 수 (기본값: 10)')
async def messages(action: str, phone: Optional[str], message: Optional[str], limit: int):
    """메시지 전송, 읽기, 조회"""
    try:
        apple_manager, tools = create_apple_tools_with_manager()
        messages_tool = tools[2]  # AppleMessagesTool
        
        parameters = {"action": action, "limit": limit}
        
        if action == "send":
            if not phone or not message:
                click.echo("❌ 메시지 전송에는 전화번호(--phone)와 메시지(--message)가 필요합니다.")
                return
            parameters.update({"phone_number": phone, "message": message})
        
        elif action == "read":
            if not phone:
                click.echo("❌ 메시지 읽기에는 전화번호(--phone)가 필요합니다.")
                return
            parameters["phone_number"] = phone
        
        result = await messages_tool.execute(parameters)
        
        if result.is_success:
            click.echo("✅ 메시지 작업 성공")
            
            if action == "send":
                click.echo(f"💬 {phone}로 메시지를 전송했습니다.")
                click.echo(f"   내용: {message}")
            
            elif action in ["read", "unread"]:
                if result.data:
                    messages_data = result.data.get("messages", [])
                    count = result.data.get("count", 0)
                else:
                    messages_data = []
                    count = 0
                click.echo(f"💬 메시지 {count}개:")
                
                for msg in messages_data:
                    sender = msg.get("sender", "알 수 없음")
                    content = msg.get("content", "내용 없음")
                    date = msg.get("date", "날짜 없음")
                    click.echo(f"  • {sender} ({date}): {content}")
        else:
            click.echo(f"❌ 오류: {result.error_message}")
    
    except Exception as e:
        click.echo(f"❌ 예상치 못한 오류: {str(e)}")


@apple_apps.command()
@click.option('--action', '-a', type=click.Choice(['create', 'search', 'list']), required=True, help='수행할 작업')
@click.option('--title', '-t', help='이벤트 제목 (create 시 필수)')
@click.option('--start', '-s', help='시작 시간 (YYYY-MM-DD HH:MM 형식, create 시 필수)')
@click.option('--end', '-e', help='종료 시간 (YYYY-MM-DD HH:MM 형식, create 시 필수)')
@click.option('--location', '-l', help='장소 (선택사항)')
@click.option('--notes', '-n', help='메모 (선택사항)')
@click.option('--search', help='검색할 텍스트 (search 시 필수)')
@click.option('--limit', default=10, help='조회할 이벤트 수 (기본값: 10)')
async def calendar(action: str, title: Optional[str], start: Optional[str], end: Optional[str], 
                  location: Optional[str], notes: Optional[str], search: Optional[str], limit: int):
    """캘린더 이벤트 생성, 검색, 조회"""
    try:
        apple_manager, tools = create_apple_tools_with_manager()
        calendar_tool = tools[5]  # AppleCalendarTool
        
        parameters = {"action": action, "limit": limit}
        
        if action == "create":
            if not title or not start or not end:
                click.echo("❌ 이벤트 생성에는 제목(--title), 시작시간(--start), 종료시간(--end)이 필요합니다.")
                click.echo("   시간 형식: YYYY-MM-DD HH:MM (예: 2024-01-15 14:30)")
                return
            
            # 시간 형식 변환 (ISO 형식으로)
            try:
                start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M")
                start_iso = start_dt.isoformat()
                end_iso = end_dt.isoformat()
            except ValueError:
                click.echo("❌ 시간 형식이 올바르지 않습니다. YYYY-MM-DD HH:MM 형식을 사용해주세요.")
                return
            
            parameters.update({
                "title": title,
                "start_date": start_iso,
                "end_date": end_iso
            })
            if location:
                parameters["location"] = location
            if notes:
                parameters["notes"] = notes
        
        elif action == "search":
            if not search:
                click.echo("❌ 검색에는 검색어(--search)가 필요합니다.")
                return
            parameters["search_text"] = search
        
        result = await calendar_tool.execute(parameters)
        
        if result.is_success:
            click.echo("✅ 캘린더 작업 성공")
            
            if action == "create":
                click.echo(f"📅 이벤트 '{title}'를 생성했습니다.")
                click.echo(f"   시간: {start} ~ {end}")
                if location:
                    click.echo(f"   장소: {location}")
            
            elif action in ["search", "list"]:
                if result.data:
                    events_data = result.data.get("events", [])
                    count = result.data.get("count", 0)
                else:
                    events_data = []
                    count = 0
                click.echo(f"📅 이벤트 {count}개:")
                
                for event in events_data:
                    event_title = event.get("title", "제목 없음")
                    event_date = event.get("startDate", "날짜 없음")
                    event_location = event.get("location", "")
                    click.echo(f"  • {event_title} ({event_date})")
                    if event_location:
                        click.echo(f"    📍 {event_location}")
        else:
            click.echo(f"❌ 오류: {result.error_message}")
    
    except Exception as e:
        click.echo(f"❌ 예상치 못한 오류: {str(e)}")


@apple_apps.command()
@click.option('--action', '-a', type=click.Choice(['search', 'directions']), required=True, help='수행할 작업')
@click.option('--query', '-q', help='검색어 (search 시 필수)')
@click.option('--from-addr', help='출발지 주소 (directions 시 필수)')
@click.option('--to-addr', help='목적지 주소 (directions 시 필수)')
@click.option('--transport', type=click.Choice(['driving', 'walking', 'transit']), default='driving', help='교통수단 (기본값: driving)')
@click.option('--limit', default=5, help='검색 결과 수 (기본값: 5)')
async def maps(action: str, query: Optional[str], from_addr: Optional[str], to_addr: Optional[str], 
              transport: str, limit: int):
    """지도 검색 및 길찾기"""
    try:
        apple_manager, tools = create_apple_tools_with_manager()
        maps_tool = tools[6]  # AppleMapsTool
        
        parameters = {"action": action, "limit": limit}
        
        if action == "search":
            if not query:
                click.echo("❌ 검색에는 검색어(--query)가 필요합니다.")
                return
            parameters["query"] = query
        
        elif action == "directions":
            if not from_addr or not to_addr:
                click.echo("❌ 길찾기에는 출발지(--from-addr)와 목적지(--to-addr)가 필요합니다.")
                return
            parameters.update({
                "from_address": from_addr,
                "to_address": to_addr,
                "transport_type": transport
            })
        
        result = await maps_tool.execute(parameters)
        
        if result.is_success:
            click.echo("✅ 지도 작업 성공")
            
            if action == "search":
                if result.data:
                    locations_data = result.data.get("locations", [])
                    count = result.data.get("count", 0)
                else:
                    locations_data = []
                    count = 0
                click.echo(f"🗺️ 위치 {count}개 발견:")
                
                for location in locations_data:
                    name = location.get("name", "이름 없음")
                    address = location.get("address", "주소 없음")
                    click.echo(f"  • {name}")
                    click.echo(f"    📍 {address}")
            
            elif action == "directions":
                click.echo(f"🛣️ {from_addr} → {to_addr}")
                click.echo(f"   교통수단: {transport}")
                if result.data:
                    directions_data = result.data.get("result", {})
                else:
                    directions_data = {}
                if directions_data:
                    click.echo("   길찾기 결과를 Apple Maps에서 확인하세요.")
        else:
            click.echo(f"❌ 오류: {result.error_message}")
    
    except Exception as e:
        click.echo(f"❌ 예상치 못한 오류: {str(e)}")


# 자연어 명령어 처리
@apple_apps.command()
@click.argument('command', nargs=-1, required=True)
async def ai(command):
    """자연어로 Apple 앱 제어
    
    예시:
    - pai apple ai "John에게 연락처 찾아줘"
    - pai apple ai "회의 노트 만들어줘"
    - pai apple ai "내일 2시에 회의 일정 만들어줘"
    - pai apple ai "스타벅스 찾아줘"
    """
    command_text = " ".join(command)
    click.echo(f"🤖 자연어 명령어: {command_text}")
    
    # 간단한 키워드 기반 라우팅 (나중에 LLM으로 개선)
    if any(word in command_text.lower() for word in ["연락처", "전화번호", "contact"]):
        click.echo("📱 연락처 관련 명령어로 해석됩니다.")
        click.echo("💡 직접 명령어: pai apple contacts --help")
    
    elif any(word in command_text.lower() for word in ["노트", "메모", "note"]):
        click.echo("📝 노트 관련 명령어로 해석됩니다.")
        click.echo("💡 직접 명령어: pai apple notes --help")
    
    elif any(word in command_text.lower() for word in ["일정", "캘린더", "미팅", "회의", "calendar"]):
        click.echo("📅 캘린더 관련 명령어로 해석됩니다.")
        click.echo("💡 직접 명령어: pai apple calendar --help")
    
    elif any(word in command_text.lower() for word in ["지도", "위치", "찾기", "길찾기", "map"]):
        click.echo("🗺️ 지도 관련 명령어로 해석됩니다.")
        click.echo("💡 직접 명령어: pai apple maps --help")
    
    else:
        click.echo("❓ 명령어를 이해하지 못했습니다.")
        click.echo("📚 사용 가능한 명령어:")
        click.echo("  • pai apple contacts  - 연락처 관리")
        click.echo("  • pai apple notes     - 노트 관리")
        click.echo("  • pai apple messages  - 메시지 관리")
        click.echo("  • pai apple calendar  - 캘린더 관리")
        click.echo("  • pai apple maps      - 지도 검색")


# Click 비동기 함수들을 동기화
def make_sync(async_func):
    """비동기 함수를 동기 함수로 변환"""
    def sync_func(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))
    return sync_func

# 모든 비동기 명령어를 동기화
contacts.callback = make_sync(contacts.callback)
notes.callback = make_sync(notes.callback)
messages.callback = make_sync(messages.callback)
calendar.callback = make_sync(calendar.callback)
maps.callback = make_sync(maps.callback)
ai.callback = make_sync(ai.callback)
