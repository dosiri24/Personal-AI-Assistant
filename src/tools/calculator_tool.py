"""
계산기 도구

수학적 계산을 수행하는 MCP 도구입니다.
"""

import asyncio
import ast
import operator
import math
from typing import Dict, Any, List, Union

from ..mcp.base_tool import BaseTool, ToolResult, ExecutionStatus
from ..mcp.base_tool import ToolMetadata, ToolParameter, ParameterType, ToolCategory
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CalculatorTool(BaseTool):
    """수학적 계산을 수행하는 도구"""
    
    def __init__(self):
        super().__init__()
        self._metadata = ToolMetadata(
            name="calculator",
            version="1.0.0",
            description="수학적 계산을 안전하게 수행합니다",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(
                    name="expression",
                    type=ParameterType.STRING,
                    description="계산할 수학 표현식 (예: '2 + 3 * 4', 'sqrt(16)', 'sin(pi/2)')",
                    required=True
                )
            ]
        )
        
        # 안전한 연산자와 함수들
        self._safe_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        self._safe_functions = {
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'sum': sum,
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'asin': math.asin,
            'acos': math.acos,
            'atan': math.atan,
            'sinh': math.sinh,
            'cosh': math.cosh,
            'tanh': math.tanh,
            'log': math.log,
            'log10': math.log10,
            'log2': math.log2,
            'exp': math.exp,
            'ceil': math.ceil,
            'floor': math.floor,
            'degrees': math.degrees,
            'radians': math.radians,
            'factorial': math.factorial,
            'gcd': math.gcd,
        }
        
        self._safe_constants = {
            'pi': math.pi,
            'e': math.e,
            'tau': math.tau,
            'inf': math.inf,
        }

    async def execute(self, **kwargs) -> ToolResult:
        """계산 실행"""
        try:
            expression = kwargs.get('expression', '').strip()
            
            if not expression:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    data={"error": "계산할 표현식이 필요합니다"}
                )
            
            logger.info(f"계산 요청: {expression}")
            
            # 표현식 파싱 및 계산
            result = await self._safe_evaluate(expression)
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "expression": expression,
                    "result": result,
                    "type": type(result).__name__
                },
                message=f"계산 결과: {expression} = {result}"
            )
            
        except Exception as e:
            logger.error(f"계산 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                data={"error": str(e)},
                message=f"계산 오류: {str(e)}"
            )

    async def _safe_evaluate(self, expression: str) -> Union[int, float]:
        """안전한 표현식 평가"""
        try:
            # AST 파싱
            node = ast.parse(expression, mode='eval')
            return self._eval_node(node.body)
        except Exception as e:
            raise ValueError(f"잘못된 표현식: {str(e)}")

    def _eval_node(self, node) -> Union[int, float]:
        """AST 노드 평가"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):  # Python 3.8 이하 호환성
            return node.n
        elif isinstance(node, ast.Name):
            if node.id in self._safe_constants:
                return self._safe_constants[node.id]
            else:
                raise ValueError(f"허용되지 않은 변수: {node.id}")
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if type(node.op) in self._safe_operators:
                return self._safe_operators[type(node.op)](left, right)
            else:
                raise ValueError(f"허용되지 않은 연산자: {type(node.op)}")
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            if type(node.op) in self._safe_operators:
                return self._safe_operators[type(node.op)](operand)
            else:
                raise ValueError(f"허용되지 않은 단항 연산자: {type(node.op)}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in self._safe_functions:
                func = self._safe_functions[node.func.id]
                args = [self._eval_node(arg) for arg in node.args]
                return func(*args)
            else:
                raise ValueError(f"허용되지 않은 함수: {getattr(node.func, 'id', 'unknown')}")
        elif isinstance(node, ast.Compare):
            # 비교 연산은 지원하지 않음
            raise ValueError("비교 연산은 지원되지 않습니다")
        else:
            raise ValueError(f"허용되지 않은 노드 타입: {type(node)}")

    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        return self._metadata


# 편의를 위한 팩토리 함수
def create_calculator_tool() -> CalculatorTool:
    """CalculatorTool 인스턴스 생성"""
    return CalculatorTool()


# 직접 실행 테스트
async def main():
    """테스트용 메인 함수"""
    tool = CalculatorTool()
    
    test_expressions = [
        "2 + 3",
        "10 * 5 - 2",
        "sqrt(16)",
        "sin(pi/2)",
        "2 ** 3",
        "log(e)",
        "abs(-5)",
    ]
    
    for expr in test_expressions:
        result = await tool.execute(expression=expr)
        print(f"{expr} -> {result}")


if __name__ == "__main__":
    asyncio.run(main())
