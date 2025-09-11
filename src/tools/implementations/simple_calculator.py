"""
간단한 계산기 도구

새로운 아키텍처에 맞게 단순화된 계산기 도구입니다.
"""

from typing import Dict, Any
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.tools.base import BaseTool, ExecutionResult


class SimpleCalculatorTool(BaseTool):
    """간단한 계산기 도구"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="기본적인 수학 연산을 수행하는 계산기 도구",
            category="utility"
        )
        
        # 매개변수 정의
        self.add_parameter("operation", "str", "수행할 연산 (+, -, *, /)", required=True)
        self.add_parameter("a", "float", "첫 번째 숫자", required=True)  
        self.add_parameter("b", "float", "두 번째 숫자", required=True)
    
    async def _execute_impl(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """계산기 실행"""
        operation = parameters["operation"]
        a = float(parameters["a"])
        b = float(parameters["b"])
        
        try:
            if operation == "+":
                result = a + b
            elif operation == "-":
                result = a - b
            elif operation == "*":
                result = a * b
            elif operation == "/":
                if b == 0:
                    return ExecutionResult(
                        success=False,
                        message="0으로 나눌 수 없습니다",
                        errors=["Division by zero"]
                    )
                result = a / b
            else:
                return ExecutionResult(
                    success=False,
                    message=f"지원되지 않는 연산: {operation}",
                    errors=[f"Unsupported operation: {operation}"]
                )
            
            return ExecutionResult(
                success=True,
                message=f"{a} {operation} {b} = {result}",
                data={"result": result}
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                message=f"계산 오류: {str(e)}",
                errors=[str(e)]
            )


def create_calculator_tool() -> SimpleCalculatorTool:
    """계산기 도구 생성 함수"""
    return SimpleCalculatorTool()