"""
Discord Bot AI 메시지 처리 모듈
"""

import discord
from typing import TYPE_CHECKING, Optional
import asyncio

if TYPE_CHECKING:
    from ..bot import DiscordBot

from ..ai_handler import get_ai_handler
from ..session import SessionManager


class AIMessageHandler:
    """AI 메시지 처리 클래스"""
    
    def __init__(self, bot_instance: 'DiscordBot'):
        self.bot_instance = bot_instance
        self.bot = bot_instance.bot
        self.logger = bot_instance.logger
        self.settings = bot_instance.settings
        self.config = bot_instance.config
        
        # 세션 매니저 초기화
        self.session_manager = getattr(bot_instance, 'session_manager', None)
        if not self.session_manager:
            self.session_manager = SessionManager()
    
    async def handle_ai_message(self, message: discord.Message):
        """
        AI가 처리해야 할 메시지 핸들링
        
        Args:
            message: Discord 메시지 객체
        """
        try:
            self.logger.info(f"AI 메시지 처리 시작: {message.author} -> {message.content}")
            
            # 빈 메시지 처리
            content = await self._process_message_content(message)
            if not content:
                await message.reply("안녕하세요! 무엇을 도와드릴까요?")
                return
            
            # 타이핑 표시 시작
            async with message.channel.typing():
                await self._process_with_session(message, content)
                
        except Exception as e:
            self.logger.error(f"AI 메시지 처리 중 오류: {e}")
            await self._send_error_response(message, e)
    
    async def _process_message_content(self, message: discord.Message) -> str:
        """메시지 내용 전처리"""
        content = message.content.strip()
        
        # 봇 멘션 제거
        if self.bot.user and self.bot.user in message.mentions:
            content = content.replace(f'<@{self.bot.user.id}>', '').strip()
        
        return content
    
    async def _process_with_session(self, message: discord.Message, content: str):
        """세션을 사용한 메시지 처리"""
        try:
            self.logger.info(f"세션 관리 시작: {message.author.id}")
            
            # 세션 조회/생성
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
            
            # AI Handler를 통한 메시지 처리
            await self._process_with_ai_handler(message, content, session, turn_id)
            
        except Exception as e:
            self.logger.error(f"세션 처리 중 오류: {e}")
            await self._send_error_response(message, e)
    
    async def _process_with_ai_handler(self, message: discord.Message, content: str, session, turn_id: str):
        """AI Handler를 통한 메시지 처리"""
        try:
            self.logger.info("AI Handler 호출 시작")
            ai_handler = get_ai_handler()
            
            # SessionManager 설정
            if hasattr(ai_handler, 'session_manager'):
                ai_handler.session_manager = self.session_manager
            
            # AI 응답 생성
            response = await ai_handler.process_message(
                user_message=content,
                user_id=str(message.author.id),
                channel_id=str(message.channel.id),
                metadata={
                    "turn_id": turn_id,
                    "session_id": session.session_id,
                    "discord_message_id": message.id,
                    "guild_id": message.guild.id if message.guild else None,
                    "is_dm": isinstance(message.channel, discord.DMChannel)
                }
            )
            
            self.logger.info(f"AI Handler 응답: {response}")
            
            # 응답 전송 (AIResponse 객체에서 content 추출)
            response_content = response.content if hasattr(response, 'content') else str(response)
            await self._send_ai_response(message, response_content, turn_id)
            
        except Exception as e:
            self.logger.error(f"AI Handler 처리 중 오류: {e}")
            await self._send_error_response(message, e)
    
    async def _send_ai_response(self, message: discord.Message, response: str, turn_id: str):
        """AI 응답 전송"""
        try:
            # 응답 길이 제한 (Discord 2000자 제한)
            if len(response) > 1900:
                # 긴 응답을 여러 메시지로 분할
                await self._send_long_response(message, response)
            else:
                # 일반 응답 전송
                await message.reply(response)
            
            # 응답을 세션에 기록
            await self.session_manager.update_conversation_turn(
                turn_id=turn_id,
                bot_response=response
            )
            
            self.logger.info(f"AI 응답 전송 완료: {message.author.id}")
            
        except Exception as e:
            self.logger.error(f"AI 응답 전송 중 오류: {e}")
            await self._send_error_response(message, e)
    
    async def _send_long_response(self, message: discord.Message, response: str):
        """긴 응답을 여러 메시지로 분할 전송"""
        MAX_LENGTH = 1900
        
        # 문단 단위로 분할 시도
        paragraphs = response.split('\n\n')
        current_message = ""
        
        for paragraph in paragraphs:
            if len(current_message + paragraph) <= MAX_LENGTH:
                current_message += paragraph + '\n\n'
            else:
                if current_message:
                    await message.reply(current_message.strip())
                    await asyncio.sleep(0.5)  # 메시지 전송 간격
                
                # 현재 문단이 너무 긴 경우 강제 분할
                if len(paragraph) > MAX_LENGTH:
                    words = paragraph.split(' ')
                    current_message = ""
                    for word in words:
                        if len(current_message + word) <= MAX_LENGTH:
                            current_message += word + ' '
                        else:
                            if current_message:
                                await message.reply(current_message.strip())
                                await asyncio.sleep(0.5)
                            current_message = word + ' '
                else:
                    current_message = paragraph + '\n\n'
        
        # 마지막 메시지 전송
        if current_message.strip():
            await message.reply(current_message.strip())
    
    async def _send_error_response(self, message: discord.Message, error: Exception):
        """에러 응답 전송"""
        try:
            error_embed = discord.Embed(
                title="❌ 처리 중 오류 발생",
                description="메시지 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.",
                color=0xff0000
            )
            
            # 관리자에게는 상세 오류 정보 표시
            from .types import is_admin_user
            if is_admin_user(message.author.id, self.config):
                error_embed.add_field(
                    name="오류 상세",
                    value=f"```{str(error)}```",
                    inline=False
                )
            
            await message.reply(embed=error_embed)
            
        except Exception as send_error:
            self.logger.error(f"에러 응답 전송 실패: {send_error}")
            # 마지막 수단으로 간단한 텍스트 메시지
            try:
                await message.reply("처리 중 오류가 발생했습니다. 관리자에게 문의하세요.")
            except:
                pass  # 더 이상 할 수 있는 것이 없음
