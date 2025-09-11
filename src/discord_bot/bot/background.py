"""
Discord Bot 백그라운드 작업 모듈
"""

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, List, Tuple
import discord

if TYPE_CHECKING:
    from ..bot import DiscordBot

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from datetime import timezone as ZoneInfo


class BackgroundTasks:
    """백그라운드 작업 관리 클래스"""
    
    def __init__(self, bot_instance: 'DiscordBot'):
        self.bot_instance = bot_instance
        self.bot = bot_instance.bot
        self.logger = bot_instance.logger
        self.settings = bot_instance.settings
        self.config = bot_instance.config
        
        # 작업 상태 추적
        self._reminder_task: Optional[asyncio.Task] = None
        self._proactive_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start_all_tasks(self):
        """모든 백그라운드 작업 시작"""
        if self._running:
            return
        
        self._running = True
        
        # 정각 리마인더 시작
        if getattr(self.settings, 'reminder_enabled', False):
            await self.start_reminder_loop()
        
        # 프로액티브 Todo 선톡 시작
        if getattr(self.settings, 'proactive_enabled', False):
            await self.start_proactive_loop()
    
    async def stop_all_tasks(self):
        """모든 백그라운드 작업 중지"""
        self._running = False
        
        await self.stop_reminder_loop()
        await self.stop_proactive_loop()
    
    async def start_reminder_loop(self):
        """정각 리마인더 루프 시작"""
        if self._reminder_task is None or self._reminder_task.done():
            self._reminder_task = asyncio.create_task(self._reminder_loop())
            self.logger.info("정각 리마인더 루프 시작")
    
    async def stop_reminder_loop(self):
        """정각 리마인더 루프 중지"""
        if self._reminder_task and not self._reminder_task.done():
            self._reminder_task.cancel()
            try:
                await self._reminder_task
            except asyncio.CancelledError:
                pass
            self.logger.info("정각 리마인더 루프 중지")
    
    async def start_proactive_loop(self):
        """프로액티브 Todo 선톡 루프 시작"""
        if self._proactive_task is None or self._proactive_task.done():
            self._proactive_task = asyncio.create_task(self._proactive_todo_loop())
            self.logger.info("프로액티브 Todo 선톡 루프 시작")
    
    async def stop_proactive_loop(self):
        """프로액티브 Todo 선톡 루프 중지"""
        if self._proactive_task and not self._proactive_task.done():
            self._proactive_task.cancel()
            try:
                await self._proactive_task
            except asyncio.CancelledError:
                pass
            self.logger.info("프로액티브 Todo 선톡 루프 중지")
    
    async def _reminder_loop(self):
        """정각 리마인더 루프"""
        try:
            tz = ZoneInfo(getattr(self.settings, 'default_timezone', 'Asia/Seoul'))
            
            while self._running:
                try:
                    now = datetime.now(tz)
                    
                    # 정각인지 확인 (분이 0인지)
                    if now.minute == 0:
                        await self._send_hourly_reminder(now)
                        
                        # 다음 정각까지 대기 (59분 이상 대기)
                        await asyncio.sleep(3600)  # 1시간 대기
                    else:
                        # 다음 정각까지 대기
                        minutes_to_next_hour = 60 - now.minute
                        seconds_to_next_hour = minutes_to_next_hour * 60 - now.second
                        await asyncio.sleep(seconds_to_next_hour)
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"리마인더 루프 중 오류: {e}")
                    await asyncio.sleep(300)  # 5분 후 재시도
                    
        except asyncio.CancelledError:
            self.logger.info("리마인더 루프가 취소되었습니다")
        except Exception as e:
            self.logger.error(f"리마인더 루프 치명적 오류: {e}")
    
    async def _send_hourly_reminder(self, current_time: datetime):
        """정각 리마인더 전송"""
        try:
            hour = current_time.hour
            
            # 업무 시간에만 리마인더 전송 (9시~18시)
            if not (9 <= hour <= 18):
                return
            
            # 간단한 시간 알림 메시지
            message = f"🕐 {hour}시 정각입니다!"
            
            # 특별한 시간대 메시지
            if hour == 9:
                message += " 좋은 하루 시작하세요! 😊"
            elif hour == 12:
                message += " 점심시간입니다! 🍽️"
            elif hour == 18:
                message += " 수고하셨습니다! 🌅"
            
            # 알림을 받을 채널에 메시지 전송
            await self._send_notification_to_channels(message)
            
        except Exception as e:
            self.logger.error(f"정각 리마인더 전송 중 오류: {e}")
    
    async def _proactive_todo_loop(self):
        """프로액티브 Todo 선톡 루프"""
        try:
            interval = max(1, int(getattr(self.settings, 'proactive_interval_minutes', 10)))
            
            while self._running:
                try:
                    await self._check_and_send_proactive_todos()
                    await asyncio.sleep(interval * 60)  # 인터벌만큼 대기
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"프로액티브 Todo 루프 중 오류: {e}")
                    await asyncio.sleep(300)  # 5분 후 재시도
                    
        except asyncio.CancelledError:
            self.logger.info("프로액티브 Todo 루프가 취소되었습니다")
        except Exception as e:
            self.logger.error(f"프로액티브 Todo 루프 치명적 오류: {e}")
    
    async def _check_and_send_proactive_todos(self):
        """프로액티브 Todo 확인 및 전송"""
        try:
            from src.tools.notion.client import NotionClient
            from src.ai_engine.llm_provider import GeminiProvider, ChatMessage
            
            # Notion 클라이언트 초기화
            notion = NotionClient(use_async=True)
            
            # 미완료 작업들 조회
            incomplete_todos = await self._get_incomplete_todos(notion)
            
            if not incomplete_todos:
                return
            
            # 우선순위가 높은 작업들 선별
            priority_todos = await self._filter_priority_todos(incomplete_todos)
            
            if priority_todos:
                # 프로액티브 메시지 생성
                message = await self._generate_proactive_message(priority_todos)
                
                if message:
                    await self._send_notification_to_channels(message)
            
        except Exception as e:
            self.logger.error(f"프로액티브 Todo 확인 중 오류: {e}")
    
    async def _get_incomplete_todos(self, notion_client) -> List[dict]:
        """미완료 Todo 목록 조회"""
        try:
            # Notion에서 미완료 작업들 조회
            pages = await notion_client.query_database_async(
                database_id=self.settings.notion_todo_database_id,
                filter_conditions={
                    "and": [
                        {
                            "property": "상태",
                            "select": {
                                "does_not_equal": "완료"
                            }
                        }
                    ]
                }
            )
            
            return pages.get('results', [])
            
        except Exception as e:
            self.logger.error(f"미완료 Todo 조회 중 오류: {e}")
            return []
    
    async def _filter_priority_todos(self, todos: List[dict]) -> List[Tuple[str, Optional[datetime], str, str]]:
        """우선순위 Todo 필터링"""
        try:
            tz = ZoneInfo(self.settings.default_timezone)
            window = timedelta(minutes=int(getattr(self.settings, 'proactive_window_minutes', 360)))
            now = datetime.now(tz)
            
            priority_todos = []
            
            for todo in todos:
                try:
                    # 작업 정보 추출
                    title, due_date, url, status = self._extract_todo_info(todo, tz)
                    
                    # 우선순위 판별
                    if self._is_priority_todo(due_date, window, now):
                        priority_todos.append((title, due_date, url, status))
                        
                except Exception as e:
                    self.logger.warning(f"Todo 필터링 중 오류: {e}")
            
            # 마감일 기준으로 정렬
            priority_todos.sort(key=lambda x: x[1] if x[1] else datetime.max.replace(tzinfo=tz))
            
            return priority_todos
            
        except Exception as e:
            self.logger.error(f"우선순위 Todo 필터링 중 오류: {e}")
            return []
    
    def _extract_todo_info(self, todo: dict, tz) -> Tuple[str, Optional[datetime], str, str]:
        """Todo 정보 추출"""
        props = todo.get("properties", {})
        
        # 제목 추출
        title = ""
        if "작업명" in props and props["작업명"].get("title"):
            title_list = props["작업명"]["title"]
            if title_list and title_list[0].get("text"):
                title = title_list[0]["text"]["content"]
        
        # 마감일 추출
        due_date = None
        if "마감일" in props and props["마감일"].get("date"):
            due_str = props["마감일"]["date"].get("start")
            if due_str:
                try:
                    d = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                    due_date = d.astimezone(tz) if d.tzinfo else d.replace(tzinfo=tz)
                except Exception:
                    pass
        
        # URL
        url = todo.get("url", "")
        
        # 상태
        status = ""
        if "상태" in props and props["상태"].get("select"):
            status = props["상태"]["select"].get("name", "")
        
        return title, due_date, url, status
    
    def _is_priority_todo(self, due_date: Optional[datetime], window: timedelta, now: datetime) -> bool:
        """우선순위 Todo 판별"""
        if due_date is None:
            return True  # 마감일 없는 작업도 포함
        
        # 마감일이 윈도우 내에 있는지 확인
        return due_date <= now + window
    
    async def _generate_proactive_message(self, todos: List[Tuple[str, Optional[datetime], str, str]]) -> Optional[str]:
        """프로액티브 메시지 생성"""
        try:
            from src.ai_engine.llm_provider import GeminiProvider, ChatMessage
            
            if not todos:
                return None
            
            # Todo 목록을 텍스트로 변환
            todo_text = "\n".join([
                f"- {title} (마감: {due.strftime('%m/%d %H:%M') if due else '없음'})"
                for title, due, _, _ in todos[:5]  # 최대 5개만
            ])
            
            # LLM을 사용해 자연스러운 메시지 생성
            llm = GeminiProvider()
            
            prompt = f"""
다음 미완료 작업들에 대해 사용자에게 자연스럽고 도움이 되는 리마인더 메시지를 한국어로 작성해주세요.
너무 길지 않고 친근한 톤으로 작성해주세요.

미완료 작업들:
{todo_text}

메시지 스타일:
- 친근하고 격려하는 톤
- 간결하고 명확한 표현
- 이모지 적절히 사용
- 150자 이내
"""
            
            messages = [ChatMessage(role="user", content=prompt)]
            response = await llm.get_response_async(messages)
            
            return response.strip() if response else None
            
        except Exception as e:
            self.logger.error(f"프로액티브 메시지 생성 중 오류: {e}")
            return None
    
    async def _send_notification_to_channels(self, message: str):
        """알림 메시지를 채널들에 전송"""
        try:
            sent_count = 0
            
            for guild in self.bot.guilds:
                channel = await self._get_notification_channel(guild)
                
                if channel:
                    try:
                        await channel.send(message)
                        sent_count += 1
                    except Exception as e:
                        self.logger.warning(f"채널 {channel.name}에 알림 전송 실패: {e}")
            
            if sent_count > 0:
                self.logger.info(f"{sent_count}개 채널에 알림 전송 완료")
            
        except Exception as e:
            self.logger.error(f"알림 전송 중 오류: {e}")
    
    async def _get_notification_channel(self, guild):
        """알림을 보낼 채널 찾기"""
        try:
            # 시스템 채널 우선
            if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                return guild.system_channel
            
            # 'general' 또는 '일반' 채널 찾기
            for channel in guild.text_channels:
                if channel.name.lower() in ['general', '일반', 'bot', '봇'] and channel.permissions_for(guild.me).send_messages:
                    return channel
            
            # 첫 번째 사용 가능한 텍스트 채널
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    return channel
            
            return None
            
        except Exception as e:
            self.logger.warning(f"알림 채널 찾기 실패 ({guild.name}): {e}")
            return None
