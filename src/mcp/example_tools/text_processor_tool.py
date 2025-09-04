"""
텍스트 처리 도구 - 간단한 텍스트 조작을 수행하는 예제 도구
"""

import asyncio
from typing import Dict, Any
from ..base_tool import BaseTool, ToolResult, ToolMetadata, ToolCategory, ToolParameter, ParameterType, ExecutionStatus


class TextProcessorTool(BaseTool):
    """텍스트 처리 도구"""
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name="text_processor",
            description="텍스트를 처리합니다. 대소문자 변환, 길이 계산, 단어 수 계산 등을 지원합니다.",
            version="1.0.0",
            category=ToolCategory.PRODUCTIVITY,
            author="AI Assistant",
            tags=["text", "processing", "utility"],
            parameters=[
                ToolParameter(
                    name="text",
                    type=ParameterType.STRING,
                    description="처리할 텍스트",
                    required=True
                ),
                ToolParameter(
                    name="operation",
                    type=ParameterType.STRING,
                    description="수행할 작업",
                    choices=["uppercase", "lowercase", "length", "word_count", "reverse"],
                    default="length",
                    required=False
                )
            ]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """텍스트 처리 실행"""
        try:
            text = parameters.get("text", "")
            operation = parameters.get("operation", "length")
            
            if operation == "uppercase":
                result = text.upper()
                message = f"대문자 변환: {result}"
            elif operation == "lowercase":
                result = text.lower()
                message = f"소문자 변환: {result}"
            elif operation == "length":
                result = len(text)
                message = f"텍스트 길이: {result}자"
            elif operation == "word_count":
                result = len(text.split())
                message = f"단어 수: {result}개"
            elif operation == "reverse":
                result = text[::-1]
                message = f"역순 텍스트: {result}"
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원되지 않는 작업: {operation}"
                )
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=message
            )
            
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"텍스트 처리 오류: {str(e)}"
            )


# 도구 인스턴스 생성 (자동 발견을 위해)
tool_instance = TextProcessorTool()
