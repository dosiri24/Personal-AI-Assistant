"""
테스트 관련 명령어들 (test-config, test-discord, test-ai, test-nlp, test-logs 등)
"""

import asyncio
import json
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors


@click.command(name="test-config")
def test_config():
    """환경 설정을 테스트합니다."""
    click.echo("🔧 환경 설정 테스트를 시작합니다...")
    
    from src.config import get_settings
    
    try:
        settings = get_settings()
        
        click.echo("📋 설정 정보:")
        click.echo(f"   환경: {settings.environment}")
        click.echo(f"   디버그 모드: {settings.debug}")
        click.echo(f"   로그 레벨: {settings.log_level}")
        
        click.echo("\n🤖 AI 설정:")
        click.echo(f"   AI 모델: {settings.ai_model}")
        click.echo(f"   AI 온도: {settings.ai_temperature}")
        click.echo(f"   최대 토큰: {settings.ai_max_tokens}")
        
        click.echo("\n🔑 API 키 상태:")
        click.echo(f"   Google API 키: {'✅ 설정됨' if settings.has_valid_api_key() else '❌ 미설정'}")
        click.echo(f"   Discord Bot 토큰: {'✅ 설정됨' if settings.has_valid_discord_token() else '❌ 미설정'}")
        click.echo(f"   Notion API 토큰: {'✅ 설정됨' if settings.notion_api_token else '❌ 미설정'}")
        
        click.echo("\n📁 디렉토리 경로:")
        click.echo(f"   프로젝트 루트: {settings.get_project_root()}")
        click.echo(f"   로그 디렉토리: {settings.get_logs_dir()}")
        click.echo(f"   데이터 디렉토리: {settings.get_data_dir()}")
        
        click.echo("\n✅ 환경 설정 테스트 완료")
        
    except Exception as e:
        click.echo(f"❌ 환경 설정 테스트 실패: {e}")


@click.command(name="test-discord")
@click.option('--quick', is_flag=True, help='빠른 연결 테스트만 수행')
def test_discord(quick):
    """Discord Bot 연결을 테스트합니다."""
    click.echo("🤖 Discord Bot 연결 테스트를 시작합니다...")
    
    try:
        asyncio.run(_test_discord_connection(quick=quick))
    except Exception as e:
        click.echo(f"❌ Discord Bot 테스트 실패: {e}")


async def _test_discord_connection(quick: bool = False):
    """Discord Bot 연결 테스트 (비동기)"""
    from src.config import get_settings
    from src.discord_bot import DiscordBot
    from src.discord_bot.bot import setup_basic_commands
    import asyncio
    
    logger = get_logger("discord_test")
    settings = get_settings()
    
    # 설정 확인
    if not settings.discord_bot_token:
        click.echo("❌ Discord Bot 토큰이 설정되지 않았습니다.")
        click.echo("   .env 파일에 DISCORD_BOT_TOKEN을 설정해주세요.")
        return
    
    click.echo("✅ Discord Bot 토큰이 설정되어 있습니다.")
    
    try:
        # Bot 인스턴스 생성
        click.echo("⏳ Discord Bot 인스턴스 생성 중...")
        discord_bot = DiscordBot(settings)
        
        # 기본 명령어 설정
        await setup_basic_commands(discord_bot)
        click.echo("✅ Discord Bot 초기화 완료")
        
        if quick:
            click.echo("⚡ 빠른 테스트 모드: 연결 준비만 확인")
            status = discord_bot.get_status()
            click.echo(f"   허용된 사용자: {status['allowed_users_count']}명")
            click.echo(f"   관리자 사용자: {status['admin_users_count']}명")
            click.echo("✅ Discord Bot 테스트 완료 (연결 없이)")
            return
        
        # 실제 Discord 연결 테스트
        click.echo("⏳ Discord 서버에 연결 중...")
        click.echo("   (연결 테스트 후 자동으로 종료됩니다)")
        
        # 5초 후 자동 종료하는 태스크
        async def auto_disconnect():
            await asyncio.sleep(5)
            await discord_bot.stop()
            click.echo("⏹️  테스트 완료 - Bot 연결 해제")
        
        # 자동 종료 태스크 시작
        disconnect_task = asyncio.create_task(auto_disconnect())
        
        try:
            # Discord Bot 시작 (연결 테스트)
            await discord_bot.start()
        except Exception as e:
            # 예상된 종료는 무시
            if "Connection is closed" not in str(e):
                raise
        
        # 상태 확인
        status = discord_bot.get_status()
        click.echo("\n📊 연결 테스트 결과:")
        if status['user']:
            click.echo(f"   Bot 계정: {status['user']}")
            click.echo(f"   연결된 서버 수: {status['guild_count']}")
        click.echo("✅ Discord Bot 연결 테스트 완료")
        
    except Exception as e:
        click.echo(f"❌ Discord Bot 연결 실패: {e}")
        logger.error(f"Discord Bot 테스트 실패: {e}")
        raise


@click.command(name="test-logs")
def test_logs():
    """로깅 시스템을 테스트합니다."""
    click.echo("🧪 로깅 시스템 테스트를 시작합니다...")
    
    from src.utils.logger import PersonalAILogger
    
    # 로깅 시스템 테스트
    logger_system = PersonalAILogger()
    logger_system.test_logging()
    
    click.echo("✅ 로깅 시스템 테스트가 완료되었습니다.")
    click.echo("📁 로그 파일들을 logs/ 디렉토리에서 확인할 수 있습니다.")


@click.command(name="test-old-parsing")
@click.argument('message', required=False)
def test_old_parsing(message):
    """구버전 명령어 파싱 시스템을 테스트합니다. (더 이상 사용되지 않음)"""
    click.echo("⚠️  구버전 파싱 시스템은 더 이상 사용되지 않습니다.")
    click.echo("✨ 새로운 단순화된 메시지 처리 시스템을 사용하세요:")
    if message:
        click.echo(f"   python -m src.cli.main process-message --message \"{message}\"")
    else:
        click.echo(f"   python -m src.cli.main process-message --message \"테스트 메시지\"")


@click.command(name="test-ai")
@click.option("--message", default="AI 엔진 테스트입니다", help="테스트할 메시지")
@click.option("--provider", default="gemini", help="사용할 AI 제공자 (gemini/openai)")
def test_ai(message, provider):
    """AI 엔진 연결 테스트"""
    click.echo(f"🧠 AI 엔진 연결 테스트를 시작합니다... (제공자: {provider})")
    
    async def test_ai_engine():
        try:
            from src.ai_engine.llm_provider import GeminiProvider, ChatMessage
            from src.config import get_settings
            
            settings = get_settings()
            
            # AI 제공자 초기화
            if provider.lower() == "gemini":
                ai_provider = GeminiProvider()
                
                # 초기화 실행
                click.echo("⚙️ AI 모델 초기화 중...")
                init_success = await ai_provider.initialize()
                if not init_success:
                    click.echo("❌ AI 모델 초기화 실패")
                    return
                    
                click.echo("✅ AI 모델 초기화 완료")
            else:
                click.echo(f"❌ 지원되지 않는 AI 제공자: {provider}")
                return
            
            click.echo("⏳ AI 모델 연결 중...")
            
            # 연결 테스트
            test_messages = [
                ChatMessage(role="user", content=f"이것은 연결 테스트입니다. 다음 메시지에 간단히 응답해주세요: {message}")
            ]
            
            response = await ai_provider.generate_response(test_messages)
            
            if response and response.content:
                click.echo("✅ AI 엔진 연결 성공!")
                click.echo(f"📝 테스트 메시지: {message}")
                click.echo(f"🤖 AI 응답: {response.content}")
                if hasattr(response, 'metadata') and response.metadata:
                    click.echo(f"🔢 토큰 사용량: {response.metadata.get('token_count', 'N/A')}")
            else:
                click.echo("❌ AI 응답이 비어있습니다.")
                
        except Exception as e:
            click.echo(f"❌ AI 엔진 테스트 실패: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test_ai_engine())


@click.command(name="test-nlp")
@click.option("--command", default="할일 추가하기", help="테스트할 자연어 명령")
@click.option("--user-id", type=int, default=123, help="사용자 ID")
def test_nlp(command, user_id):
    """자연어 처리 엔진 테스트"""
    click.echo("🔤 자연어 처리 엔진 테스트를 시작합니다...")
    
    async def test_nlp_engine():
        try:
            from src.ai_engine.natural_language import NaturalLanguageProcessor
            from src.config import get_settings
            
            settings = get_settings()
            nlp_processor = NaturalLanguageProcessor(settings)
            
            # NLP 엔진 초기화
            click.echo("⚙️ 자연어 처리 엔진 초기화 중...")
            init_success = await nlp_processor.initialize()
            if not init_success:
                click.echo("❌ 자연어 처리 엔진 초기화 실패")
                return
                
            click.echo("✅ 자연어 처리 엔진 초기화 완료")
            click.echo(f"📝 테스트 명령: {command}")
            click.echo("⏳ 자연어 분석 중...")
            
            # 실제 자연어 명령 파싱
            parsed_result = await nlp_processor.parse_command(
                user_command=command,
                user_id=str(user_id)
            )
            
            click.echo("\n✅ 자연어 처리 완료!")
            click.echo(f"🎯 의도 (Intent): {parsed_result.intent.value}")
            click.echo(f"🔧 필요 도구: {', '.join(parsed_result.requires_tools)}")
            click.echo(f"📊 신뢰도: {parsed_result.confidence}")
            
            if parsed_result.entities:
                click.echo("\n🏷️  추출된 엔티티:")
                for key, value in parsed_result.entities.items():
                    click.echo(f"   {key}: {value}")
            
            if parsed_result.metadata:
                click.echo("\n⚙️  메타데이터:")
                for key, value in parsed_result.metadata.items():
                    if key != "analysis_response":  # 긴 분석 결과는 제외
                        click.echo(f"   {key}: {value}")
                        
            click.echo(f"\n🚨 긴급도: {parsed_result.urgency.value}")
            if parsed_result.clarification_needed:
                click.echo(f"❓ 명확화 필요: {', '.join(parsed_result.clarification_needed)}")
                
        except Exception as e:
            click.echo(f"❌ 자연어 처리 테스트 실패: {e}")
            click.echo("ℹ️  Mock 모드로 대체합니다.")
            # 실패시 기존 Mock 로직 실행
            _run_nlp_mock(command, user_id)
    
    asyncio.run(test_nlp_engine())

def _run_nlp_mock(command, user_id):
    """NLP Mock 결과"""
    click.echo("\n✅ 자연어 처리 완료! (Mock 결과)")
    click.echo(f"🎯 의도 (Intent): task_management")
    click.echo(f"🔧 도구 (Tool): TodoTool")
    click.echo(f"📊 신뢰도: 0.95")
    click.echo("\n🏷️  추출된 엔티티:")
    click.echo(f"   action: add")
    click.echo(f"   task_type: todo")
    click.echo("\n⚙️  매개변수:")
    click.echo(f"   user_id: {user_id}")
    click.echo(f"   command: {command}")


@click.command(name="test-personalization")
@click.option("--user-id", type=int, default=123, help="사용자 ID")
@click.option("--message", default="오늘 할일을 보여줘", help="테스트할 메시지")
def test_personalization(user_id, message):
    """개인화된 응답 시스템 테스트"""
    click.echo("👤 개인화된 응답 시스템 테스트를 시작합니다...")
    
    async def test_personalization_engine():
        try:
            from src.ai_engine.natural_language import NaturalLanguageProcessor
            from src.config import get_settings
            
            settings = get_settings()
            nlp_processor = NaturalLanguageProcessor(settings)
            
            # NLP 엔진 초기화
            click.echo("⚙️ 개인화 엔진 초기화 중...")
            init_success = await nlp_processor.initialize()
            if not init_success:
                click.echo("❌ 개인화 엔진 초기화 실패")
                return
                
            click.echo("✅ 개인화 엔진 초기화 완료")
            click.echo(f"👤 사용자 ID: {user_id}")
            click.echo(f"📝 메시지: {message}")
            click.echo("⏳ 개인화 분석 중...")
            
            # 실제 개인화된 응답 생성
            personalized_response = await nlp_processor.generate_personalized_response(
                user_id=str(user_id),
                message=message,
                context={
                    "user_profile": {"name": f"User_{user_id}", "style": "friendly"},
                    "current_time": "2025-09-05 00:20:00"
                }
            )
            
            click.echo("\n✅ 개인화된 응답 생성 완료!")
            click.echo(f"🤖 개인화된 응답: {personalized_response}")
            
            # 개인화 컨텍스트 정보 표시
            click.echo("\n👤 사용자 컨텍스트:")
            click.echo(f"   이름: User_{user_id}")
            click.echo(f"   스타일: friendly")
            click.echo(f"   메시지: {message}")
                
        except Exception as e:
            click.echo(f"❌ 개인화 테스트 실패: {e}")
            click.echo("ℹ️  Mock 모드로 대체합니다.")
            # 실패시 기존 Mock 로직 실행
            _run_personalization_mock(user_id, message)
    
    asyncio.run(test_personalization_engine())

def _run_personalization_mock(user_id, message):
    """개인화 Mock 결과"""
    click.echo("\n👤 사용자 프로필: (Mock 데이터)")
    click.echo(f"   이름: User_{user_id}")
    click.echo(f"   선호 스타일: friendly")
    click.echo(f"   활동 횟수: 42")
    
    click.echo("\n🤖 개인화된 응답:")
    click.echo(f"   안녕하세요! '{message}'에 대해 도움을 드릴게요. 개인화된 응답 기능이 구현되었습니다.")


# 테스트 명령어들을 리스트로 export
testing_commands = [
    test_config,
    test_discord,
    test_logs,
    test_old_parsing,
    test_ai,
    test_nlp,
    test_personalization
]
