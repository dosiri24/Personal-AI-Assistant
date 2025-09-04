"""
시간 도구 - 현재 시간 정보를 제공하는 예제 도구
"""

import asyncio
from datetime import datetime
from typing import Dict, Any
from ..base_tool import BaseTool, ToolResult, ToolMetadata, ToolCategory, ToolParameter, ParameterType, ExecutionStatus


class TimeTool(BaseTool):
    """현재 시간 정보를 제공하는 도구"""
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name="time_info",
            description="현재 시간, 날짜 정보를 제공합니다.",
            version="1.0.0",
            category=ToolCategory.SYSTEM,
            author="AI Assistant",
            tags=["time", "date", "clock"],
            parameters=[
                ToolParameter(
                    name="format",
                    type=ParameterType.STRING,
                    description="시간 형식 ('datetime', 'date', 'time' 중 하나)",
                    choices=["datetime", "date", "time"],
                    default="datetime",
                    required=False
                )
            ]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """시간 정보 반환"""
        try:
            format_type = parameters.get("format", "datetime")
            now = datetime.now()
            
            if format_type == "date":
                result = now.strftime("%Y년 %m월 %d일")
            elif format_type == "time":
                result = now.strftime("%H시 %M분 %S초")
            else:  # datetime
                result = now.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=f"현재 {format_type}: {result}"
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"시간 조회 오류: {str(e)}"
            )


# 도구 인스턴스 생성 (자동 발견을 위해)
tool_instance = TimeTool()
