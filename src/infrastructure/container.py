"""
의존성 주입 컨테이너

시스템 전반의 의존성을 관리하는 간단한 DI 컨테이너입니다.
"""

from typing import Dict, Any, TypeVar, Type, Optional, Callable
from ..shared.interfaces import *

T = TypeVar('T')


class DIContainer:
    """간단한 의존성 주입 컨테이너"""
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
        self._singletons: Dict[Type, Any] = {}
    
    def register_singleton(self, interface: Type[T], instance: T) -> None:
        """싱글톤 인스턴스 등록"""
        self._singletons[interface] = instance
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """팩토리 함수 등록"""
        self._factories[interface] = factory
    
    def register_service(self, interface: Type[T], implementation: Type[T]) -> None:
        """서비스 구현체 등록"""
        self._services[interface] = implementation
    
    def get(self, interface: Type[T]) -> T:
        """서비스 인스턴스 조회"""
        # 싱글톤 먼저 확인
        if interface in self._singletons:
            return self._singletons[interface]
        
        # 팩토리 함수 사용
        if interface in self._factories:
            instance = self._factories[interface]()
            return instance
        
        # 등록된 구현체 인스턴스화
        if interface in self._services:
            implementation = self._services[interface]
            instance = implementation()
            return instance
        
        raise ValueError(f"No registration found for {interface}")
    
    def get_optional(self, interface: Type[T]) -> Optional[T]:
        """서비스 인스턴스 조회 (옵션)"""
        try:
            return self.get(interface)
        except ValueError:
            return None


# 전역 컨테이너 인스턴스
_container = DIContainer()


def get_container() -> DIContainer:
    """전역 DI 컨테이너 반환"""
    return _container


def setup_container():
    """컨테이너 설정"""
    from ..ai_engine.llm_provider import GeminiProvider
    from ..tools.registry import ToolRegistry  
    from ..tools.base_tool import ToolExecutor
    from ..infrastructure.config.config import ConfigProvider
    
    # 기본 서비스들 등록
    container = get_container()
    
    # LLM 프로바이더 (싱글톤)
    llm_provider = GeminiProvider()
    container.register_singleton(ILLMProvider, llm_provider)
    
    # 도구 레지스트리 (싱글톤)
    tool_registry = ToolRegistry()
    container.register_singleton(IToolRegistry, tool_registry)
    
    # 도구 실행기 (팩토리)
    container.register_factory(
        IToolExecutor,
        lambda: ToolExecutor(container.get(IToolRegistry))
    )
    
    # 설정 프로바이더 (싱글톤)
    config_provider = ConfigProvider()
    container.register_singleton(IConfigProvider, config_provider)


# 편의 함수들
def get_llm_provider() -> ILLMProvider:
    """LLM 프로바이더 조회"""
    return get_container().get(ILLMProvider)


def get_tool_registry() -> IToolRegistry:
    """도구 레지스트리 조회"""
    return get_container().get(IToolRegistry)


def get_tool_executor() -> IToolExecutor:
    """도구 실행기 조회"""
    return get_container().get(IToolExecutor)


def get_config_provider() -> IConfigProvider:
    """설정 프로바이더 조회"""
    return get_container().get(IConfigProvider)