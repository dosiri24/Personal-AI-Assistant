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
    from src.utils.logger import get_logger
    from src.config import Settings
    from src.discord_bot.bot import DiscordBot
    from src.mcp.apple_mcp_manager import autostart_if_configured

    logger = get_logger("root_launcher")

    settings = Settings()
    settings.ensure_directories()

    # Apple MCP 서버 자동 시작 (옵션)
    mcp_manager = autostart_if_configured(settings)

    if not settings.has_valid_discord_token():
        print("❌ Discord 토큰이 설정되지 않았습니다. .env의 DISCORD_BOT_TOKEN을 확인해주세요.")
        return

    bot = DiscordBot(settings)
    try:
        logger.info("Discord Bot 시작")
        await bot.start()
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


def main() -> None:
    _ensure_project_on_path()
    _bootstrap_certs()
    # 단일 인스턴스 보장: PID 파일 잠금
    from src.config import Settings
    settings = Settings()
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

    atexit.register(_cleanup)
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
