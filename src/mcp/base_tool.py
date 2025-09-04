"""
MCP 도구 인터페이스 추상화

모든 MCP 도구들이 구현해야 하는 기본 인터페이스와 
공통 데이터 구조를 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Type
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ParameterType(Enum):
    """매개변수 타입"""
    STRING = "string"
    INTEGER = "integer" 
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolCategory(Enum):
    """도구 카테고리"""
    PRODUCTIVITY = "productivity"  # 생산성 (Notion, 캘린더 등)
    COMMUNICATION = "communication"  # 커뮤니케이션 (이메일, 메시지 등)
    FILE_MANAGEMENT = "file_management"  # 파일 관리
    WEB_SCRAPING = "web_scraping"  # 웹 스크래핑
    AUTOMATION = "automation"  # 자동화
    SYSTEM = "system"  # 시스템 작업
    DATA_ANALYSIS = "data_analysis"  # 데이터 분석
    CREATIVE = "creative"  # 창작 도구


class ExecutionStatus(Enum):
    """실행 상태"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ToolParameter:
    """도구 매개변수 정의"""
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Optional[Any] = None
    choices: Optional[List[Any]] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None  # 정규식 패턴
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "name": self.name,
            "type": self.type.value,
            "description": self.description,
            "required": self.required
        }
        
        if self.default is not None:
            result["default"] = self.default
        if self.choices is not None:
            result["choices"] = self.choices
        if self.min_value is not None:
            result["min_value"] = self.min_value
        if self.max_value is not None:
            result["max_value"] = self.max_value
        if self.pattern is not None:
            result["pattern"] = self.pattern
            
        return result
    
    def validate(self, value: Any) -> bool:
        """매개변수 값 검증"""
        if value is None:
            return not self.required
        
        # 타입 검증
        if self.type == ParameterType.STRING and not isinstance(value, str):
            return False
        elif self.type == ParameterType.INTEGER and not isinstance(value, int):
            return False
        elif self.type == ParameterType.NUMBER and not isinstance(value, (int, float)):
            return False
        elif self.type == ParameterType.BOOLEAN and not isinstance(value, bool):
            return False
        elif self.type == ParameterType.ARRAY and not isinstance(value, list):
            return False
        elif self.type == ParameterType.OBJECT and not isinstance(value, dict):
            return False
        
        # 선택지 검증
        if self.choices and value not in self.choices:
            return False
        
        # 범위 검증
        if self.type in [ParameterType.INTEGER, ParameterType.NUMBER]:
            if self.min_value is not None and value < self.min_value:
                return False
            if self.max_value is not None and value > self.max_value:
                return False
        
        # 패턴 검증 (문자열의 경우)
        if self.type == ParameterType.STRING and self.pattern:
            import re
            if not re.match(self.pattern, value):
                return False
        
        return True


@dataclass
class ToolMetadata:
    """도구 메타데이터"""
    name: str
    version: str
    description: str
    category: ToolCategory
    author: str = "Personal AI Assistant"
    parameters: List[ToolParameter] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    requires_auth: bool = False
    timeout: int = 30  # 기본 타임아웃 30초
    rate_limit: Optional[int] = None  # 분당 호출 제한
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "author": self.author,
            "parameters": [param.to_dict() for param in self.parameters],
            "tags": self.tags,
            "requires_auth": self.requires_auth,
            "timeout": self.timeout,
            "rate_limit": self.rate_limit
        }


@dataclass  
class ToolResult:
    """도구 실행 결과"""
    status: ExecutionStatus
    data: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time: Optional[float] = None  # 실행 시간 (초)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = {
            "status": self.status.value,
            "data": self.data,
            "metadata": self.metadata
        }
        
        if self.error_message:
            result["error_message"] = self.error_message
        if self.execution_time is not None:
            result["execution_time"] = self.execution_time
            
        return result
    
    @property
    def is_success(self) -> bool:
        """성공 여부"""
        return self.status == ExecutionStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        """에러 여부"""
        return self.status in [ExecutionStatus.ERROR, ExecutionStatus.TIMEOUT]


class BaseTool(ABC):
    """
    모든 MCP 도구의 기본 클래스
    
    모든 도구는 이 클래스를 상속받아 구현해야 합니다.
    """
    
    def __init__(self):
        self._metadata: Optional[ToolMetadata] = None
        self._initialized = False
        
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터 반환"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        도구 실행
        
        Args:
            parameters: 실행 매개변수
            
        Returns:
            실행 결과
        """
        pass
    
    async def initialize(self) -> bool:
        """
        도구 초기화
        
        Returns:
            초기화 성공 여부
        """
        try:
            await self._initialize()
            self._initialized = True
            logger.info(f"도구 초기화 완료: {self.metadata.name}")
            return True
        except Exception as e:
            logger.error(f"도구 초기화 실패: {self.metadata.name} - {e}")
            return False
    
    async def _initialize(self) -> None:
        """
        실제 초기화 로직 (하위 클래스에서 구현)
        
        기본 구현은 아무것도 하지 않음
        """
        pass
    
    async def cleanup(self) -> None:
        """
        도구 정리 작업
        
        리소스 해제, 연결 종료 등을 수행합니다.
        """
        try:
            await self._cleanup()
            logger.info(f"도구 정리 완료: {self.metadata.name}")
        except Exception as e:
            logger.error(f"도구 정리 실패: {self.metadata.name} - {e}")
    
    async def _cleanup(self) -> None:
        """
        실제 정리 로직 (하위 클래스에서 구현)
        
        기본 구현은 아무것도 하지 않음
        """
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> List[str]:
        """
        매개변수 검증
        
        Args:
            parameters: 검증할 매개변수
            
        Returns:
            검증 에러 메시지 리스트 (빈 리스트면 성공)
        """
        errors = []
        
        # 필수 매개변수 검사
        required_params = {p.name for p in self.metadata.parameters if p.required}
        provided_params = set(parameters.keys())
        missing_params = required_params - provided_params
        
        if missing_params:
            errors.append(f"필수 매개변수가 누락되었습니다: {', '.join(missing_params)}")
        
        # 각 매개변수 검증
        param_map = {p.name: p for p in self.metadata.parameters}
        
        for param_name, param_value in parameters.items():
            if param_name not in param_map:
                errors.append(f"알 수 없는 매개변수입니다: {param_name}")
                continue
            
            param_def = param_map[param_name]
            if not param_def.validate(param_value):
                errors.append(f"매개변수 '{param_name}'의 값이 유효하지 않습니다: {param_value}")
        
        return errors
    
    async def safe_execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """
        안전한 실행 (에러 처리 포함)
        
        Args:
            parameters: 실행 매개변수
            
        Returns:
            실행 결과
        """
        start_time = datetime.now()
        
        try:
            # 초기화 검사
            if not self._initialized:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="도구가 초기화되지 않았습니다"
                )
            
            # 매개변수 검증
            validation_errors = self.validate_parameters(parameters)
            if validation_errors:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message=f"매개변수 검증 실패: {'; '.join(validation_errors)}"
                )
            
            # 실행
            result = await self.execute(parameters)
            
            # 실행 시간 계산
            execution_time = (datetime.now() - start_time).total_seconds()
            result.execution_time = execution_time
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"도구 실행 중 예외 발생: {self.metadata.name} - {e}")
            
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"실행 중 예외 발생: {str(e)}",
                execution_time=execution_time
            )
    
    def get_usage_example(self) -> Dict[str, Any]:
        """
        사용 예제 반환
        
        Returns:
            예제 매개변수
        """
        example = {}
        
        for param in self.metadata.parameters:
            if param.default is not None:
                example[param.name] = param.default
            elif param.type == ParameterType.STRING:
                example[param.name] = f"예제 {param.name}"
            elif param.type == ParameterType.INTEGER:
                example[param.name] = 1
            elif param.type == ParameterType.NUMBER:
                example[param.name] = 1.0
            elif param.type == ParameterType.BOOLEAN:
                example[param.name] = True
            elif param.type == ParameterType.ARRAY:
                example[param.name] = ["예제", "배열"]
            elif param.type == ParameterType.OBJECT:
                example[param.name] = {"예제": "객체"}
        
        return example
    
    def __str__(self) -> str:
        """문자열 표현"""
        return f"<{self.__class__.__name__}: {self.metadata.name} v{self.metadata.version}>"
    
    def __repr__(self) -> str:
        """개발자용 문자열 표현"""
        return self.__str__()
