"""
Discord Bot 이벤트 핸들러
"""

import asyncio
import discord
from typing import TYPE_CHECKING, Optional
from datetime import datetime

if TYPE_CHECKING:
    from ..bot import DiscordBot

from .types import BotStatus, MessageContext
from ..ai_handler import get_ai_handler


class BotEventHandlers:
    """Discord Bot 이벤트 핸들러 클래스"""
    
    def __init__(self, bot_instance: 'DiscordBot'):
        self.bot_instance = bot_instance
        self.bot = bot_instance.bot
        self.logger = bot_instance.logger
        self.settings = bot_instance.settings
        self.config = bot_instance.config
        
        # 이벤트 핸들러 설정
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """모든 이벤트 핸들러 등록"""
        
        @self.bot.event
        async def on_ready():
            """봇이 Discord에 연결되었을 때 호출"""
            await self._handle_ready()
        
        @self.bot.event
        async def on_disconnect():
            """봇이 Discord에서 연결 해제되었을 때 호출"""
            await self._handle_disconnect()
        
        @self.bot.event
        async def on_resumed():
            """봇이 Discord에 재연결되었을 때 호출"""
            await self._handle_resumed()
        
        @self.bot.event
        async def on_error(event, *args, **kwargs):
            """Discord 이벤트 처리 중 오류 발생 시 호출"""
            await self._handle_error(event, *args, **kwargs)
        
        @self.bot.event
        async def on_message(message):
            """메시지 수신 시 호출"""
            await self._handle_message(message)
    
    async def _handle_ready(self):
        """봇 연결 완료 처리"""
        self.logger.info(f"Discord Bot 연결 완료: {self.bot.user}")
        if self.bot.user:
            self.logger.info(f"Bot ID: {self.bot.user.id}")
        self.logger.info(f"연결된 서버 수: {len(self.bot.guilds)}")
        
        # 봇 상태 업데이트
        self.bot_instance.state.status = BotStatus.READY
        self.bot_instance.state.start_time = datetime.now().isoformat()
        self.bot_instance.state.connected_guilds = len(self.bot.guilds)
        
        # 봇 활동 상태 설정
        await self._set_bot_activity()
        
        # 닉네임 설정
        await self._setup_nicknames()
        
        # 슬래시 명령어 동기화
        await self._sync_slash_commands()
        
        # 상태 업데이트
        self.bot_instance.is_running = True
        self.bot_instance.state.status = BotStatus.RUNNING
        
        # 백그라운드 작업 시작
        await self._start_background_tasks()
        
        self.logger.info("Discord Bot 준비 완료")
    
    async def _set_bot_activity(self):
        """봇 활동 상태 설정"""
        try:
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name="앙미니 | 명령을 기다리는 중"
            )
            await self.bot.change_presence(activity=activity)
        except Exception as e:
            self.logger.warning(f"봇 활동 상태 설정 실패: {e}")
    
    async def _setup_nicknames(self):
        """봇 닉네임 설정"""
        try:
            # 서버별 닉네임 설정
            for guild in self.bot.guilds:
                try:
                    me = guild.me
                    if me and me.nick != "앙미니":
                        await me.edit(nick="앙미니")
                        self.logger.info(f"길드 닉네임 설정: {guild.name} → 앙미니")
                except Exception as e:
                    self.logger.warning(f"길드 닉네임 설정 실패({guild.name}): {e}")
            
            # 봇 사용자명 설정 (제한/쿨다운 가능)
            if self.bot.user and self.bot.user.name != "앙미니":
                try:
                    await self.bot.user.edit(username="앙미니")
                    self.logger.info("봇 사용자명 변경: 앙미니")
                except Exception as e:
                    self.logger.warning(f"봇 사용자명 변경 실패(권한/쿨다운 가능): {e}")
                    
        except Exception as e:
            self.logger.warning(f"닉네임 설정 중 오류: {e}")
    
    async def _sync_slash_commands(self):
        """슬래시 명령어 동기화"""
        try:
            synced = await self.bot.tree.sync()
            self.logger.info(f"슬래시 명령어 {len(synced)}개 동기화 완료")
        except Exception as e:
            self.logger.error(f"슬래시 명령어 동기화 실패: {e}")
    
    async def _start_background_tasks(self):
        """백그라운드 작업 시작"""
        try:
            # 정각 리마인더 루프 시작
            if (self.bot_instance._reminder_task is None and 
                getattr(self.settings, 'reminder_enabled', False)):
                self.bot_instance._reminder_task = asyncio.create_task(
                    self.bot_instance._reminder_loop()
                )
                self.logger.info("정각 리마인더 루프 시작")
        except Exception as e:
            self.logger.warning(f"리마인더 루프 시작 실패: {e}")
        
        try:
            # 프로액티브 Todo 루프 시작
            if (self.bot_instance._proactive_task is None and 
                getattr(self.settings, 'proactive_enabled', False)):
                self.bot_instance._proactive_task = asyncio.create_task(
                    self.bot_instance._proactive_todo_loop()
                )
                self.logger.info("프로액티브 Todo 선톡 루프 시작")
        except Exception as e:
            self.logger.warning(f"프로액티브 선톡 루프 시작 실패: {e}")
    
    async def _handle_disconnect(self):
        """연결 해제 처리"""
        self.logger.warning("Discord Bot 연결 해제됨")
        self.bot_instance.state.status = BotStatus.DISCONNECTED
    
    async def _handle_resumed(self):
        """재연결 처리"""
        self.logger.info("Discord Bot 재연결됨")
        self.bot_instance.state.status = BotStatus.RUNNING
    
    async def _handle_error(self, event, *args, **kwargs):
        """에러 처리"""
        self.logger.error(f"Discord 이벤트 '{event}' 처리 중 오류 발생")
        self.logger.error(f"Args: {args}")
        self.logger.error(f"Kwargs: {kwargs}")
        self.bot_instance.state.increment_errors()
    
    async def _handle_message(self, message):
        """메시지 처리"""
        # 봇 자신의 메시지는 무시
        if message.author == self.bot.user:
            return
        
        # 메시지 카운트 증가
        self.bot_instance.state.increment_messages()
        self.bot_instance.state.last_activity = datetime.now().isoformat()
        
        # 메시지 컨텍스트 생성
        context = self._create_message_context(message)
        
        # 권한 확인
        if not context.is_authorized:
            self.logger.warning(f"비인가 사용자 메시지: {context.username} ({context.user_id})")
            return
        
        # AI 메시지 처리로 전달
        await self.bot_instance._handle_ai_message(message)
    
    def _create_message_context(self, message) -> MessageContext:
        """메시지 컨텍스트 생성"""
        from .types import is_authorized_user, is_admin_user
        
        user_id = message.author.id
        
        return MessageContext(
            user_id=user_id,
            username=message.author.name,
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else None,
            is_dm=isinstance(message.channel, discord.DMChannel),
            is_admin=is_admin_user(user_id, self.config),
            is_authorized=is_authorized_user(user_id, self.config),
            content=message.content,
            raw_message=message
        )
