"""Discord Bot 모듈화 완료

원본 1,272줄 파일이 다음과 같이 모듈화되었습니다:
- bot/types.py: 기본 타입 및 설정
- bot/events.py: Discord 이벤트 핸들러
- bot/slash_commands.py: 슬래시 명령어 처리  
- bot/ai_handler.py: AI 메시지 처리
- bot/manager.py: 서버 관리 및 상태 모니터링
- bot/background.py: 백그라운드 작업 관리
- bot/core.py: 메인 통합 Discord Bot
- bot/__init__.py: 통합 관리자

기존 코드와의 호환성을 위해 모든 클래스와 함수를 재내보냅니다.
"""

import warnings
from typing import Optional

# 새로운 모듈화 시스템에서 모든 필요한 항목 가져오기
from .bot import (
    # 기본 타입
    BotStatus,
    UserRole,
    BotConfig,
    BotState,
    MessageContext,
    
    # 기능 모듈들
    BotEventHandlers,
    SlashCommands,
    AIMessageHandler,
    ServerManager,
    BackgroundTasks,
    
    # 메인 클래스
    DiscordBot,
    BotManager,
    
    # 유틸리티 함수들
    create_bot_config_from_settings,
    parse_user_ids,
    get_user_role,
    is_authorized_user,
    is_admin_user,
    
    # 편의 함수들
    get_bot_manager,
    create_discord_bot,
    get_discord_bot
)

from loguru import logger

# 호환성을 위한 경고 메시지 (운영 환경에서는 제거 가능)
warnings.warn(
    "bot.py가 모듈화되었습니다. "
    "향후 직접적으로 'from .bot import DiscordBot'를 사용하는 것을 권장합니다.",
    DeprecationWarning,
    stacklevel=2
)

# 모든 공개 항목 내보내기
__all__ = [
    # 기본 타입
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
