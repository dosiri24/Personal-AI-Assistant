"""
Discord Bot 서버 관리 모듈
"""

import discord
import asyncio
import os
import psutil
import platform
from typing import TYPE_CHECKING, Dict, Any
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ..bot import DiscordBot

from .types import BotStatus


class ServerManager:
    """서버 관리 클래스"""
    
    def __init__(self, bot_instance: 'DiscordBot'):
        self.bot_instance = bot_instance
        self.bot = bot_instance.bot
        self.logger = bot_instance.logger
        self.settings = bot_instance.settings
        self.config = bot_instance.config
        
        # 시작 시간 기록
        self.start_time = datetime.now()
    
    def get_status(self) -> Dict[str, Any]:
        """봇 상태 정보 반환"""
        try:
            # 가동 시간 계산
            uptime = datetime.now() - self.start_time
            uptime_str = self._format_uptime(uptime)
            
            # 시스템 리소스 정보
            memory_usage = self._get_memory_usage()
            cpu_usage = self._get_cpu_usage()
            
            status = {
                'is_running': self.bot_instance.is_running,
                'status': self.bot_instance.state.status.value,
                'guild_count': len(self.bot.guilds) if self.bot.guilds else 0,
                'uptime': uptime_str,
                'start_time': self.start_time.isoformat(),
                'memory_usage': memory_usage,
                'cpu_usage': cpu_usage,
                'latency': round(self.bot.latency * 1000) if self.bot.latency else 0,
                'message_count': self.bot_instance.state.message_count,
                'command_count': self.bot_instance.state.command_count,
                'error_count': self.bot_instance.state.error_count,
                'connected_guilds': self.bot_instance.state.connected_guilds
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"상태 정보 수집 중 오류: {e}")
            return {
                'is_running': False,
                'status': 'error',
                'error': str(e)
            }
    
    def _format_uptime(self, uptime: timedelta) -> str:
        """가동 시간을 읽기 쉬운 형태로 포맷"""
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}일 {hours}시간 {minutes}분"
        elif hours > 0:
            return f"{hours}시간 {minutes}분"
        elif minutes > 0:
            return f"{minutes}분 {seconds}초"
        else:
            return f"{seconds}초"
    
    def _get_memory_usage(self) -> str:
        """메모리 사용량 정보"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            system_memory = psutil.virtual_memory()
            system_memory_gb = system_memory.total / 1024 / 1024 / 1024
            
            return f"{memory_mb:.1f}MB / {system_memory_gb:.1f}GB ({system_memory.percent:.1f}%)"
        except Exception:
            return "정보 없음"
    
    def _get_cpu_usage(self) -> str:
        """CPU 사용량 정보"""
        try:
            process = psutil.Process()
            cpu_percent = process.cpu_percent()
            system_cpu = psutil.cpu_percent(interval=0.1)
            
            return f"프로세스: {cpu_percent:.1f}% / 시스템: {system_cpu:.1f}%"
        except Exception:
            return "정보 없음"
    
    async def shutdown_gracefully(self):
        """서버를 안전하게 종료"""
        try:
            await asyncio.sleep(1)  # 응답 메시지가 전송될 시간을 줌
            
            self.logger.info("서버 종료 시작...")
            self.bot_instance.state.status = BotStatus.SHUTTING_DOWN
            
            # Discord 연결 알림 메시지 전송
            await self._send_shutdown_notifications()
            
            # 백그라운드 작업 정리
            await self._cleanup_background_tasks()
            
            # 봇 종료
            await self.bot_instance.stop()
            
            # 종료 신호 파일 생성
            await self._create_shutdown_signal()
            
            self.logger.info("서버 종료 완료")
            
        except Exception as e:
            self.logger.error(f"서버 종료 중 오류: {e}")
            await self._force_shutdown()
    
    async def _send_shutdown_notifications(self):
        """종료 알림 메시지 전송"""
        try:
            for guild in self.bot.guilds:
                channel = await self._get_notification_channel(guild)
                
                if channel:
                    embed = discord.Embed(
                        title="🔴 서버 종료",
                        description="서버가 안전하게 종료됩니다.",
                        color=0xff0000,
                        timestamp=datetime.now()
                    )
                    
                    embed.add_field(
                        name="가동 시간",
                        value=self._format_uptime(datetime.now() - self.start_time),
                        inline=True
                    )
                    
                    embed.add_field(
                        name="처리한 메시지",
                        value=f"{self.bot_instance.state.message_count}개",
                        inline=True
                    )
                    
                    await channel.send(embed=embed)
                    
        except Exception as e:
            self.logger.warning(f"종료 알림 전송 실패: {e}")
    
    async def _get_notification_channel(self, guild):
        """알림을 보낼 채널 찾기"""
        # 시스템 채널 우선
        if guild.system_channel:
            return guild.system_channel
        
        # 첫 번째 텍스트 채널 사용
        text_channels = [ch for ch in guild.channels 
                        if isinstance(ch, discord.TextChannel) and ch.permissions_for(guild.me).send_messages]
        
        return text_channels[0] if text_channels else None
    
    async def _cleanup_background_tasks(self):
        """백그라운드 작업 정리"""
        try:
            self.logger.info("백그라운드 서비스 정리 중...")
            
            # 리마인더 작업 정리
            if hasattr(self.bot_instance, '_reminder_task') and self.bot_instance._reminder_task:
                self.bot_instance._reminder_task.cancel()
                try:
                    await self.bot_instance._reminder_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("리마인더 작업 정리 완료")
            
            # 프로액티브 작업 정리
            if hasattr(self.bot_instance, '_proactive_task') and self.bot_instance._proactive_task:
                self.bot_instance._proactive_task.cancel()
                try:
                    await self.bot_instance._proactive_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("프로액티브 작업 정리 완료")
            
            # 세션 매니저 정리
            if hasattr(self.bot_instance, 'session_manager'):
                try:
                    await self.bot_instance.session_manager.cleanup()
                    self.logger.info("세션 매니저 정리 완료")
                except Exception as e:
                    self.logger.warning(f"세션 매니저 정리 실패: {e}")
            
        except Exception as e:
            self.logger.warning(f"백그라운드 작업 정리 중 오류: {e}")
    
    async def _create_shutdown_signal(self):
        """종료 신호 파일 생성"""
        try:
            shutdown_file = "/tmp/ai_assistant_shutdown_requested"
            with open(shutdown_file, "w") as f:
                f.write(f"shutdown_requested_{datetime.now().isoformat()}")
            
            self.logger.info("종료 신호 파일 생성됨")
            
        except Exception as e:
            self.logger.error(f"종료 신호 파일 생성 실패: {e}")
    
    async def _force_shutdown(self):
        """강제 종료"""
        try:
            self.logger.warning("강제 종료 실행")
            
            # 강제 종료 신호 파일 생성
            force_shutdown_file = "/tmp/ai_assistant_force_shutdown"
            with open(force_shutdown_file, "w") as f:
                f.write(f"force_shutdown_{datetime.now().isoformat()}")
            
            # 봇 상태 업데이트
            self.bot_instance.state.status = BotStatus.STOPPED
            
        except Exception as e:
            self.logger.error(f"강제 종료 중 오류: {e}")
    
    def get_system_info(self) -> Dict[str, Any]:
        """시스템 정보 반환"""
        try:
            # 시스템 기본 정보
            system_info = {
                'platform': platform.system(),
                'release': platform.release(),
                'version': platform.version(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'python_version': platform.python_version(),
                'hostname': platform.node()
            }
            
            # CPU 정보
            cpu_info = {
                'cpu_count': psutil.cpu_count(),
                'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                'cpu_percent': psutil.cpu_percent(interval=1),
                'cpu_times': psutil.cpu_times()._asdict()
            }
            
            # 메모리 정보
            memory = psutil.virtual_memory()
            memory_info = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent
            }
            
            # 디스크 정보
            disk = psutil.disk_usage('/')
            disk_info = {
                'total': disk.total,
                'used': disk.used,
                'free': disk.free,
                'percent': (disk.used / disk.total) * 100
            }
            
            # 네트워크 정보
            network = psutil.net_io_counters()
            network_info = {
                'bytes_sent': network.bytes_sent,
                'bytes_recv': network.bytes_recv,
                'packets_sent': network.packets_sent,
                'packets_recv': network.packets_recv
            } if network else {}
            
            return {
                'system': system_info,
                'cpu': cpu_info,
                'memory': memory_info,
                'disk': disk_info,
                'network': network_info,
                'boot_time': psutil.boot_time()
            }
            
        except Exception as e:
            self.logger.error(f"시스템 정보 수집 중 오류: {e}")
            return {'error': str(e)}
