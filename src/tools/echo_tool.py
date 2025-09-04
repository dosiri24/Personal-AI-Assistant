"""
Echo 도구 - MCP 테스트용 간단한 도구

입력받은 메시지를 그대로 반환하는 간단한 도구입니다.
MCP 시스템 테스트 및 데모 목적으로 사용됩니다.
"""

import asyncio
from typing import Dict, Any
from datetime import datetime

from ..mcp.base_tool import BaseTool, ToolMetadata, ToolParameter, ToolResult, ParameterType, ToolCategory, ExecutionStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EchoTool(BaseTool):
    """
    에코 도구
    
    입력받은 메시지를 그대로 반환하는 간단한 테스트 도구입니다.
    """
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name="echo",
            version="1.0.0",
            description="입력받은 메시지를 그대로 반환하는 에코 도구입니다. 테스트 및 데모 목적으로 사용됩니다.",
            category=ToolCategory.SYSTEM,
            author="Personal AI Assistant",
            parameters=[
                ToolParameter(
                    name="message",
                    type=ParameterType.STRING,
                    description="에코할 메시지",
                    required=True
                ),
                ToolParameter(
                    name="delay",
                    type=ParameterType.NUMBER,
                    description="응답 지연 시간 (초)",
                    required=False,
                    default=0.0,
                    min_value=0.0,
                    max_value=10.0
                ),
                ToolParameter(
                    name="uppercase",
                    type=ParameterType.BOOLEAN,
                    description="대문자로 변환 여부",
                    required=False,
                    default=False
                )
            ],
            tags=["test", "demo", "echo", "simple"],
            requires_auth=False,
            timeout=15
        )
    
    async def _initialize(self) -> None:
        """도구 초기화"""
        logger.info("Echo 도구 초기화 완료")
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        에코 실행
        
        Args:
            parameters: 실행 매개변수
                - message (str): 에코할 메시지
                - delay (float, optional): 지연 시간
                - uppercase (bool, optional): 대문자 변환 여부
                
        Returns:
            실행 결과
        """
        try:
            # 매개변수 추출
            message = parameters["message"]
            delay = parameters.get("delay", 0.0)
            uppercase = parameters.get("uppercase", False)
            
            # 지연 시간 적용
            if delay > 0:
                logger.debug(f"Echo 도구 {delay}초 지연 중...")
                await asyncio.sleep(delay)
            
            # 메시지 처리
            result_message = message.upper() if uppercase else message
            
            # 결과 생성
            result_data = {
                "original_message": message,
                "echoed_message": result_message,
                "processed_at": datetime.now().isoformat(),
                "delay_applied": delay,
                "uppercase_applied": uppercase
            }
            
            logger.info(f"Echo 도구 실행 완료: '{message}' -> '{result_message}'")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=result_data,
                metadata={
                    "tool_name": "echo",
                    "message_length": len(message),
                    "processing_time": delay
                }
            )
        
        except Exception as e:
            logger.error(f"Echo 도구 실행 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Echo 도구 실행 중 오류 발생: {str(e)}"
            )
