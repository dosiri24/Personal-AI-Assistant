"""
계산기 도구 - 수학 계산을 수행하는 예제 도구
"""

import asyncio
from typing import Dict, Any
from ..base_tool import BaseTool, ToolResult, ToolMetadata, ToolCategory, ToolParameter, ParameterType, ExecutionStatus


class CalculatorTool(BaseTool):
    """간단한 계산기 도구"""
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name="calculator",
            description="수학 계산을 수행합니다. 사칙연산, 거듭제곱 등을 지원합니다.",
            version="1.0.0",
            category=ToolCategory.PRODUCTIVITY,
            author="AI Assistant",
            tags=["math", "calculator", "computation"],
            parameters=[
                ToolParameter(
                    name="expression",
                    type=ParameterType.STRING,
                    description="계산할 수학 표현식 (예: '2 + 3 * 4', '2 ** 3')",
                    required=True
                )
            ]
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """계산 실행"""
        try:
            expression = parameters.get("expression", "")
            
            # 보안을 위해 허용된 문자만 사용
            allowed_chars = set("0123456789+-*/() .**")
            if not all(c in allowed_chars for c in expression):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="허용되지 않은 문자가 포함되어 있습니다. 숫자와 +, -, *, /, (, ), **, 공백만 사용 가능합니다."
                )
            
            # 계산 수행
            result = eval(expression)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=f"{expression} = {result}"
            )
            
        except ZeroDivisionError:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message="0으로 나눌 수 없습니다."
            )
        except Exception as e:
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"계산 오류: {str(e)}"
            )


# 도구 인스턴스 생성 (자동 발견을 위해)
tool_instance = CalculatorTool()
