"""
도구 기본 클래스

모든 도구가 상속받아야 하는 기본 클래스와 인터페이스를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import asyncio
import time

from ..shared.interfaces import ITool
from ..shared.types import ExecutionResult, ToolMetadata
from ..shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolParameter:
    """도구 매개변수 정의"""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type, 
            "description": self.description,
            "required": self.required,
            "default": self.default
        }


class BaseTool(ITool, ABC):
    """
    도구 기본 클래스
    
    모든 도구는 이 클래스를 상속받아야 합니다.
    """
    
    def __init__(self, name: str, description: str, category: str = "general"):
        self._name = name
        self._description = description
        self._category = category
        self._version = "1.0.0"
        self._parameters: List[ToolParameter] = []
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        return ToolMetadata(
            name=self._name,
            description=self._description,
            parameters={p.name: p.to_dict() for p in self._parameters},
            category=self._category,
            version=self._version
        )
    
    def add_parameter(
        self,
        name: str,
        param_type: str,
        description: str,
        required: bool = True,
        default: Any = None
    ) -> None:
        """매개변수 추가"""
        param = ToolParameter(
            name=name,
            type=param_type,
            description=description,
            required=required,
            default=default
        )
        self._parameters.append(param)
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """매개변수 검증"""
        for param in self._parameters:
            if param.required and param.name not in parameters:
                return False
            
            if param.name in parameters:
                # 기본적인 타입 검증
                value = parameters[param.name]
                if not self._validate_parameter_type(value, param.type):
                    return False
        
        return True
    
    def _validate_parameter_type(self, value: Any, expected_type: str) -> bool:
        """매개변수 타입 검증"""
        type_mapping = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict
        }
        
        if expected_type in type_mapping:
            return isinstance(value, type_mapping[expected_type])
        
        return True  # 알 수 없는 타입은 통과
    
    async def execute(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """도구 실행 (템플릿 메소드)"""
        start_time = time.time()
        
        try:
            # 매개변수 검증
            if not await self.validate_parameters(parameters):
                return ExecutionResult(
                    success=False,
                    message="매개변수 검증 실패",
                    execution_time=time.time() - start_time,
                    errors=["Invalid parameters"]
                )
            
            # 실제 실행
            result = await self._execute_impl(parameters)
            result.execution_time = time.time() - start_time
            
            return result
            
        except Exception as e:
            logger.error(f"도구 '{self._name}' 실행 중 오류 발생: {str(e)}")
            return ExecutionResult(
                success=False,
                message=f"실행 중 오류 발생: {str(e)}",
                execution_time=time.time() - start_time,
                errors=[str(e)]
            )
    
    @abstractmethod
    async def _execute_impl(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """실제 도구 실행 로직 (서브클래스에서 구현)"""
        pass
    
    async def initialize(self) -> None:
        """도구 초기화"""
        logger.info(f"도구 '{self._name}' 초기화")
    
    async def cleanup(self) -> None:
        """리소스 정리"""
        logger.info(f"도구 '{self._name}' 정리")


class SimpleToolExecutor:
    """
    간단한 도구 실행기
    
    도구 등록과 실행을 담당합니다.
    """
    
    def __init__(self):
        self._tools: Dict[str, ITool] = {}
    
    async def register_tool(self, tool: ITool) -> bool:
        """도구 등록"""
        try:
            await tool.initialize()
            self._tools[tool.metadata.name] = tool
            logger.info(f"도구 등록: {tool.metadata.name}")
            return True
        except Exception as e:
            logger.error(f"도구 등록 실패 '{tool.metadata.name}': {str(e)}")
            return False
    
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> ExecutionResult:
        """도구 실행"""
        if tool_name not in self._tools:
            return ExecutionResult(
                success=False,
                message=f"도구를 찾을 수 없음: {tool_name}",
                errors=[f"Tool '{tool_name}' not found"]
            )
        
        tool = self._tools[tool_name]
        return await tool.execute(parameters)
    
    async def list_tools(self) -> List[str]:
        """등록된 도구 목록"""
        return list(self._tools.keys())
    
    async def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """도구 메타데이터 조회"""
        if tool_name in self._tools:
            return self._tools[tool_name].metadata
        return None
    
    async def cleanup(self) -> None:
        """모든 도구 정리"""
        for tool in self._tools.values():
            try:
                await tool.cleanup()
            except Exception as e:
                logger.error(f"도구 정리 중 오류: {str(e)}")
        
        self._tools.clear()