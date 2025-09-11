"""
Discord Bot 슬래시 명령어 모듈
"""

import discord
from discord.ext import commands
from typing import TYPE_CHECKING
import asyncio
import subprocess
import psutil
import platform

if TYPE_CHECKING:
    from ..bot import DiscordBot

from .types import is_admin_user


class SlashCommands:
    """Discord Bot 슬래시 명령어 클래스"""
    
    def __init__(self, bot_instance: 'DiscordBot'):
        self.bot_instance = bot_instance
        self.bot = bot_instance.bot
        self.logger = bot_instance.logger
        self.settings = bot_instance.settings
        self.config = bot_instance.config
        
        # 슬래시 명령어 설정
        self._setup_slash_commands()
    
    def _setup_slash_commands(self):
        """모든 슬래시 명령어 등록"""
        
        @self.bot.tree.command(name="help", description="사용 가능한 명령어 목록을 표시합니다")
        async def help_slash(interaction: discord.Interaction):
            """도움말 슬래시 명령어"""
            await self._handle_help(interaction)
        
        @self.bot.tree.command(name="status", description="봇의 현재 상태를 확인합니다")
        async def status_slash(interaction: discord.Interaction):
            """상태 확인 슬래시 명령어"""
            await self._handle_status(interaction)
        
        @self.bot.tree.command(name="server", description="서버의 현재 상태를 확인합니다")
        async def server_status_slash(interaction: discord.Interaction):
            """서버 상태 확인 슬래시 명령어"""
            await self._handle_server_status(interaction)
        
        @self.bot.tree.command(name="ping", description="봇의 응답 속도를 확인합니다")
        async def ping_slash(interaction: discord.Interaction):
            """핑 확인 슬래시 명령어"""
            await self._handle_ping(interaction)
        
        @self.bot.tree.command(name="calculate", description="수학 계산을 수행합니다")
        async def calculate_slash(interaction: discord.Interaction, expression: str):
            """계산 슬래시 명령어"""
            await self._handle_calculate(interaction, expression)
        
        @self.bot.tree.command(name="shutdown", description="서버를 안전하게 종료합니다 (관리자 전용)")
        async def shutdown_slash(interaction: discord.Interaction):
            """종료 슬래시 명령어"""
            await self._handle_shutdown(interaction)
    
    async def _handle_help(self, interaction: discord.Interaction):
        """도움말 처리"""
        embed = discord.Embed(
            title="🤖 Personal AI Assistant 명령어",
            description="사용 가능한 슬래시 명령어 목록입니다",
            color=0x00ff00
        )
        
        embed.add_field(
            name="/help",
            value="이 도움말을 표시합니다",
            inline=False
        )
        
        embed.add_field(
            name="/status",
            value="봇의 현재 상태를 확인합니다",
            inline=False
        )
        
        embed.add_field(
            name="/server",
            value="서버의 현재 상태를 확인합니다",
            inline=False
        )
        
        embed.add_field(
            name="/ping",
            value="봇의 응답 속도를 확인합니다",
            inline=False
        )
        
        embed.add_field(
            name="/calculate",
            value="수학 계산을 수행합니다",
            inline=False
        )
        
        embed.add_field(
            name="/shutdown",
            value="서버를 안전하게 종료합니다 (관리자 전용)",
            inline=False
        )
        
        embed.set_footer(text="자연어로 대화하시려면 그냥 메시지를 보내세요!")
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_status(self, interaction: discord.Interaction):
        """봇 상태 확인 처리"""
        status = self.bot_instance.get_status()
        
        embed = discord.Embed(
            title="🤖 봇 상태",
            color=0x00ff00 if status.get('is_running', False) else 0xff0000
        )
        
        embed.add_field(
            name="상태",
            value="🟢 실행 중" if status.get('is_running', False) else "🔴 중지됨",
            inline=True
        )
        
        embed.add_field(
            name="서버 수",
            value=str(status.get('guild_count', 0)),
            inline=True
        )
        
        embed.add_field(
            name="응답 속도",
            value=f"{round(self.bot.latency * 1000)}ms",
            inline=True
        )
        
        if 'uptime' in status:
            embed.add_field(
                name="가동 시간",
                value=status['uptime'],
                inline=True
            )
        
        if 'memory_usage' in status:
            embed.add_field(
                name="메모리 사용량",
                value=status['memory_usage'],
                inline=True
            )
        
        if 'cpu_usage' in status:
            embed.add_field(
                name="CPU 사용량",
                value=status['cpu_usage'],
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_server_status(self, interaction: discord.Interaction):
        """서버 상태 확인 처리"""
        try:
            # 시스템 정보 수집
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            embed = discord.Embed(
                title="🖥️ 서버 상태",
                color=0x00ff00
            )
            
            # 기본 시스템 정보
            embed.add_field(
                name="운영체제",
                value=f"{platform.system()} {platform.release()}",
                inline=True
            )
            
            embed.add_field(
                name="Python 버전",
                value=platform.python_version(),
                inline=True
            )
            
            # CPU 정보
            embed.add_field(
                name="CPU 사용률",
                value=f"{cpu_percent}%",
                inline=True
            )
            
            # 메모리 정보
            embed.add_field(
                name="메모리 사용률",
                value=f"{memory.percent}% ({memory.used // (1024**3):.1f}GB / {memory.total // (1024**3):.1f}GB)",
                inline=False
            )
            
            # 디스크 정보
            embed.add_field(
                name="디스크 사용률",
                value=f"{disk.percent}% ({disk.used // (1024**3):.1f}GB / {disk.total // (1024**3):.1f}GB)",
                inline=False
            )
            
            # Discord 연결 정보
            embed.add_field(
                name="Discord 연결",
                value=f"🟢 연결됨 (지연시간: {round(self.bot.latency * 1000)}ms)",
                inline=False
            )
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 서버 상태 확인 실패",
                description=f"서버 정보를 가져오는 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_ping(self, interaction: discord.Interaction):
        """핑 확인 처리"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"응답 속도: {latency}ms",
            color=0x00ff00 if latency < 100 else 0xffff00 if latency < 300 else 0xff0000
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_calculate(self, interaction: discord.Interaction, expression: str):
        """계산 처리"""
        try:
            # 보안을 위해 허용된 문자만 사용
            allowed_chars = set('0123456789+-*/().^ ')
            if not all(c in allowed_chars for c in expression):
                raise ValueError("허용되지 않은 문자가 포함되어 있습니다")
            
            # 간단한 수학 계산 수행
            # ^ 연산자를 ** 로 변경 (거듭제곱)
            safe_expression = expression.replace('^', '**')
            
            # eval 사용 (제한된 환경에서)
            result = eval(safe_expression, {"__builtins__": {}}, {})
            
            embed = discord.Embed(
                title="🧮 계산 결과",
                color=0x00ff00
            )
            
            embed.add_field(
                name="입력",
                value=f"`{expression}`",
                inline=False
            )
            
            embed.add_field(
                name="결과",
                value=f"`{result}`",
                inline=False
            )
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 계산 오류",
                description=f"계산 중 오류가 발생했습니다: {str(e)}",
                color=0xff0000
            )
        
        await interaction.response.send_message(embed=embed)
    
    async def _handle_shutdown(self, interaction: discord.Interaction):
        """종료 처리"""
        # 관리자 권한 확인
        if not is_admin_user(interaction.user.id, self.config):
            embed = discord.Embed(
                title="❌ 권한 부족",
                description="이 명령어는 관리자만 사용할 수 있습니다.",
                color=0xff0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🔄 서버 종료",
            description="서버를 안전하게 종료하고 있습니다...",
            color=0xffff00
        )
        
        await interaction.response.send_message(embed=embed)
        
        # 백그라운드에서 종료 실행
        asyncio.create_task(self.bot_instance._shutdown_server_gracefully())
