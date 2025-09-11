"""
Discord Bot 기본 타입 및 설정
"""

from dataclasses import dataclass
from typing import Optional, Set, Dict, Any
from enum import Enum


class BotStatus(Enum):
    """봇 상태"""
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    DISCONNECTED = "disconnected"
    SHUTTING_DOWN = "shutting_down"
    STOPPED = "stopped"


class UserRole(Enum):
    """사용자 역할"""
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"


@dataclass
class BotConfig:
    """봇 설정"""
    token: str
    authorized_users: Set[int]
    admin_users: Set[int]
    command_prefix: str = "!"
    case_insensitive: bool = True
    intents: Optional[Dict[str, bool]] = None
    
    def __post_init__(self):
        if self.intents is None:
            # 기본 인텐트 설정
            self.intents = {
                'message_content': True,
                'guilds': True,
                'guild_messages': True,
                'direct_messages': True,
                'guild_reactions': True
            }


@dataclass 
class BotState:
    """봇 현재 상태"""
    status: BotStatus = BotStatus.STARTING
    start_time: Optional[str] = None
    last_activity: Optional[str] = None
    message_count: int = 0
    command_count: int = 0
    error_count: int = 0
    connected_guilds: int = 0
    
    def increment_messages(self):
        """메시지 카운트 증가"""
        self.message_count += 1
    
    def increment_commands(self):
        """명령어 카운트 증가"""  
        self.command_count += 1
        
    def increment_errors(self):
        """에러 카운트 증가"""
        self.error_count += 1
        
    def reset_counters(self):
        """카운터 초기화"""
        self.message_count = 0
        self.command_count = 0
        self.error_count = 0


@dataclass
class MessageContext:
    """메시지 처리 컨텍스트"""
    user_id: int
    username: str
    channel_id: int
    guild_id: Optional[int]
    is_dm: bool
    is_admin: bool
    is_authorized: bool
    content: str
    raw_message: Any  # discord.Message 객체


def create_bot_config_from_settings(settings) -> BotConfig:
    """Settings 객체로부터 BotConfig 생성"""
    # authorized_users와 admin_users 파싱
    authorized_users = set()
    admin_users = set()
    
    if hasattr(settings, 'discord_authorized_users') and settings.discord_authorized_users:
        try:
            # 쉼표로 구분된 문자열을 파싱
            user_ids = settings.discord_authorized_users.split(',')
            authorized_users = {int(uid.strip()) for uid in user_ids if uid.strip().isdigit()}
        except (ValueError, AttributeError):
            pass
    
    if hasattr(settings, 'discord_admin_users') and settings.discord_admin_users:
        try:
            # 쉼표로 구분된 문자열을 파싱  
            user_ids = settings.discord_admin_users.split(',')
            admin_users = {int(uid.strip()) for uid in user_ids if uid.strip().isdigit()}
        except (ValueError, AttributeError):
            pass
    
    return BotConfig(
        token=settings.discord_token,
        authorized_users=authorized_users,
        admin_users=admin_users,
        command_prefix=getattr(settings, 'discord_command_prefix', '!'),
        case_insensitive=getattr(settings, 'discord_case_insensitive', True)
    )


# 유틸리티 함수들
def parse_user_ids(user_ids_str: str) -> Set[int]:
    """쉼표로 구분된 사용자 ID 문자열을 파싱"""
    if not user_ids_str:
        return set()
    
    user_ids = set()
    try:
        for uid in user_ids_str.split(','):
            uid = uid.strip()
            if uid.isdigit():
                user_ids.add(int(uid))
    except (ValueError, AttributeError):
        pass
    
    return user_ids


def get_user_role(user_id: int, config: BotConfig) -> UserRole:
    """사용자 역할 확인"""
    if user_id in config.admin_users:
        return UserRole.ADMIN
    elif user_id in config.authorized_users:
        return UserRole.USER
    else:
        return UserRole.GUEST


def is_authorized_user(user_id: int, config: BotConfig) -> bool:
    """사용자 권한 확인"""
    return user_id in config.authorized_users or user_id in config.admin_users


def is_admin_user(user_id: int, config: BotConfig) -> bool:
    """관리자 권한 확인"""
    return user_id in config.admin_users
