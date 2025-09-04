"""
계산기 도구 - 기본 수학 연산 도구

기본적인 수학 연산을 수행하는 도구입니다.
덧셈, 뺄셈, 곱셈, 나눗셈을 지원합니다.
"""

from typing import Dict, Any
from datetime import datetime

from ..mcp.base_tool import BaseTool, ToolMetadata, ToolParameter, ToolResult, ParameterType, ToolCategory, ExecutionStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CalculatorTool(BaseTool):
    """
    계산기 도구
    
    기본적인 수학 연산(+, -, *, /)을 수행하는 도구입니다.
    """
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name="calculator",
            version="1.0.0",
            description="기본적인 수학 연산(덧셈, 뺄셈, 곱셈, 나눗셈)을 수행하는 계산기 도구입니다.",
            category=ToolCategory.PRODUCTIVITY,
            author="Personal AI Assistant",
            parameters=[
                ToolParameter(
                    name="operation",
                    type=ParameterType.STRING,
                    description="수행할 연산 (+, -, *, /)",
                    required=True,
                    choices=["+", "-", "*", "/"]
                ),
                ToolParameter(
                    name="a",
                    type=ParameterType.NUMBER,
                    description="첫 번째 숫자",
                    required=True
                ),
                ToolParameter(
                    name="b",
                    type=ParameterType.NUMBER,
                    description="두 번째 숫자",
                    required=True
                ),
                ToolParameter(
                    name="precision",
                    type=ParameterType.INTEGER,
                    description="결과의 소수점 자릿수",
                    required=False,
                    default=2,
                    min_value=0,
                    max_value=10
                )
            ],
            tags=["math", "calculation", "arithmetic", "numbers"],
            requires_auth=False,
            timeout=5
        )
    
    async def _initialize(self) -> None:
        """도구 초기화"""
        logger.info("Calculator 도구 초기화 완료")
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        계산 실행
        
        Args:
            parameters: 실행 매개변수
                - operation (str): 연산자 (+, -, *, /)
                - a (float): 첫 번째 숫자
                - b (float): 두 번째 숫자
                - precision (int, optional): 소수점 자릿수
                
        Returns:
            실행 결과
        """
        try:
            # 매개변수 추출
            operation = parameters["operation"]
            a = float(parameters["a"])
            b = float(parameters["b"])
            precision = parameters.get("precision", 2)
            
            # 연산 수행
            result = None
            operation_name = ""
            
            if operation == "+":
                result = a + b
                operation_name = "덧셈"
            elif operation == "-":
                result = a - b
                operation_name = "뺄셈"
            elif operation == "*":
                result = a * b
                operation_name = "곱셈"
            elif operation == "/":
                if b == 0:
                    return ToolResult(
                        status=ExecutionStatus.ERROR,
                        error_message="0으로 나눌 수 없습니다"
                    )
                result = a / b
                operation_name = "나눗셈"
            else:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"지원하지 않는 연산자입니다: {operation}"
                )
            
            # 결과 반올림
            rounded_result = round(result, precision)
            
            # 결과 데이터 생성
            result_data = {
                "operation": operation,
                "operation_name": operation_name,
                "operand_a": a,
                "operand_b": b,
                "result": rounded_result,
                "precision": precision,
                "expression": f"{a} {operation} {b} = {rounded_result}",
                "calculated_at": datetime.now().isoformat()
            }
            
            logger.info(f"Calculator 도구 실행 완료: {a} {operation} {b} = {rounded_result}")
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data=result_data,
                metadata={
                    "tool_name": "calculator",
                    "operation_type": operation_name,
                    "result_value": rounded_result
                }
            )
        
        except ValueError as e:
            logger.error(f"Calculator 도구 매개변수 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"숫자 변환 오류: {str(e)}"
            )
        
        except Exception as e:
            logger.error(f"Calculator 도구 실행 실패: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"계산 중 오류 발생: {str(e)}"
            )
