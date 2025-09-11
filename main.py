"""
Top-level launcher for Personal AI Assistant.

Run this file from the project root to start the Discord-based agent server.

Usage:
  python3 main.py

The launcher sets up certificates for HTTPS (Discord) and starts the bot in
foreground mode. Press Ctrl+C to stop.
"""

from __future__ import annotations

import asyncio
import os
import sys
import atexit
import signal
from pathlib import Path


def _ensure_project_on_path() -> None:
    root = Path(__file__).resolve().parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def _bootstrap_certs() -> None:
    """Ensure a valid CA bundle is available for HTTPS (Discord, APIs)."""
    try:
        import certifi  # type: ignore

        ca = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca)
    except Exception:
        # If certifi is not available, proceed; system certs may be enough.
        pass


async def _run() -> None:
    from src.config import Settings
    from src.utils.logger import get_logger
    from src.discord_bot.bot import DiscordBot
    from src.mcp.apple.apple_client import autostart_if_configured
    from src.mcp.mcp_integration import get_unified_mcp_system
    import os

    logger = get_logger("root_launcher")

    settings = Settings()
    settings.ensure_directories()

    # Apple MCP 서버 자동 시작 (옵션)
    mcp_manager = autostart_if_configured(settings)

    # MCP 통합 시스템 초기화
    try:
        mcp_system = get_unified_mcp_system()
        await mcp_system.initialize()
        logger.info("MCP 통합 시스템 초기화 완료")
    except Exception as e:
        logger.error(f"MCP 시스템 초기화 실패: {e}")
        logger.info("MCP 시스템 없이 계속 진행")

    if not settings.has_valid_discord_token():
        print("❌ Discord 토큰이 설정되지 않았습니다. .env의 DISCORD_BOT_TOKEN을 확인해주세요.")
        return

    bot = DiscordBot(settings)
    
    # 종료 신호 파일 정리
    shutdown_files = ["/tmp/ai_assistant_shutdown_requested", "/tmp/ai_assistant_force_shutdown"]
    for file_path in shutdown_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    
    try:
        logger.info("Discord Bot 시작")
        
        # 비동기적으로 봇 시작과 종료 신호 감지 실행
        bot_task = asyncio.create_task(bot.start())
        shutdown_monitor_task = asyncio.create_task(_monitor_shutdown_signal(logger))
        
        # 둘 중 하나가 완료될 때까지 대기
        done, pending = await asyncio.wait(
            [bot_task, shutdown_monitor_task], 
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 아직 실행 중인 태스크들 취소
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        # 완료된 태스크의 예외 확인
        for task in done:
            try:
                task.result()
            except Exception as e:
                if not isinstance(e, (KeyboardInterrupt, SystemExit)):
                    logger.error(f"태스크 실행 중 오류: {e}")
                    raise
                    
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt 수신, 종료 절차 진행")
    except Exception as e:
        logger.error(f"Discord Bot 실행 오류: {e}")
        raise
    finally:
        try:
            await bot.stop()
        except Exception:
            pass
        # Apple MCP 자동 시작한 경우 정리
        try:
            if mcp_manager:
                mcp_manager.stop_background()
        except Exception:
            pass
        
        # 종료 신호 파일 정리
        for file_path in shutdown_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass


async def _monitor_shutdown_signal(logger):
    """종료 신호 파일을 모니터링"""
    import os
    
    shutdown_file = "/tmp/ai_assistant_shutdown_requested"
    force_shutdown_file = "/tmp/ai_assistant_force_shutdown"
    
    while True:
        try:
            if os.path.exists(force_shutdown_file):
                logger.info("강제 종료 신호 감지됨")
                raise SystemExit(1)
            elif os.path.exists(shutdown_file):
                logger.info("정상 종료 신호 감지됨")
                raise SystemExit(0)
            
            await asyncio.sleep(0.5)  # 0.5초마다 확인
            
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            logger.warning(f"종료 신호 모니터링 중 오류: {e}")
            await asyncio.sleep(1)


def main() -> None:
    _ensure_project_on_path()
    _bootstrap_certs()
    
    # 단일 인스턴스 보장: PID 파일 잠금
    from src.config import Settings
    from src.utils.logger import get_logger
    
    settings = Settings()
    logger = get_logger("main")
    pid_path = settings.get_data_dir() / "discord_bot.pid"
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    # 기존 PID 존재 시 생존 확인
    if pid_path.exists():
        try:
            old_pid = int(pid_path.read_text().strip())
            if old_pid > 0:
                try:
                    os.kill(old_pid, 0)
                except ProcessLookupError:
                    # 죽은 PID → 계속 진행
                    pass
                else:
                    print(f"❌ 이미 실행 중인 인스턴스가 있습니다 (PID: {old_pid}).")
                    print("   기존 프로세스를 종료하거나, 해당 PID 파일을 삭제한 뒤 다시 시도하세요.")
                    return
        except Exception:
            # 손상된 파일 → 덮어쓰기 진행
            pass

    # 현재 PID 기록 및 종료 시 정리
    try:
        pid_path.write_text(str(os.getpid()))
    except Exception:
        pass

    def _cleanup():
        try:
            if pid_path.exists():
                pid_path.unlink()
        except Exception:
            pass

    def _signal_handler(signum, frame):
        """신호 처리기"""
        logger.info(f"신호 {signum} 수신됨. 서버를 정상 종료합니다.")
        _cleanup()
        sys.exit(0)

    # 신호 처리기 등록
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    atexit.register(_cleanup)
    
    try:
        logger.info("Personal AI Assistant 서버 시작")
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt 수신. 서버를 종료합니다.")
    except SystemExit:
        logger.info("시스템 종료 요청. 서버를 종료합니다.")
    except Exception as e:
        logger.error(f"서버 실행 중 예상치 못한 오류: {e}")
    finally:
        logger.info("Personal AI Assistant 서버 종료 완료")


if __name__ == "__main__":
    main()
