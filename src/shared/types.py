"""
공통 타입 정의

프로젝트 전반에서 사용되는 공통 타입들을 정의합니다.
"""

from typing import Dict, List, Optional, Any, Union, Protocol
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Priority(Enum):
    """우선순위"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"


class Status(Enum):
    """작업 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ExecutionResult:
    """도구 실행 결과"""
    success: bool
    message: str
    data: Optional[Any] = None
    execution_time: float = 0.0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "execution_time": self.execution_time,
            "errors": self.errors
        }


@dataclass
class ToolMetadata:
    """도구 메타데이터"""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: str = "general"
    version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category,
            "version": self.version
        }


class LLMProvider(Protocol):
    """LLM 프로바이더 인터페이스"""
    
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> str:
        """응답 생성"""
        ...
    
    async def generate_structured_response(
        self, 
        messages: List[Dict[str, str]], 
        schema: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """구조화된 응답 생성"""
        ...


class ToolInterface(Protocol):
    """도구 인터페이스"""
    
    @property
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        ...
    
    async def execute(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """도구 실행"""
        ...
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """매개변수 검증"""
        ...


class ToolRegistry(Protocol):
    """도구 레지스트리 인터페이스"""
    
    async def register_tool(self, tool: ToolInterface) -> bool:
        """도구 등록"""
        ...
    
    async def get_tool(self, name: str) -> Optional[ToolInterface]:
        """도구 조회"""
        ...
    
    async def list_tools(self) -> List[str]:
        """도구 목록"""
        ...


class AgentInterface(Protocol):
    """AI 에이전트 인터페이스"""
    
    async def process_request(
        self, 
        user_input: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """요청 처리"""
        ...
    
    async def plan_actions(
        self, 
        goal: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """행동 계획 수립"""
        ...