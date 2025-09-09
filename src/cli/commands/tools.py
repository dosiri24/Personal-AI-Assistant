"""
MCP 도구 관리 명령어 그룹 (tools)
"""

import asyncio
import json
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors


@click.group()
def tools():
    """MCP 도구 관리 명령어"""
    pass


@tools.command()
@click.option("--category", help="카테고리별 필터링")
@click.option("--tag", help="태그별 필터링") 
@click.option("--all", "show_all", is_flag=True, help="비활성화된 도구도 포함")
def list(category, tag, show_all):
    """등록된 도구 목록을 조회합니다."""
    from src.mcp.registry import get_registry
    from src.mcp.base_tool import ToolCategory
    
    async def list_tools():
        try:
            registry = get_registry()
            
            # 카테고리 필터
            filter_category = None
            if category:
                try:
                    filter_category = ToolCategory(category.lower())
                except ValueError:
                    click.echo(f"❌ 잘못된 카테고리: {category}")
                    click.echo(f"   사용 가능한 카테고리: {', '.join([c.value for c in ToolCategory])}")
                    return
            
            # 도구 목록 가져오기
            tool_names = registry.list_tools(
                category=filter_category,
                tag=tag,
                enabled_only=not show_all
            )
            
            if not tool_names:
                click.echo("📭 등록된 도구가 없습니다.")
                return
            
            click.echo(f"🔧 등록된 도구 목록 ({len(tool_names)}개)")
            click.echo("-" * 50)
            
            for tool_name in tool_names:
                metadata = registry.get_tool_metadata(tool_name)
                stats = registry.get_tool_stats(tool_name)
                
                if metadata and stats:
                    status = "🟢" if stats["enabled"] else "🔴"
                    init_status = "✅" if stats["initialized"] else "⏳"
                    
                    click.echo(f"{status} {init_status} {tool_name}")
                    click.echo(f"    📝 {metadata.description}")
                    click.echo(f"    📂 카테고리: {metadata.category.value}")
                    click.echo(f"    🏷️  태그: {', '.join(metadata.tags) if metadata.tags else '없음'}")
                    click.echo(f"    📊 사용 횟수: {stats['usage_count']}")
                    click.echo("")
        
        except Exception as e:
            click.echo(f"❌ 도구 목록 조회 실패: {e}")
    
    asyncio.run(list_tools())


@tools.command()
@click.argument("tool_name")
def info(tool_name):
    """도구의 상세 정보를 조회합니다."""
    from src.mcp.registry import get_registry
    
    async def show_tool_info():
        try:
            registry = get_registry()
            metadata = registry.get_tool_metadata(tool_name)
            stats = registry.get_tool_stats(tool_name)
            
            if not metadata or not stats:
                click.echo(f"❌ 도구를 찾을 수 없습니다: {tool_name}")
                return
            
            click.echo(f"🔧 도구 정보: {tool_name}")
            click.echo("=" * 50)
            click.echo(f"📝 설명: {metadata.description}")
            click.echo(f"📦 버전: {metadata.version}")
            click.echo(f"👤 작성자: {metadata.author}")
            click.echo(f"📂 카테고리: {metadata.category.value}")
            click.echo(f"🏷️  태그: {', '.join(metadata.tags) if metadata.tags else '없음'}")
            click.echo(f"🔐 인증 필요: {'예' if metadata.requires_auth else '아니오'}")
            click.echo(f"⏱️  타임아웃: {metadata.timeout}초")
            click.echo(f"🚦 속도 제한: {metadata.rate_limit or '없음'}")
            click.echo("")
            
            click.echo("📊 사용 통계:")
            click.echo(f"   상태: {'활성화' if stats['enabled'] else '비활성화'}")
            click.echo(f"   초기화: {'완료' if stats['initialized'] else '미완료'}")
            click.echo(f"   등록일: {stats['registered_at']}")
            click.echo(f"   마지막 사용: {stats['last_used'] or '사용 안함'}")
            click.echo(f"   사용 횟수: {stats['usage_count']}")
            click.echo("")
            
            if metadata.parameters:
                click.echo("⚙️  매개변수:")
                for param in metadata.parameters:
                    required_text = "필수" if param.required else "선택"
                    default_text = f" (기본값: {param.default})" if param.default is not None else ""
                    click.echo(f"   • {param.name} ({param.type.value}, {required_text}){default_text}")
                    click.echo(f"     {param.description}")
            
            # 사용 예제
            try:
                tool = await registry.get_tool(tool_name)
                if tool:
                    example = tool.get_usage_example()
                    click.echo("")
                    click.echo("📋 사용 예제:")
                    click.echo(json.dumps(example, indent=2, ensure_ascii=False))
            except:
                pass
        
        except Exception as e:
            click.echo(f"❌ 도구 정보 조회 실패: {e}")
    
    asyncio.run(show_tool_info())


@tools.command()
@click.argument("tool_name")
@click.argument("parameters", required=False)
@click.option("--sync", is_flag=True, help="동기 실행 모드")
def execute(tool_name, parameters, sync):
    """도구를 실행합니다."""
    from src.mcp.executor import get_executor, ExecutionMode
    
    async def execute_tool():
        try:
            # 매개변수 파싱
            params = {}
            if parameters:
                try:
                    params = json.loads(parameters)
                except json.JSONDecodeError:
                    click.echo("❌ 매개변수가 올바른 JSON 형식이 아닙니다.")
                    return
            
            # 실행 모드 설정
            mode = ExecutionMode.SYNC if sync else ExecutionMode.ASYNC
            
            click.echo(f"🚀 도구 실행 시작: {tool_name}")
            click.echo(f"⚙️  매개변수: {json.dumps(params, ensure_ascii=False)}")
            click.echo(f"🔄 실행 모드: {mode.value}")
            click.echo("-" * 40)
            
            # 도구 실행
            executor = get_executor()
            result = await executor.execute_tool(tool_name, params, mode)
            
            # 결과 출력
            if result.result.is_success:
                click.echo("✅ 실행 성공!")
                click.echo(f"📤 결과: {json.dumps(result.result.data, ensure_ascii=False, indent=2)}")
            else:
                click.echo("❌ 실행 실패!")
                click.echo(f"💬 오류: {result.result.error_message}")
            
            # 실행 정보
            click.echo("")
            click.echo("📊 실행 정보:")
            exec_time = result.result.execution_time if result.result.execution_time is not None else 0.0
            click.echo(f"   실행 ID: {result.context.execution_id}")
            click.echo(f"   실행 시간: {exec_time:.3f}초")
            click.echo(f"   상태: {result.result.status.value}")
            
            # 리소스 사용량
            if result.resource_usage:
                click.echo(f"   메모리 사용량: {result.resource_usage.get('memory_mb', 0):.1f}MB")
                click.echo(f"   CPU 사용률: {result.resource_usage.get('cpu_percent', 0):.1f}%")
            
            # 경고
            if result.warnings:
                click.echo("")
                click.echo("⚠️  경고:")
                for warning in result.warnings:
                    click.echo(f"   • {warning}")
        
        except Exception as e:
            click.echo(f"❌ 도구 실행 실패: {e}")
    
    asyncio.run(execute_tool())


@tools.command()
@click.argument("tool_name")
def enable(tool_name):
    """도구를 활성화합니다."""
    from src.mcp.registry import get_registry
    
    async def enable_tool():
        try:
            registry = get_registry()
            success = await registry.enable_tool(tool_name)
            
            if success:
                click.echo(f"✅ 도구 활성화 완료: {tool_name}")
            else:
                click.echo(f"❌ 도구 활성화 실패: {tool_name}")
        
        except Exception as e:
            click.echo(f"❌ 도구 활성화 실패: {e}")
    
    asyncio.run(enable_tool())


@tools.command()
@click.argument("tool_name")
def disable(tool_name):
    """도구를 비활성화합니다."""
    from src.mcp.registry import get_registry
    
    async def disable_tool():
        try:
            registry = get_registry()
            success = await registry.disable_tool(tool_name)
            
            if success:
                click.echo(f"✅ 도구 비활성화 완료: {tool_name}")
            else:
                click.echo(f"❌ 도구 비활성화 실패: {tool_name}")
        
        except Exception as e:
            click.echo(f"❌ 도구 비활성화 실패: {e}")
    
    asyncio.run(disable_tool())


@tools.command()
def stats():
    """도구 사용 통계를 조회합니다."""
    from src.mcp.registry import get_registry
    from src.mcp.executor import get_executor
    
    async def show_stats():
        try:
            registry = get_registry()
            executor = get_executor()
            
            # 레지스트리 통계
            registry_stats = registry.get_registry_stats()
            click.echo("📊 도구 레지스트리 통계")
            click.echo("-" * 30)
            click.echo(f"총 도구 수: {registry_stats['total_tools']}")
            click.echo(f"활성화된 도구: {registry_stats['enabled_tools']}")
            click.echo(f"초기화된 도구: {registry_stats['initialized_tools']}")
            click.echo(f"총 태그 수: {registry_stats['total_tags']}")
            click.echo("")
            
            # 카테고리별 통계
            if registry_stats['categories']:
                click.echo("📂 카테고리별 분포:")
                for category, count in registry_stats['categories'].items():
                    click.echo(f"   {category}: {count}개")
                click.echo("")
            
            # 실행 엔진 통계
            execution_stats = executor.get_execution_stats()
            if execution_stats['total_executions'] > 0:
                click.echo("🚀 실행 엔진 통계")
                click.echo("-" * 30)
                click.echo(f"총 실행 횟수: {execution_stats['total_executions']}")
                click.echo(f"성공: {execution_stats['successful']}")
                click.echo(f"실패: {execution_stats['failed']}")
                click.echo(f"타임아웃: {execution_stats['timeouts']}")
                click.echo(f"성공률: {execution_stats['success_rate']:.1f}%")
                click.echo(f"평균 실행 시간: {execution_stats['average_execution_time']:.3f}초")
                click.echo(f"현재 실행 중: {execution_stats['active_executions']}개")
        
        except Exception as e:
            click.echo(f"❌ 통계 조회 실패: {e}")
    
    asyncio.run(show_stats())


@tools.command()
@click.option("--limit", default=10, help="표시할 히스토리 수")
def history(limit):
    """도구 실행 히스토리를 조회합니다."""
    from src.mcp.executor import get_executor
    
    def show_history():
        try:
            executor = get_executor()
            history_data = executor.get_execution_history(limit)
            
            if not history_data:
                click.echo("📭 실행 히스토리가 없습니다.")
                return
            
            click.echo(f"📜 최근 실행 히스토리 ({len(history_data)}개)")
            click.echo("-" * 60)
            
            for entry in reversed(history_data):  # 최신순
                status_icon = {
                    "success": "✅",
                    "error": "❌", 
                    "timeout": "⏰",
                    "pending": "⏳",
                    "running": "🔄"
                }.get(entry['result']['status'], "❓")
                
                click.echo(f"{status_icon} {entry['tool_name']} ({entry['execution_id']})")
                click.echo(f"    시작: {entry['started_at']}")
                click.echo(f"    실행 시간: {entry['elapsed_time']:.3f}초")
                click.echo(f"    모드: {entry['mode']}")
                
                if entry['result']['status'] == 'error':
                    click.echo(f"    오류: {entry['result'].get('error_message', '알 수 없음')}")
                
                if entry['warnings']:
                    click.echo(f"    경고: {', '.join(entry['warnings'])}")
                
                click.echo("")
        
        except Exception as e:
            click.echo(f"❌ 히스토리 조회 실패: {e}")
    
    show_history()


@tools.command()
@click.option("--package", default="src.tools", help="도구를 찾을 패키지 경로")
def discover(package):
    """패키지에서 도구를 자동 발견하고 등록합니다."""
    from src.mcp.registry import get_registry
    
    async def discover_tools():
        try:
            click.echo(f"🔍 도구 자동 발견 시작: {package}")
            click.echo("-" * 40)
            
            registry = get_registry()
            discovered_count = await registry.discover_tools(package)
            
            if discovered_count > 0:
                click.echo(f"✅ {discovered_count}개 도구 발견 및 등록 완료!")
                
                # 등록된 도구 목록 표시
                tool_names = registry.list_tools()
                if tool_names:
                    click.echo("")
                    click.echo("📋 등록된 도구:")
                    for tool_name in tool_names:
                        metadata = registry.get_tool_metadata(tool_name)
                        if metadata:
                            click.echo(f"   • {tool_name} - {metadata.description}")
            else:
                click.echo("📭 발견된 도구가 없습니다.")
        
        except Exception as e:
            click.echo(f"❌ 도구 자동 발견 실패: {e}")
    
    asyncio.run(discover_tools())


@tools.command(name="execute-ai")
@click.option("--command", required=True, help="자연어 명령")
@click.option("--user-id", type=int, default=0, help="사용자 ID")
def execute_ai(command, user_id):
    """AI 엔진을 통해 자연어 명령을 실행합니다."""
    click.echo(f"🧠 AI 엔진을 통한 자연어 명령 실행: {command}")
    
    # Phase 3에서 구현될 AI 엔진 통합 대신 임시 응답
    click.echo("⏳ 자연어 분석 중...")
    click.echo("✅ 명령 분석 완료 (Mock 결과)")
    click.echo(f"🎯 추론된 의도: task_management")
    click.echo(f"🔧 선택된 도구: TodoTool")
    click.echo(f"⚙️  매개변수: action=create, title='{command}'")
    click.echo("\nℹ️  실제 AI 엔진 통합은 Phase 3에서 구현될 예정입니다.")


@tools.command(name="test-integration")
def test_integration():
    """MCP와 AI 엔진 통합 테스트를 실행합니다."""
    click.echo("🧪 MCP-AI 통합 테스트 시작...")
    
    # Phase 3에서 구현될 통합 테스트 대신 임시 구현
    click.echo("⏳ 도구 레지스트리 초기화...")
    click.echo("⏳ AI 엔진 연결...")
    click.echo("⏳ 통합 테스트 실행...")
    click.echo("✅ 기본 통합 테스트 완료 (Mock 결과)")
    click.echo("📊 테스트 결과:")
    click.echo("   - 도구 발견: ✅")
    click.echo("   - AI 명령 분석: ✅")
    click.echo("   - 도구 실행: ✅")
    click.echo("   - 결과 반환: ✅")
    click.echo("\nℹ️  실제 MCP-AI 통합은 Phase 3에서 구현될 예정입니다.")


@tools.command(name="nl")
@click.option("--text", "text", required=True, help="자연어 명령")
@click.option("--user-id", default="cli-user", help="사용자 ID")
def execute_natural_language(text: str, user_id: str):
    """자연어로 MCP 도구를 실행합니다 (Mock LLM 기반)."""
    import asyncio
    from src.mcp.mcp_integration import MCPIntegration

    async def _run():
        click.echo("🧠 에이전틱 의사결정 + MCP 실행 초기화...")
        integration = MCPIntegration()
        await integration.initialize()

        click.echo(f"💬 입력: {text}")
        result = await integration.process_user_request(text, user_id=user_id)

        click.echo("\n✅ 결과:")
        click.echo(result)

    try:
        asyncio.run(_run())
    except Exception as e:
        click.echo(f"❌ 실행 실패: {e}")


# Tools 그룹을 export
tools_group = tools
