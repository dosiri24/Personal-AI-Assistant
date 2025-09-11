"""
시스템 인터페이스 정의

시스템의 주요 컴포넌트들 간의 인터페이스를 정의합니다.
의존성 역전 원칙을 적용하여 각 레이어의 책임을 명확히 합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, AsyncGenerator
from .types import ExecutionResult, ToolMetadata, Priority, Status


class ILLMProvider(ABC):
    """LLM 프로바이더 인터페이스"""
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> str:
        """텍스트 응답 생성"""
        pass
    
    @abstractmethod
    async def generate_structured_response(
        self, 
        messages: List[Dict[str, str]], 
        schema: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """구조화된 응답 생성"""
        pass


class ITool(ABC):
    """도구 인터페이스"""
    
    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata:
        """도구 메타데이터"""
        pass
    
    @abstractmethod
    async def execute(self, parameters: Dict[str, Any]) -> ExecutionResult:
        """도구 실행"""
        pass
    
    @abstractmethod
    async def validate_parameters(self, parameters: Dict[str, Any]) -> bool:
        """매개변수 검증"""
        pass
    
    async def initialize(self) -> None:
        """도구 초기화 (옵션)"""
        pass
    
    async def cleanup(self) -> None:
        """리소스 정리 (옵션)"""
        pass


class IToolRegistry(ABC):
    """도구 레지스트리 인터페이스"""
    
    @abstractmethod
    async def register_tool(self, tool: ITool) -> bool:
        """도구 등록"""
        pass
    
    @abstractmethod
    async def unregister_tool(self, name: str) -> bool:
        """도구 등록 해제"""
        pass
    
    @abstractmethod
    async def get_tool(self, name: str) -> Optional[ITool]:
        """도구 조회"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[str]:
        """등록된 도구 목록"""
        pass
    
    @abstractmethod
    async def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        """도구 메타데이터 조회"""
        pass


class IToolExecutor(ABC):
    """도구 실행기 인터페이스"""
    
    @abstractmethod
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> ExecutionResult:
        """도구 실행"""
        pass
    
    @abstractmethod
    async def execute_with_retry(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        max_retries: int = 3
    ) -> ExecutionResult:
        """재시도와 함께 도구 실행"""
        pass


class IAgent(ABC):
    """AI 에이전트 인터페이스"""
    
    @abstractmethod
    async def process_request(
        self, 
        user_input: str, 
        user_id: str = "default",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """사용자 요청 처리"""
        pass
    
    @abstractmethod
    async def plan_actions(
        self, 
        goal: str, 
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """목표 달성을 위한 행동 계획 수립"""
        pass


class IMemorySystem(ABC):
    """메모리 시스템 인터페이스"""
    
    @abstractmethod
    async def store_conversation(
        self, 
        user_id: str, 
        conversation: List[Dict[str, Any]]
    ) -> None:
        """대화 저장"""
        pass
    
    @abstractmethod
    async def retrieve_conversation_history(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """대화 기록 조회"""
        pass
    
    @abstractmethod
    async def search_relevant_context(
        self, 
        query: str, 
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """관련 컨텍스트 검색"""
        pass


class IConfigProvider(ABC):
    """설정 제공자 인터페이스"""
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 조회"""
        pass
    
    @abstractmethod
    def get_section(self, section: str) -> Dict[str, Any]:
        """설정 섹션 조회"""
        pass
    
    @abstractmethod
    def reload(self) -> None:
        """설정 다시 로드"""
        pass


class IEventBus(ABC):
    """이벤트 버스 인터페이스"""
    
    @abstractmethod
    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """이벤트 발행"""
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        event_type: str, 
        handler: callable
    ) -> None:
        """이벤트 구독"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, event_type: str, handler: callable) -> None:
        """구독 해제"""
        pass