"""
Discord Bot 핵심 클래스

Discord.py를 사용하여 Discord 서버와 연결하고
사용자의 메시지를 처리하는 봇을 구현합니다.
"""

import asyncio
import discord
from discord.ext import commands
from typing import Optional, Callable, Any
from collections import deque
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands
from .ai_handler import get_ai_handler
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger
from src.config import Settings

# Discord Bot 컴포넌트 가져오기 (지연 로딩 방지)
try:
    from .parser import MessageParser
    from .router import MessageRouter
except ImportError:
    # 개발 중 가져오기 오류 방지
    MessageParser = None
    MessageRouter = None
    MessageParser = None
    MessageRouter = None

# Apple Notes 통합을 위한 간단한 헬퍼 함수들
import subprocess
import re


class DiscordBot:
    """
    Personal AI Assistant Discord Bot
    
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
        
        # Discord 인텐트 설정
        intents = discord.Intents.default()
        intents.message_content = True  # 메시지 내용 읽기 권한
        intents.guilds = True
        intents.guild_messages = True
        intents.dm_messages = True
        
        # Bot 클라이언트 생성
        self.bot = commands.Bot(
            command_prefix='!',
            intents=intents,
            help_command=None  # 기본 도움말 비활성화
        )
        
        # 허용된 사용자 ID 목록 파싱
        self.allowed_users = self._parse_user_ids(settings.allowed_user_ids)
        self.admin_users = self._parse_user_ids(settings.admin_user_ids)
        
        # 봇 상태
        self.is_running = False
        self.message_handler: Optional[Callable] = None
        
        # 새로운 메시지 처리 시스템 (Phase 2 Step 2.3 업데이트)
        self.message_parser = MessageParser() if MessageParser else None
        self.message_router = MessageRouter() if MessageRouter else None
        
        # 메시지 큐 시스템 (Phase 2 Step 2.3)
        from .message_queue import MessageQueue
        self.message_queue = MessageQueue()
        
        # 세션 관리 시스템 (Phase 2 Step 2.4)
        from .session import SessionManager
        self.session_manager = SessionManager()
        
        # 이벤트 핸들러 등록
        self._setup_event_handlers()

        self.logger.info("Discord Bot 초기화 완료 (Phase 2 Step 2.4 - 대화 세션 관리 포함)")
        
        # 중복 응답 방지용 최근 메시지 캐시
        self._recent_message_ids = deque(maxlen=2000)
        self._recent_message_set = set()
    
    def _parse_user_ids(self, user_ids_str: str) -> set[int]:
        """
        쉼표로 구분된 사용자 ID 문자열을 파싱
        
        Args:
            user_ids_str: 쉼표로 구분된 사용자 ID 문자열
            
        Returns:
            사용자 ID 정수 집합
        """
        if not user_ids_str.strip():
            return set()
        
        user_ids = set()
        for user_id in user_ids_str.split(','):
            try:
                user_ids.add(int(user_id.strip()))
            except ValueError:
                self.logger.warning(f"잘못된 사용자 ID 형식: {user_id}")
        
        return user_ids
    
    def _setup_event_handlers(self):
        """Discord Bot 이벤트 핸들러 설정"""
        
        @self.bot.event
        async def on_ready():
            """봇이 Discord에 연결되었을 때 호출"""
            self.logger.info(f"Discord Bot 연결 완료: {self.bot.user}")
            if self.bot.user:
                self.logger.info(f"Bot ID: {self.bot.user.id}")
            self.logger.info(f"연결된 서버 수: {len(self.bot.guilds)}")
            
            # 봇 상태 설정
            activity = discord.Activity(
                type=discord.ActivityType.listening,
                name="앙미니 | 명령을 기다리는 중"
            )
            await self.bot.change_presence(activity=activity)

            # 서버(길드) 별 닉네임을 'ai어드바이저'로 고정 (권한 필요)
            try:
                for guild in self.bot.guilds:
                    try:
                        me = guild.me
                        if me and me.nick != "앙미니":
                            await me.edit(nick="앙미니")
                            self.logger.info(f"길드 닉네임 설정: {guild.name} → 앙미니")
                    except Exception as e:
                        self.logger.warning(f"길드 닉네임 설정 실패({guild.name}): {e}")
            except Exception as e:
                self.logger.warning(f"닉네임 일괄 설정 중 오류: {e}")

            # 가능하면 계정 사용자명도 'ai어드바이저'로 설정 (디엠 표시용, 제한/쿨다운 가능)
            try:
                if self.bot.user and self.bot.user.name != "앙미니":
                    await self.bot.user.edit(username="앙미니")
                    self.logger.info("봇 사용자명 변경: 앙미니")
            except Exception as e:
                self.logger.warning(f"봇 사용자명 변경 실패(권한/쿨다운 가능): {e}")
            
            self.is_running = True
            self.logger.info("Discord Bot 준비 완료")
        
        @self.bot.event
        async def on_disconnect():
            """봇이 Discord에서 연결 해제되었을 때 호출"""
            self.logger.warning("Discord Bot 연결 해제됨")
            self.is_running = False
        
        @self.bot.event
        async def on_resumed():
            """봇이 Discord에 재연결되었을 때 호출"""
            self.logger.info("Discord Bot 재연결됨")
            self.is_running = True
        
        @self.bot.event
        async def on_error(event, *args, **kwargs):
            """봇에서 에러가 발생했을 때 호출"""
            self.logger.error(f"Discord Bot 에러 발생: {event}", exc_info=True)
        
        @self.bot.event
        async def on_message(message):
            """메시지가 수신되었을 때 호출"""
            # 봇 자신의 메시지는 무시
            if message.author == self.bot.user:
                return
            
            # 프로세스 간 중복 방지 (DB 기반): 이미 처리한 Discord 메시지면 무시
            try:
                # SessionManager는 __init__에서 초기화됨
                inserted = await self.session_manager.try_mark_discord_message_processed(message.id)
                if not inserted:
                    return
            except Exception:
                # DB 접근 오류인 경우에만 로컬 캐시로 폴백
                try:
                    if message.id in self._recent_message_set:
                        return
                    self._recent_message_set.add(message.id)
                    self._recent_message_ids.append(message.id)
                    while len(self._recent_message_set) > self._recent_message_ids.maxlen:
                        oldest = self._recent_message_ids.popleft()
                        self._recent_message_set.discard(oldest)
                except Exception:
                    pass
            
            # 동일 메시지 중복 처리 방지 (디스코드 이벤트 중복/재전송 대비)
            try:
                if message.id in self._recent_message_set:
                    return
                self._recent_message_set.add(message.id)
                self._recent_message_ids.append(message.id)
                # 데크가 가득 차면 가장 오래된 항목 제거
                while len(self._recent_message_set) > self._recent_message_ids.maxlen:
                    oldest = self._recent_message_ids.popleft()
                    self._recent_message_set.discard(oldest)
            except Exception:
                # 캐시 오류는 무시하고 계속 진행
                pass
            
            # 사용자 권한 확인
            self.logger.info(f"권한 확인: 사용자 {message.author} (ID: {message.author.id})")
            self.logger.info(f"허용된 사용자: {self.allowed_users}")
            self.logger.info(f"관리자 사용자: {self.admin_users}")
            
            if not self._is_authorized_user(message.author.id):
                self.logger.warning(f"권한 없는 사용자의 메시지: {message.author} ({message.author.id})")
                await message.reply("❌ 이 봇을 사용할 권한이 없습니다.")
                return
            
            # 메시지 로깅
            self.logger.info(f"메시지 수신: {message.author} -> {message.content}")
            
            # DM인지 서버 메시지인지 확인
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user and self.bot.user in message.mentions
            
            self.logger.info(f"메시지 타입 확인: is_dm={is_dm}, is_mentioned={is_mentioned}")
            self.logger.info(f"채널 타입: {type(message.channel)}")
            
            # 모든 메시지를 AI가 처리하도록 변경 (DM, 멘션, 서버 메시지 모두)
            self.logger.info("AI 메시지 처리 시작")
            await self._handle_ai_message(message)
            
            # 명령어 처리
            await self.bot.process_commands(message)
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """
        사용자가 봇 사용 권한이 있는지 확인
        
        Args:
            user_id: Discord 사용자 ID
            
        Returns:
            권한 여부
        """
        # 허용된 사용자 목록이 비어있으면 모든 사용자 허용
        if not self.allowed_users:
            return True
        
        return user_id in self.allowed_users or user_id in self.admin_users
    
    def _is_admin_user(self, user_id: int) -> bool:
        """
        사용자가 관리자 권한이 있는지 확인
        
        Args:
            user_id: Discord 사용자 ID
            
        Returns:
            관리자 권한 여부
        """
        return user_id in self.admin_users
    
    async def _handle_ai_message(self, message: discord.Message):
        """
        AI가 처리해야 할 메시지 핸들링 (Phase 2 Step 2.4 업데이트)
        
        Args:
            message: Discord 메시지 객체
        """
        try:
            self.logger.info(f"AI 메시지 처리 시작: {message.author} -> {message.content}")
            
            # 빈 메시지 처리
            content = message.content.strip()
            if self.bot.user and self.bot.user in message.mentions:
                content = content.replace(f'<@{self.bot.user.id}>', '').strip()
            
            if not content:
                await message.reply("안녕하세요! 무엇을 도와드릴까요?")
                return
            
            # 타이핑 표시 시작
            async with message.channel.typing():
                self.logger.info(f"세션 관리 시작: {message.author.id}")
                
                # 세션 조회/생성 (Phase 2 Step 2.4)
                session = await self.session_manager.get_or_create_session(
                    user_id=message.author.id,
                    user_name=str(message.author),
                    channel_id=message.channel.id,
                    channel_name=str(message.channel)
                )
                
                # 대화 턴 추가
                turn_id = await self.session_manager.add_conversation_turn(
                    user_id=message.author.id,
                    user_message=content,
                    metadata={
                        "discord_message_id": message.id,
                        "guild_id": message.guild.id if message.guild else None
                    }
                )
                
                self.logger.info(f"세션 생성 완료: {session.session_id}, 턴: {turn_id}")
                
                # AI Handler를 통한 직접 메시지 처리 (메시지 큐 사용 안함)
                try:
                    self.logger.info("AI Handler 호출 시작")
                    ai_handler = get_ai_handler()
                    # 대화 컨텍스트 활용을 위해 SessionManager 주입 (없으면 생성된 핸들러는 빈 컨텍스트로 진행)
                    try:
                        ai_handler.session_manager = self.session_manager  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    self.logger.info(f"AI Handler 상태: {await ai_handler.get_status()}")
                    
                    ai_response = await ai_handler.process_message(
                        content, 
                        str(message.author.id), 
                        str(message.channel.id)
                    )
                    
                    self.logger.info(f"AI 응답 받음: {ai_response.content[:100]}...")
                    
                    # 1) 비서 메시지 전송
                    await message.reply(ai_response.content)
                    # 2) 시스템 안내(실행 검증) 전송
                    system_notice = getattr(ai_response, "system_notice", None)
                    if isinstance(system_notice, str) and system_notice.strip():
                        try:
                            await message.reply(f"ℹ️ {system_notice}")
                        except Exception:
                            pass
                    
                    # 세션에 AI 응답 저장
                    await self.session_manager.update_conversation_turn(
                        turn_id=turn_id,
                        bot_response=ai_response.content
                    )
                    
                    self.logger.info(f"AI 응답 완료: {message.author.id}")
                    
                except Exception as ai_error:
                    self.logger.error(f"AI 처리 실패: {ai_error}", exc_info=True)
                    await message.reply("AI 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
                
                self.logger.info(f"메시지 처리 완료 (세션: {session.session_id}, 턴: {turn_id})")
        
        except Exception as e:
            self.logger.error(f"메시지 처리 중 오류: {e}", exc_info=True)
            await message.reply("❌ 메시지 처리 중 오류가 발생했습니다.")
    
    async def _send_response(self, message: discord.Message, response):
        """
        응답 메시지 전송
        
        Args:
            message: 원본 Discord 메시지
            response: ResponseMessage 객체 또는 문자열
        """
        try:
            # ResponseMessage 객체인 경우
            if hasattr(response, 'content'):
                if response.reply:
                    if response.embed:
                        await message.reply(content=response.content, embed=response.embed)
                    else:
                        await message.reply(content=response.content)
                else:
                    if response.embed:
                        await message.channel.send(content=response.content, embed=response.embed)
                    else:
                        await message.channel.send(content=response.content)
            else:
                # 문자열인 경우 (하위 호환성)
                await message.reply(str(response))
                
        except Exception as e:
            self.logger.error(f"응답 전송 중 오류: {e}", exc_info=True)
            await message.reply("❌ 응답 전송 중 오류가 발생했습니다.")
    
    def set_message_handler(self, handler: Callable):
        """
        외부 메시지 핸들러 설정
        
        Args:
            handler: 메시지를 처리할 비동기 함수
        """
        self.message_handler = handler
        self.logger.info("메시지 핸들러 설정됨")
    
    async def start(self, token: Optional[str] = None):
        """
        Discord Bot 시작
        """
        if not self.settings.discord_bot_token:
            raise ValueError("Discord Bot 토큰이 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        try:
            self.logger.info("Discord Bot 시작 중...")
            
            # 메시지 큐 시작 (Phase 2 Step 2.3)
            await self.message_queue.start()
            
            # 세션 관리 시작 (Phase 2 Step 2.4)
            await self.session_manager.start()
            
            await self.bot.start(self.settings.discord_bot_token)
        except discord.LoginFailure:
            self.logger.error("Discord Bot 로그인 실패: 토큰을 확인해주세요")
            raise
        except Exception as e:
            self.logger.error(f"Discord Bot 시작 실패: {e}", exc_info=True)
            raise

    async def stop(self):
        """
        Discord Bot 중지
        """
        self.is_running = False
        
        try:
            self.logger.info("Discord Bot 중지 중...")
            
            # 메시지 큐 중지 (Phase 2 Step 2.3)
            await self.message_queue.stop()
            
            # 세션 관리 중지 (Phase 2 Step 2.4)
            await self.session_manager.stop()
            
            await self.bot.close()
            self.logger.info("Discord Bot 중지 완료")
        except Exception as e:
            self.logger.error(f"Discord Bot 중지 중 오류: {e}", exc_info=True)

    def get_status(self) -> dict[str, Any]:
        """
        Discord Bot 상태 정보 반환 (Phase 2 Step 2.2 업데이트)
        
        Returns:
            상태 정보 딕셔너리
        """
        base_status = {
            "is_running": self.is_running,
            "is_connected": not self.bot.is_closed() if hasattr(self, 'bot') else False,
            "user": str(self.bot.user) if self.bot.user else None,
            "user_id": self.bot.user.id if self.bot.user else None,
            "guild_count": len(self.bot.guilds) if hasattr(self.bot, 'guilds') else 0,
            "allowed_users_count": len(self.allowed_users),
            "admin_users_count": len(self.admin_users),
            "latency": round(self.bot.latency * 1000, 2) if hasattr(self.bot, 'latency') else None
        }
        
        # 단순화된 메시지 처리 시스템 상태 추가
        if hasattr(self, 'message_parser') and self.message_parser:
            parser_stats = self.message_parser.get_parser_stats()
            base_status.update({
                "message_system": {
                    "parser_type": parser_stats["parser_type"],
                    "supported_contexts": parser_stats["supported_contexts"],
                    "message_types": parser_stats["supported_message_types"],
                    "natural_language_processing": parser_stats["natural_language_processing"]
                }
            })
        
        if hasattr(self, 'message_router') and self.message_router:
            base_status.update({
                "routing_system": {
                    "router_type": "simplified",
                    "cli_integration": "enabled",
                    "natural_language_processing": "delegated_to_llm"
                }
            })
        
        return base_status


async def setup_basic_commands(bot_instance: DiscordBot):
    """
    기본 Discord 명령어 설정
    
    Args:
        bot_instance: DiscordBot 인스턴스
    """
    bot = bot_instance.bot
    logger = bot_instance.logger
    
    @bot.command(name='help', aliases=['도움말'])
    async def help_command(ctx):
        """도움말 명령어"""
        embed = discord.Embed(
            title="🤖 Personal AI Assistant 도움말",
            description="AI 비서와 자연어로 대화하세요!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📝 사용 방법",
            value="• DM으로 직접 메시지를 보내세요\n• 서버에서 봇을 멘션하고 메시지를 보내세요\n• 자연어로 명령하면 AI가 이해하고 처리합니다",
            inline=False
        )
        
        embed.add_field(
            name="🎯 명령어",
            value="• `!help` 또는 `!도움말` - 이 도움말 보기\n• `!status` 또는 `!상태` - 봇 상태 확인\n• `!ping` - 응답 속도 확인",
            inline=False
        )
        
        embed.add_field(
            name="💡 예시",
            value="• \"내일 오후 3시에 회의 일정 추가해줘\"\n• \"이번 주 할일 목록 보여줘\"\n• \"AI 관련 최신 뉴스 찾아줘\"",
            inline=False
        )
        
        embed.set_footer(text="Personal AI Assistant v2.1 - Phase 2")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='status', aliases=['상태'])
    async def status_command(ctx):
        """봇 상태 확인 명령어"""
        status = bot_instance.get_status()
        
        embed = discord.Embed(
            title="🤖 봇 상태",
            color=0x00ff00 if status['is_running'] else 0xff0000
        )
        
        embed.add_field(
            name="연결 상태",
            value="🟢 온라인" if status['is_connected'] else "🔴 오프라인",
            inline=True
        )
        
        if status['latency']:
            embed.add_field(
                name="응답 속도",
                value=f"{status['latency']}ms",
                inline=True
            )
        
        embed.add_field(
            name="서버 수",
            value=str(status['guild_count']),
            inline=True
        )
        
        embed.add_field(
            name="허용된 사용자",
            value=str(status['allowed_users_count']) + "명",
            inline=True
        )
        
        if status['user']:
            embed.set_footer(text=f"봇 계정: {status['user']}")
        
        await ctx.send(embed=embed)
    
    @bot.command(name='ping')
    async def ping_command(ctx):
        """Ping 명령어"""
        latency = round(bot.latency * 1000, 2)
        await ctx.send(f"🏓 Pong! 응답 속도: {latency}ms")
    
    logger.info("기본 Discord 명령어 설정 완료")
