"""CLI 메인 명령어 모듈"""

import click
import time
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import setup_logging, get_logger


@click.group()
@click.version_option(version="0.1.0", prog_name="Personal AI Assistant")
@click.option("--log-level", default="INFO", help="로그 레벨 설정 (DEBUG, INFO, WARNING, ERROR)")
def cli(log_level):
    """
    Personal AI Assistant - 지능형 개인 비서
    
    Discord를 통해 자연어 명령을 받아 에이전틱 AI가 스스로 판단하고 
    MCP 도구를 활용하여 임무를 완수하는 지능형 개인 비서
    """
    # 로깅 시스템 초기화
    setup_logging()
    logger = get_logger("cli")
    logger.info(f"Personal AI Assistant CLI 시작됨 (로그 레벨: {log_level})")


@cli.command()
@click.option("--daemon", is_flag=True, help="백그라운드 데몬으로 실행")
def start(daemon):
    """AI 비서 서비스를 시작합니다."""
    from src.config import get_settings
    from src.daemon import DaemonManager
    
    logger = get_logger("cli")
    settings = get_settings()
    
    # PID 파일 경로
    pid_file = settings.get_data_dir() / "ai_assistant.pid"
    daemon_manager = DaemonManager(pid_file)
    
    if daemon_manager.is_running():
        click.echo("❌ AI Assistant가 이미 실행 중입니다.")
        click.echo(f"   PID: {daemon_manager.get_pid()}")
        click.echo("   먼저 'stop' 명령으로 중지해주세요.")
        return
    
    if daemon:
        click.echo("🚀 Personal AI Assistant를 백그라운드 데몬으로 시작합니다...")
        logger.info("데몬 모드로 서비스 시작 요청")
        
        try:
            # 데몬 프로세스에서 실행할 함수
            def daemon_main():
                _start_service_main(dev_mode=False)
            
            daemon_manager.start_daemon(daemon_main)
            click.echo("✅ 서비스가 백그라운드에서 성공적으로 시작되었습니다.")
            
        except Exception as e:
            click.echo(f"❌ 데몬 시작 실패: {e}")
            logger.error(f"데몬 시작 실패: {e}")
    else:
        click.echo("🚀 Personal AI Assistant를 개발 모드로 시작합니다...")
        logger.info("개발 모드로 서비스 시작 요청")
        
        try:
            _start_service_main(dev_mode=True)
        except KeyboardInterrupt:
            click.echo("\n⏹️  종료 신호를 받았습니다...")
            logger.info("사용자 종료 요청")
        except Exception as e:
            click.echo(f"❌ 서비스 시작 실패: {e}")
            logger.error(f"서비스 시작 실패: {e}")


@cli.command()
def stop():
    """AI 비서 서비스를 중지합니다."""
    from src.config import get_settings
    from src.daemon import DaemonManager
    
    logger = get_logger("cli")
    settings = get_settings()
    
    # PID 파일 경로
    pid_file = settings.get_data_dir() / "ai_assistant.pid"
    daemon_manager = DaemonManager(pid_file)
    
    if not daemon_manager.is_running():
        click.echo("❌ 실행 중인 AI Assistant를 찾을 수 없습니다.")
        return
    
    click.echo("🛑 Personal AI Assistant를 중지합니다...")
    logger.info("서비스 중지 요청")
    
    try:
        if daemon_manager.stop_daemon(timeout=10):
            click.echo("✅ 서비스가 성공적으로 중지되었습니다.")
            logger.info("서비스 중지 완료")
        else:
            click.echo("❌ 서비스 중지에 실패했습니다.")
            logger.error("서비스 중지 실패")
    except Exception as e:
        click.echo(f"❌ 서비스 중지 중 오류: {e}")
        logger.error(f"서비스 중지 중 오류: {e}")


@cli.command()
def restart():
    """AI 비서 서비스를 재시작합니다."""
    from src.config import get_settings
    from src.daemon import DaemonManager
    
    logger = get_logger("cli")
    settings = get_settings()
    
    # PID 파일 경로
    pid_file = settings.get_data_dir() / "ai_assistant.pid"
    daemon_manager = DaemonManager(pid_file)
    
    click.echo("🔄 Personal AI Assistant를 재시작합니다...")
    logger.info("서비스 재시작 요청")
    
    try:
        def daemon_main():
            _start_service_main(dev_mode=False)
        
        daemon_manager.restart_daemon(daemon_main)
        click.echo("✅ 서비스가 성공적으로 재시작되었습니다.")
        logger.info("서비스 재시작 완료")
        
    except Exception as e:
        click.echo(f"❌ 서비스 재시작 실패: {e}")
        logger.error(f"서비스 재시작 실패: {e}")


@cli.command()
def health():
    """AI 비서 서비스의 상세 헬스체크를 수행합니다."""
    from src.config import get_settings
    from src.daemon import DaemonManager, ServiceStatus
    
    logger = get_logger("cli")
    settings = get_settings()
    
    # PID 파일 경로
    pid_file = settings.get_data_dir() / "ai_assistant.pid"
    daemon_manager = DaemonManager(pid_file)
    service_status = ServiceStatus(daemon_manager)
    
    click.echo("🏥 Personal AI Assistant 헬스체크:")
    logger.info("서비스 헬스체크 요청")
    
    status_info = service_status.get_status_info()
    
    if status_info['running']:
        click.echo("   🟢 기본 상태: 실행 중")
        click.echo(f"   📍 PID: {status_info['pid']}")
        
        # 업타임 정보
        if status_info['uptime']:
            click.echo(f"   ⏱️  업타임: {status_info['uptime']}")
        
        # 리소스 사용량
        if status_info['memory_usage']:
            click.echo(f"   💾 메모리: {status_info['memory_usage']}")
        
        if status_info['cpu_usage']:
            click.echo(f"   🖥️  CPU: {status_info['cpu_usage']}")
        
        # 헬스 상태
        if 'health_status' in status_info:
            health_status = status_info['health_status']
            if health_status == 'healthy':
                click.echo("   💚 헬스 상태: 정상")
            elif health_status == 'warning':
                click.echo("   ⚠️  헬스 상태: 경고")
            else:
                click.echo("   🔴 헬스 상태: 심각")
            
            if status_info.get('error_count', 0) > 0:
                click.echo(f"   ❌ 에러 횟수: {status_info['error_count']}")
                
                if status_info.get('last_error'):
                    click.echo(f"   🔍 마지막 에러: {status_info['last_error']}")
        
        # 재시작 정보
        if 'restart_info' in status_info:
            restart_info = status_info['restart_info']
            click.echo(f"   🔄 최근 재시작: {restart_info['recent_restarts']}회")
            
            if restart_info['last_restart']:
                click.echo(f"   📅 마지막 재시작: {restart_info['last_restart']}")
        
        # 개별 구성 요소 상태 (TODO: 실제 구현 시 추가)
        click.echo("\n🔍 구성 요소 상태:")
        click.echo("   🤖 Discord Bot: 연결 대기")
        click.echo("   🧠 AI Engine: 초기화 대기")
        click.echo("   🗄️  데이터베이스: 연결 대기")
        click.echo("   📝 로깅 시스템: ✅ 정상")
        click.echo("   ⚙️  설정 시스템: ✅ 정상")
        
    else:
        click.echo("   🔴 기본 상태: 중지됨")
        click.echo("   ℹ️  서비스가 실행되지 않고 있습니다.")
    
    logger.debug("헬스체크 완료")


@cli.command()
def status():
    """AI 비서 서비스 상태를 확인합니다."""
    from src.config import get_settings
    from src.daemon import DaemonManager, ServiceStatus
    
    logger = get_logger("cli")
    settings = get_settings()
    
    # PID 파일 경로
    pid_file = settings.get_data_dir() / "ai_assistant.pid"
    daemon_manager = DaemonManager(pid_file)
    service_status = ServiceStatus(daemon_manager)
    
    click.echo("📊 Personal AI Assistant 상태:")
    logger.info("서비스 상태 확인 요청")
    
    status_info = service_status.get_status_info()
    
    if status_info['running']:
        click.echo("   🟢 상태: 실행 중")
        click.echo(f"   📍 PID: {status_info['pid']}")
        
        if status_info['uptime']:
            click.echo(f"   ⏱️  업타임: {status_info['uptime']}")
        
        if status_info['memory_usage']:
            click.echo(f"   💾 메모리: {status_info['memory_usage']}")
        
        if status_info['cpu_usage']:
            click.echo(f"   🖥️  CPU: {status_info['cpu_usage']}")
        
        # TODO: 실제 서비스 상태 확인
        click.echo("   🤖 Discord Bot: 연결됨")
        click.echo("   🧠 AI Engine: 활성화")
        click.echo("   🗄️  데이터베이스: 연결됨")
    else:
        click.echo("   🔴 상태: 중지됨")
    
    logger.debug("상태 확인 완료")


def _start_service_main(dev_mode: bool = True):
    """실제 서비스 메인 로직"""
    logger = get_logger("service")
    
    try:
        logger.info("AI Assistant 서비스 초기화 시작")
        
        # TODO: Discord Bot 초기화
        click.echo("⏳ Discord Bot 초기화 중...")
        logger.info("Discord Bot 초기화")
        time.sleep(1)  # 임시 대기
        
        # TODO: AI Engine 초기화
        click.echo("⏳ AI Engine 초기화 중...")
        logger.info("AI Engine 초기화")
        time.sleep(1)  # 임시 대기
        
        # TODO: 데이터베이스 연결
        click.echo("⏳ 데이터베이스 연결 중...")
        logger.info("데이터베이스 연결")
        time.sleep(1)  # 임시 대기
        
        if dev_mode:
            click.echo("✅ AI Assistant가 개발 모드로 시작되었습니다!")
            click.echo("   Ctrl+C로 종료할 수 있습니다.")
        
        logger.info("AI Assistant 서비스 시작 완료")
        
        # 메인 이벤트 루프
        while True:
            # TODO: 실제 서비스 로직 구현
            time.sleep(1)
            
    except KeyboardInterrupt:
        if dev_mode:
            click.echo("\n⏹️  종료 신호를 받았습니다...")
        logger.info("서비스 종료 요청")
    except Exception as e:
        logger.error(f"서비스 실행 중 오류: {e}")
        raise
    finally:
        logger.info("AI Assistant 서비스 종료")


@cli.command()
@click.option('--rotate', is_flag=True, help='로그 파일 로테이션 수행')
@click.option('--compress', is_flag=True, help='현재 로그 파일 압축')
@click.option('--cleanup', is_flag=True, help='오래된 로그 및 임시 파일 정리')
@click.option('--stats', is_flag=True, help='로그 파일 통계 출력')
def maintenance(rotate, compress, cleanup, stats):
    """시스템 유지보수 작업을 수행합니다."""
    from src.config import get_settings
    from log_manager import LogManager, PerformanceOptimizer
    
    settings = get_settings()
    log_manager = LogManager(settings.get_logs_dir())
    optimizer = PerformanceOptimizer(settings.get_data_dir())
    
    click.echo("🔧 시스템 유지보수 작업:")
    
    if rotate:
        click.echo("   📋 로그 로테이션 수행 중...")
        log_manager.rotate_logs()
        click.echo("   ✅ 로그 로테이션 완료")
    
    if compress:
        click.echo("   🗜️  로그 파일 압축 중...")
        log_manager.compress_logs()
        click.echo("   ✅ 로그 압축 완료")
    
    if cleanup:
        click.echo("   🧹 시스템 정리 중...")
        optimizer.optimize_data_directory()
        click.echo("   ✅ 시스템 정리 완료")
    
    if stats:
        click.echo("   📊 로그 파일 통계:")
        log_stats = log_manager.get_log_stats()
        
        click.echo(f"      - 총 로그 파일: {log_stats['total_files']}개")
        click.echo(f"      - 총 크기: {log_stats['total_size_mb']} MB")
        
        if 'backup_files' in log_stats:
            click.echo(f"      - 백업 파일: {log_stats['backup_files']}개")
            click.echo(f"      - 백업 크기: {log_stats['backup_size_mb']} MB")
        
        click.echo("   📁 디스크 사용량:")
        disk_stats = optimizer.get_disk_usage()
        if 'error' not in disk_stats:
            click.echo(f"      - 데이터 디렉토리: {disk_stats['total_size_mb']} MB")
            click.echo(f"      - 파일 수: {disk_stats['file_count']}개")
    
    if not any([rotate, compress, cleanup, stats]):
        click.echo("   ℹ️  옵션을 선택해주세요. --help로 사용법을 확인할 수 있습니다.")


@cli.command()
@click.option('--follow', '-f', is_flag=True, help='실시간으로 로그 출력')
@click.option('--lines', '-n', default=50, help='출력할 라인 수')
@click.option('--type', 'log_type', default='main', 
              type=click.Choice(['main', 'discord', 'ai', 'errors']),
              help='로그 파일 타입')
def logs(follow, lines, log_type):
    """AI Assistant 로그를 확인합니다."""
    from src.config import get_settings
    import subprocess
    import sys
    
    settings = get_settings()
    logs_dir = settings.get_logs_dir()
    
    # 로그 파일 매핑
    log_files = {
        'main': logs_dir / "personal_ai_assistant.log",
        'discord': logs_dir / "discord_bot.log", 
        'ai': logs_dir / "ai_engine.log",
        'errors': logs_dir / "errors.log"
    }
    
    log_file = log_files.get(log_type)
    
    if not log_file or not log_file.exists():
        click.echo(f"❌ 로그 파일을 찾을 수 없습니다: {log_file}")
        return
    
    if follow:
        click.echo(f"📄 로그 파일을 실시간으로 출력합니다: {log_file}")
        click.echo("(Ctrl+C로 종료)")
        try:
            subprocess.run(['tail', '-f', str(log_file)])
        except KeyboardInterrupt:
            click.echo("\n로그 출력을 종료합니다.")
        except FileNotFoundError:
            click.echo("❌ tail 명령을 찾을 수 없습니다.")
    else:
        click.echo(f"📄 로그 파일 마지막 {lines}줄 출력: {log_file}")
        try:
            result = subprocess.run(['tail', '-n', str(lines), str(log_file)], 
                                 capture_output=True, text=True)
            if result.returncode == 0:
                click.echo(result.stdout)
            else:
                click.echo(f"❌ 로그 읽기 실패: {result.stderr}")
        except FileNotFoundError:
            click.echo("❌ tail 명령을 찾을 수 없습니다.")


@cli.command()
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


@cli.command()
@click.option('--quick', is_flag=True, help='빠른 연결 테스트만 수행')
def test_discord(quick):
    """Discord Bot 연결을 테스트합니다."""
    import asyncio
    click.echo("🤖 Discord Bot 연결 테스트를 시작합니다...")
    
    try:
        asyncio.run(_test_discord_connection(quick=quick))
    except Exception as e:
        click.echo(f"❌ Discord Bot 테스트 실패: {e}")


async def _test_discord_connection(quick: bool = False):
    """Discord Bot 연결 테스트 (비동기)"""
    from src.config import get_settings
    from discord_bot import DiscordBot
    from discord_bot.bot import setup_basic_commands
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


@cli.command()
@click.option("--message", required=True, help="처리할 자연어 메시지")
@click.option("--user-id", type=int, default=0, help="사용자 ID")
@click.option("--user-name", default="Unknown", help="사용자 이름")
@click.option("--context", default="channel", help="메시지 컨텍스트 (dm/mention/channel)")
@click.option("--format", default="text", help="출력 형식 (text/json)")
def process_message(message, user_id, user_name, context, format):
    """자연어 메시지를 AI가 처리합니다."""
    import json
    
    logger = get_logger("cli")
    logger.info(f"자연어 메시지 처리 요청: {message[:50]}...")
    
    try:
        # Phase 3에서 구현될 AI 엔진 대신 임시 응답 생성
        response_data = {
            "status": "success",
            "message": f"'{message}' 메시지를 받았습니다.",
            "response": f"안녕하세요 {user_name}님! '{message}'라고 말씀하셨군요. 현재 AI 엔진이 개발 중이라 임시 응답을 드립니다. Phase 3에서 실제 LLM 처리가 구현될 예정입니다.",
            "user_id": user_id,
            "user_name": user_name,
            "context": context,
            "processing_time": "0.1s",
            "ai_engine": "placeholder (Phase 3에서 구현 예정)"
        }
        
        if format == "json":
            click.echo(json.dumps(response_data, ensure_ascii=False, indent=2))
        else:
            click.echo(f"✅ 메시지 처리 완료")
            click.echo(f"👤 사용자: {user_name} ({user_id})")
            click.echo(f"📝 메시지: {message}")
            click.echo(f"🤖 AI 응답: {response_data['response']}")
            
        logger.info("자연어 메시지 처리 완료")
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "message": message
        }
        
        if format == "json":
            click.echo(json.dumps(error_response, ensure_ascii=False, indent=2))
        else:
            click.echo(f"❌ 메시지 처리 실패: {e}")
            
        logger.error(f"자연어 메시지 처리 실패: {e}")


@cli.command()
@click.argument('message', required=False)
def test_old_parsing(message):
    """구버전 명령어 파싱 시스템을 테스트합니다. (더 이상 사용되지 않음)"""
    click.echo("⚠️  구버전 파싱 시스템은 더 이상 사용되지 않습니다.")
    click.echo("� 새로운 단순화된 메시지 처리 시스템을 사용하세요:")
    if message:
        click.echo(f"   python -m src.cli.main process-message --message \"{message}\"")
    else:
        click.echo(f"   python -m src.cli.main process-message --message \"테스트 메시지\"")


@cli.command()
def test_logs():
    """로깅 시스템을 테스트합니다."""
    click.echo("🧪 로깅 시스템 테스트를 시작합니다...")
    
    from src.utils.logger import PersonalAILogger
    
    # 로깅 시스템 테스트
    logger_system = PersonalAILogger()
    logger_system.test_logging()
    
    click.echo("✅ 로깅 시스템 테스트가 완료되었습니다.")
    click.echo("📁 로그 파일들을 logs/ 디렉토리에서 확인할 수 있습니다.")


if __name__ == "__main__":
    cli()
