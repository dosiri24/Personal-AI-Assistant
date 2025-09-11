"""
Discord Bot 메인 통합 클래스
"""

import asyncio
import discord
from discord.ext import commands
from typing import Optional, Callable, Any, Dict
from collections import deque
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger
from src.config import Settings

# 기존 컴포넌트들 (호환성을 위해)
try:
    from ..parser import MessageParser
    from ..router import MessageRouter
    from ..message_queue import MessageQueue
    from ..session import SessionManager
except ImportError:
    # 개발 중 가져오기 오류 방지
    MessageParser = None
    MessageRouter = None
    MessageQueue = None
    SessionManager = None

# 모듈화된 컴포넌트들
from .types import BotConfig, BotState, create_bot_config_from_settings
from .events import BotEventHandlers
from .slash_commands import SlashCommands
from .ai_handler import AIMessageHandler
from .manager import ServerManager
from .background import BackgroundTasks


class DiscordBot:
    """
    Personal AI Assistant Discord Bot (모듈화된 버전)
    
    Discord 서버와 연결하여 사용자의 자연어 명령을 받고,
    백엔드 AI 시스템과 통신하여 응답을 제공합니다.
    """
    
    def __init__(self, settings: Settings):
        """
        Discord Bot 초기화
        
        Args:
            settings: 애플리케이션 설정 객체
        """
        self.settings = settings
        self.logger = get_discord_logger()
        
        # 봇 설정 생성
        self.config = create_bot_config_from_settings(settings)
        self.state = BotState()
        
        # Discord 인텐트 설정
        intents = discord.Intents.default()
        intents.message_content = True  # 메시지 내용 읽기 권한
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.guild_reactions = True
        
        # Bot 클라이언트 생성
        self.bot = commands.Bot(
            command_prefix=self.config.command_prefix,
            intents=intents,
            case_insensitive=self.config.case_insensitive,
            help_command=None  # 기본 도움말 비활성화
        )
        
        # 호환성을 위한 속성들
        self.allowed_users = self.config.authorized_users
        self.admin_users = self.config.admin_users
        self.is_running = False
        
        # 기존 시스템 (호환성을 위해)
        self.message_parser = MessageParser() if MessageParser else None
        self.message_router = MessageRouter() if MessageRouter else None
        self.message_queue = MessageQueue() if MessageQueue else None
        self.session_manager = SessionManager() if SessionManager else None
        
        # 백그라운드 작업 관리
        self._reminder_task: Optional[asyncio.Task] = None
        self._proactive_task: Optional[asyncio.Task] = None
        
        # 중복 응답 방지용 최근 메시지 캐시
        self._recent_message_ids = deque(maxlen=2000)
        
        # 모듈화된 컴포넌트들 초기화
        self._init_components()
        
        self.logger.info("Discord Bot 초기화 완료 (모듈화된 버전)")
    
    def _init_components(self):
        """모듈화된 컴포넌트들 초기화"""
        try:
            # 이벤트 핸들러 설정
            self.event_handlers = BotEventHandlers(self)
            
            # 슬래시 명령어 설정
            self.slash_commands = SlashCommands(self)
            
            # AI 메시지 핸들러 설정
            self.ai_message_handler = AIMessageHandler(self)
            
            # 서버 관리자 설정
            self.server_manager = ServerManager(self)
            
            # 백그라운드 작업 관리자 설정
            self.background_tasks = BackgroundTasks(self)
            
            self.logger.info("모든 모듈화된 컴포넌트 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"컴포넌트 초기화 중 오류: {e}")
            raise
    
    async def start(self, token: str = None):
        """봇 시작"""
        try:
            if token is None:
                token = self.config.token
            
            if not token:
                raise ValueError("Discord 토큰이 필요합니다")
            
            self.logger.info("Discord Bot 시작 중...")
            await self.bot.start(token)
            
        except Exception as e:
            self.logger.error(f"Discord Bot 시작 실패: {e}")
            raise
    
    async def stop(self):
        """봇 중지"""
        try:
            self.logger.info("Discord Bot 중지 중...")
            
            # 백그라운드 작업 중지
            if hasattr(self, 'background_tasks'):
                await self.background_tasks.stop_all_tasks()
            
            # 봇 연결 종료
            if self.bot and not self.bot.is_closed():
                await self.bot.close()
            
            self.is_running = False
            self.logger.info("Discord Bot 중지 완료")
            
        except Exception as e:
            self.logger.error(f"Discord Bot 중지 중 오류: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """봇 상태 반환"""
        if hasattr(self, 'server_manager'):
            return self.server_manager.get_status()
        else:
            # 기본 상태 정보
            return {
                'is_running': self.is_running,
                'guild_count': len(self.bot.guilds) if self.bot.guilds else 0,
                'latency': round(self.bot.latency * 1000) if self.bot.latency else 0
            }
    
    # 호환성을 위한 메서드들
    def _parse_user_ids(self, user_ids_str: str) -> set[int]:
        """사용자 ID 파싱 (호환성)"""
        from .types import parse_user_ids
        return parse_user_ids(user_ids_str)
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """사용자 권한 확인 (호환성)"""
        from .types import is_authorized_user
        return is_authorized_user(user_id, self.config)
    
    def _is_admin_user(self, user_id: int) -> bool:
        """관리자 권한 확인 (호환성)"""
        from .types import is_admin_user
        return is_admin_user(user_id, self.config)
    
    async def _handle_ai_message(self, message: discord.Message):
        """AI 메시지 처리 (호환성)"""
        if hasattr(self, 'ai_message_handler'):
            await self.ai_message_handler.handle_ai_message(message)
        else:
            # 기본 응답
            await message.reply("AI 시스템이 초기화되지 않았습니다.")
    
    async def _shutdown_server_gracefully(self):
        """서버 안전 종료 (호환성)"""
        if hasattr(self, 'server_manager'):
            await self.server_manager.shutdown_gracefully()
        else:
            await self.stop()
    
    async def _reminder_loop(self):
        """리마인더 루프 (호환성)"""
        if hasattr(self, 'background_tasks'):
            await self.background_tasks._reminder_loop()
    
    async def _proactive_todo_loop(self):
        """프로액티브 Todo 루프 (호환성)"""
        if hasattr(self, 'background_tasks'):
            await self.background_tasks._proactive_todo_loop()
    
    # 기존 메서드들을 위한 호환성 wrapper들
    def _setup_event_handlers(self):
        """이벤트 핸들러 설정 (호환성 - 이미 __init__에서 처리됨)"""
        pass
    
    def _setup_slash_commands(self):
        """슬래시 명령어 설정 (호환성 - 이미 __init__에서 처리됨)"""
        pass
