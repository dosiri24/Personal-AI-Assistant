"""
Discord Bot 메시지 라우터

파싱된 메시지를 적절한 처리기로 라우팅하고
CLI를 통해 LLM으로 자연어를 전달하는 시스템입니다.
"""

import asyncio
import subprocess
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger
from .parser import ParsedMessage, MessageType, MessageContext


@dataclass
class ResponseMessage:
    """응답 메시지 데이터 클래스"""
    content: str
    is_embed: bool = False
    embed_data: Optional[Dict[str, Any]] = None
    is_file: bool = False
    file_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "content": self.content,
            "is_embed": self.is_embed,
            "embed_data": self.embed_data,
            "is_file": self.is_file,
            "file_path": self.file_path
        }


class MessageRouter:
    """
    Discord 메시지 라우팅 클래스 (단순화)
    
    파싱된 메시지를 처리하고 적절한 응답을 생성합니다.
    자연어 메시지는 CLI를 통해 LLM으로 전달됩니다.
    """
    
    def __init__(self):
        """메시지 라우터 초기화"""
        self.logger = get_discord_logger()
        self.project_root = Path(__file__).parent.parent.parent
        self.cli_path = self.project_root / "src" / "cli" / "main.py"
        
        # 간단한 응답 템플릿
        self.quick_responses = {
            MessageType.GREETING: [
                "안녕하세요! 무엇을 도와드릴까요?",
                "반갑습니다! 궁금한 것이 있으시면 언제든 말씀해주세요.",
                "안녕하세요! 저는 개인 AI 어시스턴트입니다. 도움이 필요하시면 말씀해주세요."
            ],
            MessageType.EMPTY: [
                "메시지가 비어있는 것 같네요. 무엇을 도와드릴까요?",
                "말씀하고 싶은 것이 있으시면 언제든 말씀해주세요!"
            ]
        }
        
        self.logger.info("메시지 라우터 초기화 완료 (단순화된 버전)")
    
    async def route_message(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """
        파싱된 메시지를 라우팅하고 응답 생성
        
        Args:
            parsed_message: 파싱된 메시지 객체
            
        Returns:
            응답 메시지 객체
        """
        try:
            self.logger.info(f"메시지 라우팅 시작: {parsed_message.message_type.value}")
            
            # 메시지 타입별 처리
            if parsed_message.message_type == MessageType.COMMAND:
                return await self._handle_command(parsed_message)
            elif parsed_message.message_type == MessageType.GREETING:
                return self._handle_greeting(parsed_message)
            elif parsed_message.message_type == MessageType.EMPTY:
                return self._handle_empty(parsed_message)
            elif parsed_message.message_type == MessageType.NATURAL_LANGUAGE:
                return await self._handle_natural_language(parsed_message)
            else:
                return self._handle_unknown(parsed_message)
                
        except Exception as e:
            self.logger.error(f"메시지 라우팅 중 오류: {e}", exc_info=True)
            return ResponseMessage(
                content=f"죄송합니다. 메시지 처리 중 오류가 발생했습니다: {str(e)}"
            )
    
    async def _handle_command(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """명령어 처리 (! 로 시작하는 명령어)"""
        command_text = parsed_message.cleaned_text
        
        if command_text.startswith('!help') or command_text.startswith('!도움말'):
            return ResponseMessage(
                content=("🤖 개인 AI 어시스턴트 도움말\n\n"
                        "• 자연어로 대화하세요 (예: 내일 회의 일정 추가해줘)\n"
                        "• !help 또는 !도움말: 이 도움말 보기\n"
                        "• !status 또는 !상태: 봇 상태 확인\n\n"
                        "무엇이든 자연어로 말씀해주시면 AI가 도와드립니다!")
            )
        elif command_text.startswith('!status') or command_text.startswith('!상태'):
            return ResponseMessage(
                content=("✅ AI 어시스턴트가 정상적으로 작동 중입니다!\n\n"
                        f"• 메시지 파서: 활성화\n"
                        f"• CLI 연동: 활성화\n"
                        f"• LLM 처리: 대기 중\n"
                        f"• 처리된 메시지: {parsed_message.message_type.value}")
            )
        else:
            # 알 수 없는 명령어는 자연어로 처리
            return await self._handle_natural_language(parsed_message)
    
    def _handle_greeting(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """인사 메시지 처리"""
        import random
        response = random.choice(self.quick_responses[MessageType.GREETING])
        
        # 사용자 이름이 있으면 개인화
        if parsed_message.user_name:
            response = f"{parsed_message.user_name}님, " + response
        
        return ResponseMessage(content=response)
    
    def _handle_empty(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """빈 메시지 처리"""
        import random
        response = random.choice(self.quick_responses[MessageType.EMPTY])
        return ResponseMessage(content=response)
    
    async def _handle_natural_language(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """자연어 메시지를 CLI를 통해 LLM으로 전달"""
        try:
            self.logger.info(f"자연어 메시지를 CLI로 전달: {parsed_message.cleaned_text[:50]}...")
            
            # CLI 명령어 구성
            cli_command = [
                sys.executable,
                str(self.cli_path),
                "process-message",
                "--message", parsed_message.cleaned_text,
                "--user-id", str(parsed_message.user_id),
                "--user-name", parsed_message.user_name,
                "--context", parsed_message.context.value,
                "--format", "json"
            ]
            
            # CLI 실행 (비동기)
            process = await asyncio.create_subprocess_exec(
                *cli_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root)
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # 성공적으로 처리된 경우
                try:
                    result = json.loads(stdout.decode('utf-8'))
                    response_content = result.get('response', '응답을 생성할 수 없습니다.')
                    
                    self.logger.info("CLI를 통한 자연어 처리 성공")
                    return ResponseMessage(content=response_content)
                    
                except json.JSONDecodeError:
                    # JSON 파싱 실패시 텍스트 그대로 사용
                    response_content = stdout.decode('utf-8').strip()
                    return ResponseMessage(
                        content=response_content if response_content else "처리 완료되었습니다."
                    )
            else:
                # CLI 실행 실패
                error_msg = stderr.decode('utf-8').strip()
                self.logger.error(f"CLI 실행 실패: {error_msg}")
                
                return ResponseMessage(
                    content="죄송합니다. 현재 AI 처리 시스템이 준비 중입니다. 잠시 후 다시 시도해주세요."
                )
                
        except Exception as e:
            self.logger.error(f"자연어 처리 중 오류: {e}", exc_info=True)
            return ResponseMessage(
                content="죄송합니다. 메시지 처리 중 문제가 발생했습니다. 다시 시도해주세요."
            )
    
    def _handle_unknown(self, parsed_message: ParsedMessage) -> ResponseMessage:
        """알 수 없는 메시지 타입 처리"""
        return ResponseMessage(
            content="죄송합니다. 메시지를 이해할 수 없습니다. 다시 말씀해주시겠어요?"
        )
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """라우팅 통계 정보 반환"""
        return {
            "router_type": "simplified",
            "cli_integration": "enabled",
            "natural_language_processing": "delegated_to_llm",
            "supported_message_types": [msg_type.value for msg_type in MessageType],
            "cli_path": str(self.cli_path)
        }
