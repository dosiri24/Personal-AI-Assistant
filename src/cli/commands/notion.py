"""
Notion 통합 도구 관리 명령어 그룹 (notion)
"""

import asyncio
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors


@click.group()
def notion():
    """Notion 통합 도구 관리"""
    pass


@notion.command(name="test-connection")
@click.option('--token', help='Notion API 토큰 (설정되지 않은 경우)')
def test_connection(token):
    """Notion API 연결을 테스트합니다."""
    async def test_notion_connection():
        try:
            from src.tools.notion import NotionClient, NotionConnectionConfig
            from src.config import get_settings
            
            # 토큰 설정
            if token:
                click.echo(f"🔑 제공된 토큰으로 연결 테스트...")
                config = NotionConnectionConfig(api_token=token)
            else:
                settings = get_settings()
                notion_token = getattr(settings, 'notion_api_token', None)
                if not notion_token:
                    click.echo("❌ Notion API 토큰이 설정되지 않았습니다.")
                    click.echo("   --token 옵션으로 토큰을 제공하거나 환경변수를 설정하세요.")
                    return
                click.echo("🔑 설정된 토큰으로 연결 테스트...")
                config = NotionConnectionConfig(api_token=notion_token)
            
            # 클라이언트 생성 및 테스트
            client = NotionClient(config=config, use_async=True)
            
            # 워크스페이스 검색으로 연결 테스트
            click.echo("📡 Notion API 연결 중...")
            
            # 간단한 검색 테스트
            try:
                search_result = await client.search("")
                
                if search_result:
                    click.echo("✅ Notion API 연결 성공!")
                    results = search_result.get('results', [])
                    click.echo(f"   워크스페이스에서 {len(results)}개의 페이지/데이터베이스를 찾았습니다.")
                    if results:
                        click.echo("   최근 페이지:")
                        for i, result in enumerate(results[:3]):  # 상위 3개만 표시
                            title = "제목 없음"
                            if result.get('properties') and result['properties'].get('title'):
                                title_prop = result['properties']['title']
                                if title_prop.get('title') and title_prop['title']:
                                    title = title_prop['title'][0]['text']['content']
                            elif result.get('properties') and result['properties'].get('Name'):
                                name_prop = result['properties']['Name']
                                if name_prop.get('title') and name_prop['title']:
                                    title = name_prop['title'][0]['text']['content']
                            
                            click.echo(f"     {i+1}. {title} ({result.get('object', 'unknown')})")
                else:
                    click.echo("❌ 워크스페이스 정보를 가져올 수 없습니다.")
            except Exception as search_error:
                click.echo(f"❌ 검색 실패: {search_error}")
                # 기본 연결만 확인
                click.echo("   기본 연결은 성공했지만 검색에 실패했습니다.")
                
        except Exception as e:
            click.echo(f"❌ Notion API 연결 실패: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_notion_connection())


@notion.command(name="create-event")
@click.option('--database-id', help='캘린더 데이터베이스 ID')
@click.option('--title', required=True, help='이벤트 제목')
@click.option('--date', required=True, help='이벤트 날짜 (예: "2024-01-15" 또는 "tomorrow")')
@click.option('--description', help='이벤트 설명')
def create_event(database_id, title, date, description):
    """Notion 캘린더에 새 이벤트를 생성합니다."""
    async def create_calendar_event():
        try:
            from src.tools.notion import CalendarTool
            from src.config import get_settings
            from src.mcp.base_tool import ExecutionStatus
            
            settings = get_settings()
            
            # 캘린더 도구 생성
            calendar_tool = CalendarTool(settings=settings)
            
            # 매개변수 구성
            params = {
                'action': 'create',
                'title': title,
                'start_date': date
            }
            
            if database_id:
                params['database_id'] = database_id
            
            if description:
                params['description'] = description
            
            click.echo(f"📅 캘린더 이벤트 생성: {title}")
            click.echo(f"📅 날짜: {date}")
            
            # 도구 실행
            result = await calendar_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS:
                click.echo("✅ 이벤트가 성공적으로 생성되었습니다!")
                if result.data:
                    click.echo(f"   이벤트 ID: {result.data.get('id', 'Unknown')}")
                    click.echo(f"   URL: {result.data.get('url', 'Unknown')}")
            else:
                click.echo(f"❌ 이벤트 생성 실패: {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ 이벤트 생성 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(create_calendar_event())


@notion.command(name="list-events")
@click.option('--database-id', help='캘린더 데이터베이스 ID')
@click.option('--limit', default=10, help='조회할 이벤트 수 (기본값: 10)')
def list_events(database_id, limit):
    """Notion 캘린더의 이벤트 목록을 조회합니다."""
    async def list_calendar_events():
        try:
            from src.tools.notion import CalendarTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            
            # 캘린더 도구 생성
            calendar_tool = CalendarTool(settings=settings)
            
            # 매개변수 구성
            params = {
                'action': 'list',
                'limit': limit
            }
            
            if database_id:
                params['database_id'] = database_id
            
            click.echo(f"📅 캘린더 이벤트 조회 (최대 {limit}개)...")
            
            # 도구 실행
            result = await calendar_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS and result.data:
                events = result.data.get('events', [])
                click.echo(f"✅ {len(events)}개의 이벤트를 찾았습니다:")
                
                for i, event in enumerate(events, 1):
                    click.echo(f"\n   {i}. {event.get('title', '제목 없음')}")
                    click.echo(f"      📅 날짜: {event.get('date', '날짜 없음')}")
                    if event.get('description'):
                        click.echo(f"      📝 설명: {event.get('description')}")
                    click.echo(f"      🔗 URL: {event.get('url', 'URL 없음')}")
            else:
                click.echo("❌ 이벤트 조회 실패:")
                click.echo(f"   {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ 이벤트 조회 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(list_calendar_events())


@notion.command(name="create-todo")
@click.option('--database-id', help='Todo 데이터베이스 ID')
@click.option('--title', required=True, help='할일 제목')
@click.option('--description', help='할일 설명')
@click.option('--priority', type=click.Choice(['낮음', '중간', '높음']), default='중간', help='우선순위')
@click.option('--due-date', help='마감일 (예: "2024-01-15" 또는 "next week")')
def create_todo(database_id, title, description, priority, due_date):
    """Notion Todo에 새 할일을 생성합니다."""
    async def create_todo_item():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            
            # Todo 도구 생성
            todo_tool = TodoTool(settings=settings)
            
            # 매개변수 구성
            params = {
                'action': 'create',
                'title': title,
                'priority': priority
            }
            
            if database_id:
                params['database_id'] = database_id
            
            if description:
                params['description'] = description
                
            if due_date:
                params['due_date'] = due_date
            
            click.echo(f"✅ Todo 항목 생성: {title}")
            click.echo(f"🎯 우선순위: {priority}")
            
            # 도구 실행
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS:
                click.echo("✅ Todo가 성공적으로 생성되었습니다!")
                if result.data:
                    click.echo(f"   Todo ID: {result.data.get('id', 'Unknown')}")
                    click.echo(f"   URL: {result.data.get('url', 'Unknown')}")
            else:
                click.echo(f"❌ Todo 생성 실패: {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo 생성 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(create_todo_item())


@notion.command(name="list-todos")
@click.option('--database-id', help='Todo 데이터베이스 ID')
@click.option('--filter', type=click.Choice(['all', 'pending', 'completed', 'overdue']), 
              default='all', help='필터 타입')
@click.option('--limit', default=10, help='조회할 Todo 수 (기본값: 10)')
def list_todos(database_id, filter, limit):
    """Notion Todo 목록을 조회합니다."""
    async def list_todo_items():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            
            # Todo 도구 생성
            todo_tool = TodoTool(settings=settings)
            
            # 매개변수 구성
            params = {
                'action': 'list',
                'filter': filter,
                'limit': limit
            }
            
            if database_id:
                params['database_id'] = database_id
            
            click.echo(f"📋 Todo 목록 조회 (필터: {filter}, 최대 {limit}개)...")
            
            # 도구 실행
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS and result.data:
                todos = result.data.get('todos', [])
                click.echo(f"✅ {len(todos)}개의 Todo를 찾았습니다:")
                
                for i, todo in enumerate(todos, 1):
                    status_icon = "✅" if todo.get('completed') else "⏳"
                    priority_icons = {'low': '🟢', 'medium': '🟡', 'high': '🔴'}
                    priority_icon = priority_icons.get(todo.get('priority', 'medium'), '🟡')
                    
                    click.echo(f"\n   {i}. {status_icon} {todo.get('title', '제목 없음')}")
                    click.echo(f"      {priority_icon} 우선순위: {todo.get('priority', 'medium')}")
                    
                    if todo.get('due_date'):
                        click.echo(f"      📅 마감일: {todo.get('due_date')}")
                    if todo.get('description'):
                        click.echo(f"      📝 설명: {todo.get('description')}")
                    
                    # 프로젝트/경험 정보 추가
                    if todo.get('projects'):
                        projects_text = ", ".join(todo['projects'])
                        click.echo(f"      🏗️ 프로젝트: {projects_text}")
                    
                    click.echo(f"      🔗 URL: {todo.get('url', 'URL 없음')}")
            else:
                click.echo("❌ Todo 조회 실패:")
                click.echo(f"   {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo 조회 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(list_todo_items())


@notion.command(name="get-todo")
@click.option('--id', required=True, help='조회할 Todo ID')
def get_todo(id):
    """특정 Todo의 상세 정보를 조회합니다."""
    async def get_todo_item():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            todo_tool = TodoTool(settings=settings)
            
            params = {
                'action': 'get',
                'todo_id': id
            }
            
            click.echo(f"📋 Todo 조회 중 (ID: {id[:8]}...)...")
            
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS and result.data:
                todo = result.data.get('todo', {})
                status_icon = "✅" if todo.get('completed') else "⏳"
                priority_icons = {'낮음': '🟢', '중간': '🟡', '높음': '🔴'}
                priority_icon = priority_icons.get(todo.get('priority', '중간'), '🟡')
                
                click.echo(f"\n{status_icon} {todo.get('title', '제목 없음')}")
                click.echo(f"   {priority_icon} 우선순위: {todo.get('priority', '중간')}")
                click.echo(f"   📅 상태: {todo.get('status', '알 수 없음')}")
                
                if todo.get('due_date'):
                    click.echo(f"   ⏰ 마감일: {todo.get('due_date')}")
                if todo.get('description'):
                    click.echo(f"   📝 설명: {todo.get('description')}")
                if todo.get('projects'):
                    projects_text = ", ".join(todo['projects'])
                    click.echo(f"   🏗️ 프로젝트: {projects_text}")
                
                click.echo(f"   🆔 ID: {todo.get('id', 'Unknown')}")
                click.echo(f"   🔗 URL: {todo.get('url', 'URL 없음')}")
                click.echo(f"   📅 생성일: {todo.get('created_time', 'Unknown')}")
                click.echo(f"   ✏️ 수정일: {todo.get('last_edited_time', 'Unknown')}")
            else:
                click.echo("❌ Todo 조회 실패:")
                click.echo(f"   {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo 조회 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(get_todo_item())


@notion.command(name="update-todo")
@click.option('--id', required=True, help='수정할 Todo ID')
@click.option('--title', help='새 제목')
@click.option('--description', help='새 설명')
@click.option('--priority', type=click.Choice(['높음', '중간', '낮음']), help='새 우선순위')
@click.option('--due-date', help='새 마감일 (ISO 형식 또는 자연어)')
def update_todo(id, title, description, priority, due_date):
    """Todo를 수정합니다."""
    async def update_todo_item():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            todo_tool = TodoTool(settings=settings)
            
            params = {
                'action': 'update',
                'todo_id': id
            }
            
            if title:
                params['title'] = title
            if description:
                params['description'] = description
            if priority:
                params['priority'] = priority
            if due_date:
                params['due_date'] = due_date
            
            if len(params) == 2:  # action과 todo_id만 있는 경우
                click.echo("❌ 수정할 내용을 지정해주세요 (--title, --description, --priority, --due-date 중 하나 이상)")
                return
            
            click.echo(f"✏️ Todo 수정 중 (ID: {id[:8]}...)...")
            
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS:
                click.echo("✅ Todo가 성공적으로 수정되었습니다!")
                if result.data:
                    click.echo(f"   제목: {result.data.get('title', 'Unknown')}")
                    click.echo(f"   수정된 필드: {', '.join(result.data.get('updated_fields', []))}")
            else:
                click.echo(f"❌ Todo 수정 실패: {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo 수정 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(update_todo_item())


@notion.command(name="complete-todo")
@click.option('--id', required=True, help='완료 처리할 Todo ID')
@click.option('--completed', type=bool, default=True, help='완료 상태 (True: 완료, False: 미완료)')
def complete_todo(id, completed):
    """Todo의 완료 상태를 변경합니다."""
    async def complete_todo_item():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            todo_tool = TodoTool(settings=settings)
            
            params = {
                'action': 'complete',
                'todo_id': id,
                'completed': completed
            }
            
            action_text = "완료 처리" if completed else "미완료로 변경"
            click.echo(f"✅ Todo {action_text} 중 (ID: {id[:8]}...)...")
            
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS:
                click.echo(f"✅ Todo {action_text}가 완료되었습니다!")
                if result.data:
                    click.echo(f"   제목: {result.data.get('title', 'Unknown')}")
                    click.echo(f"   상태: {result.data.get('status', 'Unknown')}")
            else:
                click.echo(f"❌ Todo {action_text} 실패: {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo {action_text} 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(complete_todo_item())


@notion.command(name="delete-todo")
@click.option('--id', required=True, help='삭제할 Todo ID')
@click.option('--confirm', is_flag=True, help='삭제 확인')
def delete_todo(id, confirm):
    """Todo를 삭제합니다."""
    if not confirm:
        click.echo("❌ 삭제하려면 --confirm 플래그를 사용해주세요")
        return
    
    async def delete_todo_item():
        try:
            from src.tools.notion import TodoTool
            from src.mcp.base_tool import ExecutionStatus
            from src.config import get_settings
            
            settings = get_settings()
            todo_tool = TodoTool(settings=settings)
            
            params = {
                'action': 'delete',
                'todo_id': id
            }
            
            click.echo(f"🗑️ Todo 삭제 중 (ID: {id[:8]}...)...")
            
            result = await todo_tool.execute(**params)
            
            if result.status == ExecutionStatus.SUCCESS:
                click.echo("✅ Todo가 성공적으로 삭제되었습니다!")
                if result.data:
                    click.echo(f"   제목: {result.data.get('title', 'Unknown')}")
            else:
                click.echo(f"❌ Todo 삭제 실패: {result.error_message}")
                
        except Exception as e:
            click.echo(f"❌ Todo 삭제 중 오류: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(delete_todo_item())


# Notion 그룹을 export
notion_group = notion
