"""
Discord Bot 메시지 파싱 시스템 (단순화)

자연어 메시지를 LLM에게 전달하기 위해 기본적인 메타데이터만 추출하고
실제 자연어 처리는 Phase 3의 AI 엔진에서 담당합니다.
"""

import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import discord
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger


class MessageContext(Enum):
    """메시지 컨텍스트 열거형"""
    DM = "dm"
    MENTION = "mention"
    CHANNEL = "channel"


class MessageType(Enum):
    """메시지 타입 열거형 (단순화)"""
    COMMAND = "command"          # ! 로 시작하는 명령어
    NATURAL_LANGUAGE = "natural" # 자연어 메시지
    GREETING = "greeting"        # 간단한 인사
    EMPTY = "empty"             # 빈 메시지


@dataclass
class ParsedMessage:
    """파싱된 메시지 데이터 클래스 (단순화)"""
    message_type: MessageType
    original_text: str
    cleaned_text: str
    context: MessageContext
    user_id: int
    user_name: str
    channel_type: str
    timestamp: str
    is_command: bool
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "message_type": self.message_type.value,
            "original_text": self.original_text,
            "cleaned_text": self.cleaned_text,
            "context": self.context.value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "channel_type": self.channel_type,
            "timestamp": self.timestamp,
            "is_command": self.is_command,
            "metadata": self.metadata
        }


class MessageParser:
    """
    Discord 메시지 파서 클래스 (단순화)
    
    자연어 메시지를 LLM에게 전달하기 위해 필요한 최소한의 메타데이터만 추출합니다.
    실제 자연어 이해는 Phase 3의 AI 엔진에서 담당합니다.
    """
    
    def __init__(self):
        """메시지 파서 초기화"""
        self.logger = get_discord_logger()
        
        # 간단한 명령어 패턴 (! 로 시작)
        self.command_pattern = re.compile(r'^!(\w+)')
        
        # 간단한 인사 패턴
        self.greeting_patterns = [
            r'^(안녕|하이|헬로|hello|hi)$',
            r'^(안녕하세요|반갑습니다)$'
        ]
        
        self.logger.info("메시지 파서 초기화 완료 (단순화된 버전)")
    
    def parse_message(self, message: discord.Message) -> ParsedMessage:
        """
        Discord 메시지를 파싱하여 기본 메타데이터 추출
        
        Args:
            message: Discord 메시지 객체
            
        Returns:
            파싱된 메시지 객체
        """
        try:
            # 메시지 컨텍스트 확인
            context = self._determine_context(message)
            
            # 메시지 내용 정리 (멘션 제거)
            cleaned_text = self._clean_message_content(message)
            original_text = message.content.strip()
            
            # 메시지 타입 결정
            message_type = self._determine_message_type(cleaned_text)
            
            # 기본 메타데이터
            metadata = {
                "has_mentions": len(message.mentions) > 0,
                "mention_count": len(message.mentions),
                "message_length": len(cleaned_text),
                "word_count": len(cleaned_text.split()) if cleaned_text else 0
            }
            
            # 사용자 정보
            user_name = getattr(message.author, 'display_name', str(message.author))
            
            # 타임스탬프
            timestamp = message.created_at.isoformat() if hasattr(message, 'created_at') else ""
            
            parsed_message = ParsedMessage(
                message_type=message_type,
                original_text=original_text,
                cleaned_text=cleaned_text,
                context=context,
                user_id=message.author.id,
                user_name=user_name,
                channel_type=str(type(message.channel).__name__),
                timestamp=timestamp,
                is_command=message_type == MessageType.COMMAND,
                metadata=metadata
            )
            
            self.logger.info(f"메시지 파싱 완료: {message_type.value} (길이: {len(cleaned_text)})")
            return parsed_message
            
        except Exception as e:
            self.logger.error(f"메시지 파싱 중 오류: {e}", exc_info=True)
            
            # 오류 발생시 기본 메시지 반환
            return ParsedMessage(
                message_type=MessageType.NATURAL_LANGUAGE,
                original_text=getattr(message, 'content', ''),
                cleaned_text='',
                context=self._determine_context(message),
                user_id=getattr(message.author, 'id', 0),
                user_name=str(getattr(message, 'author', 'Unknown')),
                channel_type=str(type(getattr(message, 'channel', object())).__name__),
                timestamp='',
                is_command=False,
                metadata={"error": str(e)}
            )
    
    def _determine_context(self, message: discord.Message) -> MessageContext:
        """메시지 컨텍스트 결정"""
        try:
            if isinstance(message.channel, discord.DMChannel):
                return MessageContext.DM
            elif message.mentions:
                return MessageContext.MENTION
            else:
                return MessageContext.CHANNEL
        except:
            return MessageContext.CHANNEL
    
    def _clean_message_content(self, message: discord.Message) -> str:
        """메시지 내용 정리 (멘션 제거)"""
        try:
            content = message.content.strip()
            
            # 봇 멘션 제거
            for mention in message.mentions:
                content = content.replace(f'<@{mention.id}>', '').strip()
                content = content.replace(f'<@!{mention.id}>', '').strip()
            
            # 여러 공백을 하나로 통합
            content = re.sub(r'\s+', ' ', content).strip()
            
            return content
        except:
            return ""
    
    def _determine_message_type(self, content: str) -> MessageType:
        """메시지 타입 결정"""
        if not content:
            return MessageType.EMPTY
        
        # 명령어 확인 (! 로 시작)
        if self.command_pattern.match(content):
            return MessageType.COMMAND
        
        # 간단한 인사 확인
        content_lower = content.lower()
        for pattern in self.greeting_patterns:
            if re.match(pattern, content_lower):
                return MessageType.GREETING
        
        # 나머지는 모두 자연어로 처리
        return MessageType.NATURAL_LANGUAGE
    
    def get_parser_stats(self) -> Dict[str, Any]:
        """파서 통계 정보 반환"""
        return {
            "parser_type": "simplified",
            "supported_contexts": [ctx.value for ctx in MessageContext],
            "supported_message_types": [msg_type.value for msg_type in MessageType],
            "natural_language_processing": "delegated_to_ai_engine"
        }
