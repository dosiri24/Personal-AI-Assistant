"""
Discord Bot 모듈화 시스템
원본 bot.py (1,272줄)을 기능별로 분리하여 관리성 향상

모듈 구조:
- types.py: 기본 타입 및 설정
- events.py: Discord 이벤트 핸들러
- slash_commands.py: 슬래시 명령어 처리  
- ai_handler.py: AI 메시지 처리
- manager.py: 서버 관리 및 상태 모니터링
- background.py: 백그라운드 작업 관리
- core.py: 메인 통합 Discord Bot

통합 관리자를 통해 모든 기능에 일관된 접근 제공
"""

import warnings
from typing import Optional

# 핵심 타입 및 설정
from .types import (
    BotStatus,
    UserRole,
    BotConfig,
    BotState,
    MessageContext,
    create_bot_config_from_settings,
    parse_user_ids,
    get_user_role,
    is_authorized_user,
    is_admin_user
)

# 기능별 모듈들
from .events import BotEventHandlers
from .slash_commands import SlashCommands
from .ai_handler import AIMessageHandler
from .manager import ServerManager
from .background import BackgroundTasks

# 메인 통합 봇 클래스
from .core import DiscordBot

from loguru import logger

# 기존 코드와의 호환성을 위한 경고 메시지
warnings.warn(
    "bot.py가 모듈화되었습니다. "
    "향후 직접적으로 'from .bot import DiscordBot'를 사용하는 것을 권장합니다.",
    DeprecationWarning,
    stacklevel=2
)


class BotManager:
    """Discord Bot 통합 관리자"""
    
    def __init__(self, settings=None):
        self.settings = settings
        self.bot_instance: Optional[DiscordBot] = None
        self.initialized = False
    
    def create_bot(self, settings=None) -> DiscordBot:
        """봇 인스턴스 생성"""
        if settings:
            self.settings = settings
        
        if not self.settings:
            raise ValueError("Settings가 필요합니다")
        
        self.bot_instance = DiscordBot(self.settings)
        self.initialized = True
        
        return self.bot_instance
    
    def get_bot(self) -> Optional[DiscordBot]:
        """현재 봇 인스턴스 반환"""
        return self.bot_instance
    
    async def start_bot(self, token: str = None):
        """봇 시작"""
        if not self.bot_instance:
            raise RuntimeError("봇이 초기화되지 않았습니다. create_bot()을 먼저 호출하세요.")
        
        if token:
            await self.bot_instance.start(token)
        else:
            await self.bot_instance.start()
    
    async def stop_bot(self):
        """봇 중지"""
        if self.bot_instance:
            await self.bot_instance.stop()
    
    def get_status(self):
        """봇 상태 조회"""
        if self.bot_instance:
            return self.bot_instance.get_status()
        return {"status": "not_initialized"}


# 편의를 위한 전역 인스턴스
_global_manager: Optional[BotManager] = None


def get_bot_manager() -> BotManager:
    """전역 봇 매니저 인스턴스 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = BotManager()
    return _global_manager


def create_discord_bot(settings) -> DiscordBot:
    """편의 함수: Discord Bot 생성"""
    return get_bot_manager().create_bot(settings)


def get_discord_bot() -> Optional[DiscordBot]:
    """편의 함수: 현재 Discord Bot 인스턴스 반환"""
    return get_bot_manager().get_bot()


# 모든 공개 클래스와 함수 내보내기
__all__ = [
    # 핵심 타입
    'BotStatus',
    'UserRole',
    'BotConfig',
    'BotState',
    'MessageContext',
    
    # 기능 모듈들
    'BotEventHandlers',
    'SlashCommands',
    'AIMessageHandler',
    'ServerManager',
    'BackgroundTasks',
    
    # 메인 클래스
    'DiscordBot',
    'BotManager',
    
    # 유틸리티 함수들
    'create_bot_config_from_settings',
    'parse_user_ids',
    'get_user_role',
    'is_authorized_user',
    'is_admin_user',
    
    # 편의 함수들
    'get_bot_manager',
    'create_discord_bot',
    'get_discord_bot'
]
