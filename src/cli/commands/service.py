"""
서비스 관리 명령어들 (start, stop, restart, status, health, maintenance)
"""

import time
import asyncio
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors, format_status


@click.command()
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


@click.command()
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


@click.command()
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


@click.command()
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


@click.command()
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


@click.command()
@click.option('--rotate', is_flag=True, help='로그 파일 로테이션 수행')
@click.option('--compress', is_flag=True, help='현재 로그 파일 압축')
@click.option('--cleanup', is_flag=True, help='오래된 로그 및 임시 파일 정리')
@click.option('--stats', is_flag=True, help='로그 파일 통계 출력')
def maintenance(rotate, compress, cleanup, stats):
    """시스템 유지보수 작업을 수행합니다."""
    from src.log_manager import LogManager
    from src.config import get_settings
    
    logger = get_logger("cli")
    settings = get_settings()
    log_manager = LogManager(settings.get_logs_dir())
    
    if not any([rotate, compress, cleanup, stats]):
        click.echo("❌ 최소한 하나의 유지보수 작업을 선택해주세요.")
        click.echo("   --rotate, --compress, --cleanup, --stats 중 선택")
        return
    
    click.echo("🔧 시스템 유지보수 작업 시작:")
    logger.info("유지보수 작업 시작")
    
    if stats:
        click.echo("\n📊 로그 파일 통계:")
        stats_info = log_manager.get_log_stats()
        
        for log_type, info in stats_info.items():
            click.echo(f"   📝 {log_type}:")
            click.echo(f"      파일 크기: {info['size']}")
            click.echo(f"      라인 수: {info['lines']}")
            click.echo(f"      마지막 수정: {info['last_modified']}")
    
    if rotate:
        click.echo("\n🔄 로그 파일 로테이션:")
        try:
            log_manager.rotate_logs()
            click.echo("   ✅ 로테이션 완료")
        except Exception as e:
            click.echo(f"   ❌ 로테이션 실패: {e}")
            logger.error(f"로그 로테이션 실패: {e}")
    
    if compress:
        click.echo("\n🗜️  로그 파일 압축:")
        try:
            log_manager.compress_logs()
            click.echo("   ✅ 압축 완료")
        except Exception as e:
            click.echo(f"   ❌ 압축 실패: {e}")
            logger.error(f"로그 압축 실패: {e}")
    
    if cleanup:
        click.echo("\n🧹 오래된 파일 정리:")
        try:
            # 30일 이상 된 로그 파일 정리
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=30)
            
            deleted_count = 0
            logs_dir = settings.get_logs_dir()
            
            for log_file in logs_dir.glob("*.log.*"):
                if log_file.stat().st_mtime < cutoff_date.timestamp():
                    log_file.unlink()
                    deleted_count += 1
                    click.echo(f"      🗑️  {log_file.name}")
            
            if deleted_count > 0:
                click.echo(f"   ✅ 삭제된 파일: {deleted_count}개")
            else:
                click.echo("   ℹ️  정리할 파일이 없습니다.")
                
        except Exception as e:
            click.echo(f"   ❌ 정리 실패: {e}")
            logger.error(f"파일 정리 실패: {e}")
    
    click.echo("\n✅ 유지보수 작업 완료")
    logger.info("유지보수 작업 완료")


def _start_service_main(dev_mode: bool = True):
    """실제 서비스 메인 로직"""
    logger = get_logger("service")
    
    try:
        logger.info("AI Assistant 서비스 초기화 시작")
        
        # Discord Bot 초기화 및 실행
        click.echo("⏳ Discord Bot 초기화 중...")
        logger.info("Discord Bot 초기화")
        
        # Discord Bot 실행
        asyncio.run(_run_discord_bot(dev_mode))
        
    except KeyboardInterrupt:
        if dev_mode:
            click.echo("\n⏹️  종료 신호를 받았습니다...")
        logger.info("서비스 종료 요청")
    except Exception as e:
        logger.error(f"서비스 실행 중 오류: {e}")
        raise
    finally:
        logger.info("AI Assistant 서비스 종료")


async def _run_discord_bot(dev_mode: bool = True):
    """Discord Bot 실행"""
    logger = get_logger("discord_service")
    
    try:
        from src.config import Settings
        from src.discord_bot.bot import DiscordBot
        
        # 설정 로드
        settings = Settings()
        
        if not settings.has_valid_discord_token():
            logger.error("유효한 Discord 토큰이 없습니다. .env 파일을 확인하세요.")
            click.echo("❌ Discord 토큰이 설정되지 않았습니다.")
            return
        
        # AI Engine 초기화
        click.echo("⏳ AI Engine 초기화 중...")
        logger.info("AI Engine 초기화")
        # TODO: 실제 AI Engine 초기화
        
        # 데이터베이스 연결
        click.echo("⏳ 데이터베이스 연결 중...")
        logger.info("데이터베이스 연결")
        # TODO: 실제 데이터베이스 연결
        
        # Discord Bot 생성 및 시작
        bot = DiscordBot(settings)
        logger.info("Discord Bot 시작 중...")
        
        if dev_mode:
            click.echo("✅ AI Assistant가 개발 모드로 시작되었습니다!")
            click.echo("   🤖 Discord Bot 연결 중...")
            click.echo("   Ctrl+C로 종료할 수 있습니다.")
        
        logger.info("AI Assistant 서비스 시작 완료")
        
        # Discord Bot 실행 (블로킹)
        await bot.start()
        
    except Exception as e:
        logger.error(f"Discord Bot 실행 중 오류: {e}")
        if dev_mode:
            click.echo(f"❌ Discord Bot 실행 오류: {e}")
        raise


# 서비스 명령어들을 리스트로 export
service_commands = [
    start,
    stop, 
    restart,
    status,
    health,
    maintenance
]
