"""
Apple MCP 서버 프로세스 관리자

옵션적으로 애플리케이션 시작 시 외부 Apple MCP 서버(bun + TypeScript)를
백그라운드로 자동 실행하고 종료 시 정리합니다.
"""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path
from typing import Optional

from ..utils.logger import get_logger
from ..config import Settings


class AppleMCPManager:
    """Apple MCP 서버 생명주기 관리자"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = get_logger("apple_mcp")
        self.server_path = Path(settings.apple_mcp_server_path)
        self.pid_file = settings.get_data_dir() / "apple-mcp.pid"
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
            self.logger.info("Apple MCP 서버가 이미 실행 중입니다")
            return True

        if not self.server_path.exists():
            self.logger.warning(f"Apple MCP 서버 경로를 찾을 수 없습니다: {self.server_path}")
            return False

        # bun 존재 여부는 Popen 실패로 감지
        env = {**os.environ, "PORT": str(self.settings.apple_mcp_port)}
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
            self.logger.info(f"Apple MCP 서버 시작: PID={process.pid}, PORT={self.settings.apple_mcp_port}")
            return True
        except FileNotFoundError:
            self.logger.error("Bun이 설치되어 있지 않습니다. https://bun.sh 에서 설치 후 재시도하세요.")
            return False
        except Exception as e:
            self.logger.error(f"Apple MCP 서버 시작 실패: {e}")
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
            self.logger.warning(f"프로세스 종료 시도 실패: {e}")

        try:
            self.pid_file.unlink(missing_ok=True)
        except Exception:
            pass
        self.logger.info("Apple MCP 서버 중지 처리 완료")
        return True


def autostart_if_configured(settings: Settings) -> Optional[AppleMCPManager]:
    """설정에 따라 자동 시작 수행 후 매니저 반환 (미시작 시 None)"""
    if not getattr(settings, "apple_mcp_autostart", False):
        return None
    manager = AppleMCPManager(settings)
    manager.start_background()
    return manager

