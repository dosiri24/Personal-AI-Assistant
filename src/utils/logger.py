"""
로깅 시스템 모듈

Loguru와 Rich를 통합하여 구조화된 로깅 시스템을 제공합니다.
- 로그 레벨별 파일 분리 저장
- Rich 콘솔 출력 지원
- 구조화된 로그 포맷
- 자동 로그 로테이션
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler
import logging


class PersonalAILogger:
    """Personal AI Assistant 전용 로거 클래스"""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        로거 초기화
        
        Args:
            log_dir: 로그 파일을 저장할 디렉토리 (기본: 프로젝트 루트/logs)
        """
        self.console = Console()
        
        # 기본 로그 디렉토리 설정
        if log_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.log_dir = project_root / "logs"
        else:
            self.log_dir = log_dir
            
        # 로그 디렉토리 생성
        self.log_dir.mkdir(exist_ok=True)
        
        # 기존 로거 제거
        logger.remove()
        
        # 로깅 시스템 설정
        self._setup_logging()
    
    def _setup_logging(self):
        """로깅 시스템 설정"""
        
        # 1. 콘솔 출력 (Rich Handler 사용)
        logger.add(
            sink=sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            level="DEBUG",
            colorize=True,
            enqueue=True
        )
        
        # 2. 전체 로그 파일 (모든 레벨)
        logger.add(
            sink=self.log_dir / "personal_ai_assistant.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            enqueue=True
        )
        
        # 3. 에러 로그 파일 (ERROR 이상만)
        logger.add(
            sink=self.log_dir / "errors.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
            level="ERROR",
            rotation="5 MB",
            retention="90 days",
            compression="zip",
            enqueue=True
        )
        
        # 4. Discord Bot 전용 로그
        def discord_filter(record):
            name = record.get("name", "")
            return isinstance(name, str) and "discord" in name.lower()
            
        logger.add(
            sink=self.log_dir / "discord_bot.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=discord_filter,
            level="INFO",
            rotation="5 MB",
            retention="7 days",
            enqueue=True
        )
        
        # 5. AI 엔진 전용 로그
        def ai_engine_filter(record):
            name = record.get("name", "")
            return isinstance(name, str) and "ai_engine" in name.lower()
            
        logger.add(
            sink=self.log_dir / "ai_engine.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            filter=ai_engine_filter,
            level="INFO",
            rotation="10 MB",
            retention="14 days",
            enqueue=True
        )
    
    def get_logger(self, name: str = "personal_ai_assistant"):
        """
        특정 모듈용 로거 반환
        
        Args:
            name: 로거 이름 (모듈명)
            
        Returns:
            설정된 loguru 로거
        """
        return logger.bind(name=name)
    
    def test_logging(self):
        """로깅 시스템 테스트"""
        test_logger = self.get_logger("test")
        
        test_logger.debug("디버그 메시지 테스트")
        test_logger.info("정보 메시지 테스트")
        test_logger.warning("경고 메시지 테스트")
        test_logger.error("에러 메시지 테스트")
        test_logger.critical("심각한 에러 메시지 테스트")
        
        # Discord Bot 로그 테스트
        discord_logger = self.get_logger("discord_bot")
        discord_logger.info("Discord Bot 연결 테스트")
        
        # AI Engine 로그 테스트
        ai_logger = self.get_logger("ai_engine")
        ai_logger.info("AI 엔진 초기화 테스트")


# 전역 로거 인스턴스
_logger_instance: Optional[PersonalAILogger] = None


def setup_logging(log_dir: Optional[Path] = None) -> PersonalAILogger:
    """
    전역 로깅 시스템 초기화
    
    Args:
        log_dir: 로그 디렉토리
        
    Returns:
        PersonalAILogger 인스턴스
    """
    global _logger_instance
    _logger_instance = PersonalAILogger(log_dir)
    return _logger_instance


def get_logger(name: str = "personal_ai_assistant"):
    """
    로거 인스턴스 반환
    
    Args:
        name: 로거 이름
        
    Returns:
        loguru 로거
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = setup_logging()
    
    return _logger_instance.get_logger(name)


# 편의를 위한 별칭
def get_discord_logger():
    """Discord Bot 전용 로거"""
    return get_logger("discord_bot")


def get_ai_logger():
    """AI Engine 전용 로거"""
    return get_logger("ai_engine")


def get_mcp_logger():
    """MCP 도구 전용 로거"""
    return get_logger("mcp_tools")


def get_memory_logger():
    """장기기억 시스템 전용 로거"""
    return get_logger("memory_system")


# 모듈 임포트시 자동 초기화
if __name__ != "__main__":
    setup_logging()
