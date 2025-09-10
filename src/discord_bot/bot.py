"""
Discord Bot 핵심 클래스

Discord.py를 사용하여 Discord 서버와 연결하고
사용자의 메시지를 처리하는 봇을 구현합니다.
"""

import asyncio
import discord
from discord.ext import commands
from typing import Optional, Callable, Any, Dict
from collections import deque
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from .ai_handler import get_ai_handler

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
        # Reminder task
        self._reminder_task: Optional[asyncio.Task] = None
        # Proactive todo nudge task (every N minutes)
        self._proactive_task: Optional[asyncio.Task] = None
        self._proactive_seen: dict[str, float] = {}
        self._proactive_llm = None  # lightweight LLM provider for proactive nudges
    
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

            # 정각 리마인더 루프 시작
            try:
                if self._reminder_task is None and self.settings.reminder_enabled:
                    self._reminder_task = asyncio.create_task(self._reminder_loop())
                    self.logger.info("정각 리마인더 루프 시작")
            except Exception as e:
                self.logger.warning(f"리마인더 루프 시작 실패: {e}")

            # Proactive todo nudge 루프 시작
            try:
                if self._proactive_task is None and getattr(self.settings, 'proactive_enabled', False):
                    self._proactive_task = asyncio.create_task(self._proactive_todo_loop())
                    self.logger.info("프로액티브 Todo 선톡 루프 시작")
            except Exception as e:
                self.logger.warning(f"프로액티브 선톡 루프 시작 실패: {e}")
        
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
        finally:
            # 리마인더 태스크 취소
            try:
                if self._reminder_task and not self._reminder_task.done():
                    self._reminder_task.cancel()
            except Exception:
                pass
            # 프로액티브 태스크 취소
            try:
                if self._proactive_task and not self._proactive_task.done():
                    self._proactive_task.cancel()
            except Exception:
                pass

    async def _reminder_loop(self):
        """매 정각마다 Notion Todo의 '예정' 상태 중 마감 임박 항목을 확인하여 알림"""
        from zoneinfo import ZoneInfo
        from datetime import datetime, timedelta
        from src.tools.notion.client import NotionClient, NotionError

        # 준비: Discord 대상 사용자(관리자) 식별
        def _get_admin_ids() -> list[int]:
            ids: list[int] = []
            try:
                if self.settings.admin_user_ids:
                    for s in self.settings.admin_user_ids.split(','):
                        s = s.strip()
                        if s:
                            ids.append(int(s))
            except Exception:
                pass
            return ids

        # Notion 클라이언트 준비
        try:
            notion = NotionClient(use_async=True)
        except Exception as e:
            self.logger.warning(f"리마인더용 Notion 클라이언트 초기화 실패: {e}")
            return

        tz = ZoneInfo(self.settings.default_timezone)
        threshold = timedelta(minutes=self.settings.reminder_threshold_minutes)

        while self.is_running:
            try:
                # 다음 정각까지 대기
                now = datetime.now(tz)
                next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                await asyncio.sleep(max(1.0, (next_hour - now).total_seconds()))

                # 실행 시각
                run_at = datetime.now(tz)
                until = run_at + threshold

                db_id = getattr(self.settings, 'notion_todo_database_id', None)
                if not db_id:
                    self.logger.debug("리마인더: Notion Todo DB 미설정, 건너뜀")
                    continue

                # 필터: 상태=예정 AND 마감일 on_or_before until AND on_or_after now
                filter_criteria = {
                    "and": [
                        {"property": "작업상태", "status": {"equals": "예정"}},
                        {"property": "마감일", "date": {"on_or_before": until.isoformat()}},
                        {"property": "마감일", "date": {"on_or_after": run_at.isoformat()}},
                    ]
                }

                try:
                    result = await notion.query_database(
                        database_id=db_id,
                        filter_criteria=filter_criteria,
                        sorts=None,
                        page_size=50,
                    )
                except Exception as e:
                    self.logger.warning(f"리마인더: Notion 쿼리 실패: {e}")
                    continue

                pages = (result or {}).get("results", [])
                if not pages:
                    continue

                # 항목 파싱
                reminders = []
                for page in pages:
                    try:
                        props = page.get("properties", {})
                        title = ""
                        if "작업명" in props and props["작업명"].get("title"):
                            tl = props["작업명"]["title"]
                            if tl and tl[0].get("text"):
                                title = tl[0]["text"]["content"]
                        due_str = None
                        if "마감일" in props and props["마감일"].get("date"):
                            due_str = props["마감일"]["date"].get("start")
                        due_local = None
                        if due_str:
                            try:
                                d = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                                due_local = d.astimezone(tz) if d.tzinfo else d.replace(tzinfo=tz)
                            except Exception:
                                pass
                        url = page.get("url", "")
                        if title and due_local:
                            reminders.append((title, due_local, url))
                    except Exception:
                        continue

                if not reminders:
                    continue

                # 관리자에게 DM 전송
                admin_ids = _get_admin_ids()
                if not admin_ids:
                    self.logger.debug("리마인더: 관리자 ID 없음, 건너뜀")
                    continue

                # 전송 대상: 채널 우선, 없으면 DM (관리자)
                lines = [
                    "⏰ 마감 임박 할 일 확인",
                    f"기준시각: {run_at.strftime('%Y-%m-%d %H:%M %Z')}",
                    ""
                ]
                # 가까운 순 정렬
                reminders.sort(key=lambda x: x[1])
                for title, due_local, url in reminders[:10]:
                    lines.append(f"• {title} (마감: {due_local.strftime('%m-%d %H:%M')})")
                    if url:
                        lines.append(f"  링크: {url}")
                lines.append("\n이 중에 진행하셨나요? 필요하면 업데이트해드릴게요.")
                payload = "\n".join(lines)

                ch_id = getattr(self.settings, 'reminder_channel_id', None)
                sent = False
                if ch_id:
                    try:
                        channel = self.bot.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
                        if channel:
                            await channel.send(payload)
                            sent = True
                    except Exception as e:
                        self.logger.warning(f"리마인더 채널 전송 실패({ch_id}): {e}")

                if not sent:
                    admin_ids = _get_admin_ids()
                    for admin_id in admin_ids:
                        try:
                            user = self.bot.get_user(admin_id) or await self.bot.fetch_user(admin_id)
                            if not user:
                                continue
                            await user.send(payload)
                        except Exception as e:
                            self.logger.warning(f"리마인더 DM 실패({admin_id}): {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"리마인더 루프 오류: {e}")

    async def _proactive_todo_loop(self):
        """매 N분마다 Notion Todo에서 '완료'가 아닌 항목을 가져와 프리엠티브 선톡.

        - 필터: 작업상태 != 완료
        - 정렬: 마감일 오름차순(있으면)
        - 창: 설정의 proactive_window_minutes 내 마감 또는 마감일 없음
        - 메시지: LLM이 간단하게 한국어로 선톡을 작성
        """
        try:
            from zoneinfo import ZoneInfo
            from datetime import datetime, timedelta
            from src.tools.notion.client import NotionClient
            # LLM: lightweight provider 직접 사용 (AI Handler 초기화 회피)
            from src.ai_engine.llm_provider import GeminiProvider, ChatMessage
        except Exception as e:
            self.logger.warning(f"프로액티브 선톡 초기 임포트 실패: {e}")
            return

        tz = ZoneInfo(self.settings.default_timezone)
        interval = max(1, int(getattr(self.settings, 'proactive_interval_minutes', 10)))
        window = timedelta(minutes=int(getattr(self.settings, 'proactive_window_minutes', 360)))

        # Notion 클라이언트 준비
        try:
            notion = NotionClient(use_async=True)
        except Exception as e:
            self.logger.warning(f"프로액티브 선톡용 Notion 클라이언트 초기화 실패: {e}")
            return

        def _get_targets(pages: list[dict]) -> list[tuple[str, Optional[datetime], str, str]]:
            targets: list[tuple[str, Optional[datetime], str, str]] = []
            for page in pages:
                try:
                    pid = page.get("id", "")
                    props = page.get("properties", {})
                    # 제목
                    title = ""
                    if "작업명" in props and props["작업명"].get("title"):
                        tl = props["작업명"]["title"]
                        if tl and tl[0].get("text"):
                            title = tl[0]["text"]["content"]
                    # 마감
                    due_str = None
                    if "마감일" in props and props["마감일"].get("date"):
                        due_str = props["마감일"]["date"].get("start")
                    due_local = None
                    if due_str:
                        try:
                            d = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                            due_local = d.astimezone(tz) if d.tzinfo else d.replace(tzinfo=tz)
                        except Exception:
                            pass
                    url = page.get("url", "")
                    status = None
                    if "작업상태" in props and props["작업상태"].get("status"):
                        status = props["작업상태"]["status"].get("name")
                    if title:
                        targets.append((pid, due_local, title, url))
                except Exception:
                    continue
            return targets

        while self.is_running:
            try:
                await asyncio.sleep(interval * 60)

                db_id = getattr(self.settings, 'notion_todo_database_id', None)
                if not db_id:
                    self.logger.debug("프로액티브: Notion Todo DB 미설정, 건너뜀")
                    continue

                now = datetime.now(tz)
                horizon = now + window

                # 상태 != 완료, 마감일이 없거나 horizon 이전
                filter_criteria = {
                    "and": [
                        {"property": "작업상태", "status": {"does_not_equal": "완료"}},
                        {"or": [
                            {"property": "마감일", "date": {"is_empty": True}},
                            {"property": "마감일", "date": {"on_or_before": horizon.isoformat()}}
                        ]}
                    ]
                }

                try:
                    result = await notion.query_database(
                        database_id=db_id,
                        filter_criteria=filter_criteria,
                        sorts=[{"property": "마감일", "direction": "ascending"}],
                        page_size=50,
                    )
                except Exception as e:
                    self.logger.warning(f"프로액티브: Notion 쿼리 실패: {e}")
                    continue

                pages = (result or {}).get("results", [])
                if not pages:
                    continue

                targets = _get_targets(pages)
                if not targets:
                    continue

                # 중복 방지: 최근 전송한 항목 제외 (3시간 내)
                dedup_targets: list[tuple[str, Optional[datetime], str, str]] = []
                for pid, due_local, title, url in targets:
                    ts = self._proactive_seen.get(pid)
                    if ts and (now.timestamp() - ts) < window.total_seconds():
                        continue
                    dedup_targets.append((pid, due_local, title, url))
                if not dedup_targets:
                    continue

                # 메시지 생성(LLM): 친근한 선톡 톤으로 1~3문장 (경량 LLM 사용)
                prov = self._proactive_llm
                if prov is None:
                    try:
                        from src.config import Settings
                        prov = GeminiProvider(Settings())
                        ok = await prov.initialize()
                        if not ok:
                            prov = None
                        else:
                            self._proactive_llm = prov
                            self.logger.info("프로액티브: 경량 LLM Provider 초기화 완료")
                    except Exception as e:
                        self.logger.warning(f"프로액티브: 경량 LLM Provider 초기화 실패 — {e}")
                        prov = None
                lines = []
                for pid, due_local, title, url in dedup_targets[:10]:
                    when = due_local.strftime('%m-%d %H:%M') if due_local else '마감 미정'
                    # 링크는 넣지 않음 (요청 사항)
                    lines.append(f"• {title} (마감: {when})")
                listing = "\n".join(lines)

                content = None
                if prov and prov.is_available():
                    sys_msg = (
                        "너는 Discord에서 사용자를 도와주는 비서야.\n"
                        "- 아래 '진행 중/예정' 할일 목록을 바탕으로, 친근하게 선제 메시지를 1~3문장으로 작성해.\n"
                        "- 과장/사족 없이 핵심만. 한국어. 이모지 1~2개 허용.\n"
                        "- 링크 언급 금지. 너무 딱딱하지 않게, 부담 낮게 권유.\n"
                    )
                    usr = (
                        f"[기준시각] {now.strftime('%Y-%m-%d %H:%M %Z')}\n"
                        f"[할일 목록]\n{listing}\n\n"
                        "사용자가 부담 없이 빠르게 확인/진행을 결정할 수 있도록 부드럽게 권유해줘."
                    )
                    try:
                        resp = await prov.generate_response([
                            ChatMessage(role='system', content=sys_msg),
                            ChatMessage(role='user', content=usr)
                        ], temperature=0.3)
                        content = (resp.content or "").strip()
                    except Exception as e:
                        self.logger.warning(f"프로액티브: LLM 생성 실패 — {e}")

                if not content:
                    # LLM 실패 시 기본 포맷 (친근, 링크 없음)
                    header = f"미완료 할 일 알림 — {now.strftime('%Y-%m-%d %H:%M')}"
                    intro = "잠깐 체크해 보실 만한 항목들이 있어요:"  # 가벼운 안내
                    content = header + "\n\n" + intro + "\n" + listing

                # 전송: 채널 우선, 없으면 관리자 DM
                sent = False
                ch_id = getattr(self.settings, 'proactive_channel_id', None) or getattr(self.settings, 'reminder_channel_id', None)
                if ch_id:
                    try:
                        channel = self.bot.get_channel(ch_id) or await self.bot.fetch_channel(ch_id)
                        if channel:
                            await channel.send(content)
                            sent = True
                    except Exception as e:
                        self.logger.warning(f"프로액티브 채널 전송 실패({ch_id}): {e}")
                if not sent:
                    # 관리자 DM
                    admins = self._parse_user_ids(self.settings.admin_user_ids)
                    for aid in admins:
                        try:
                            user = self.bot.get_user(aid) or await self.bot.fetch_user(aid)
                            if user:
                                await user.send(content)
                                sent = True
                        except Exception as e:
                            self.logger.warning(f"프로액티브 DM 실패({aid}): {e}")
                # 전송 성공 시, 본 항목들 기록
                if sent:
                    for pid, _, _, _ in dedup_targets:
                        self._proactive_seen[pid] = now.timestamp()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.warning(f"프로액티브 루프 오류: {e}")

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
