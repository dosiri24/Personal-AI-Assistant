"""
의존성 주입 컨테이너
Step 9.1 - 컴포넌트 통합의 핵심 구성 요소
"""

from typing import Dict, Any, Type, TypeVar, Callable, Optional
from abc import ABC, abstractmethod
import logging
from enum import Enum

T = TypeVar('T')

class ServiceScope(Enum):
    """서비스 생명주기 범위"""
    SINGLETON = "singleton"  # 앱 전체에서 하나의 인스턴스
    TRANSIENT = "transient"  # 요청할 때마다 새 인스턴스
    SCOPED = "scoped"       # 특정 범위 내에서 하나의 인스턴스

class ServiceRegistration:
    """서비스 등록 정보"""
    
    def __init__(
        self, 
        service_type: Type,
        implementation: Optional[Type],
        scope: ServiceScope = ServiceScope.SINGLETON,
        factory: Optional[Callable] = None
    ):
        self.service_type = service_type
        self.implementation = implementation
        self.scope = scope
        self.factory = factory
        self.instance: Optional[Any] = None

class DIContainer:
    """의존성 주입 컨테이너"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceRegistration] = {}
        self._logger = logging.getLogger(__name__)
        self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
        
    def register(
        self, 
        service_type: Type[T], 
        implementation: Type[T],
        scope: ServiceScope = ServiceScope.SINGLETON
    ) -> 'DIContainer':
        """서비스 등록"""
        registration = ServiceRegistration(service_type, implementation, scope)
        self._services[service_type] = registration
        self._logger.info(f"Registered service: {service_type.__name__} -> {implementation.__name__}")
        return self
    
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        scope: ServiceScope = ServiceScope.SINGLETON
    ) -> 'DIContainer':
        """팩토리 함수로 서비스 등록"""
        registration = ServiceRegistration(service_type, None, scope, factory)
        self._services[service_type] = registration
        self._logger.info(f"Registered factory for service: {service_type.__name__}")
        return self
    
    def register_instance(
        self,
        service_type: Type[T],
        instance: T
    ) -> 'DIContainer':
        """이미 생성된 인스턴스 등록"""
        registration = ServiceRegistration(service_type, type(instance), ServiceScope.SINGLETON)
        registration.instance = instance
        self._services[service_type] = registration
        self._logger.info(f"Registered instance for service: {service_type.__name__}")
        return self
    
    def resolve(self, service_type: Type[T], scope_id: Optional[str] = None) -> T:
        """서비스 해결 (인스턴스 가져오기)"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} is not registered")
        
        registration = self._services[service_type]
        
        # Singleton 처리
        if registration.scope == ServiceScope.SINGLETON:
            if registration.instance is None:
                registration.instance = self._create_instance(registration)
            return registration.instance  # type: ignore
        
        # Scoped 처리
        elif registration.scope == ServiceScope.SCOPED:
            if scope_id is None:
                scope_id = "default"
            
            if scope_id not in self._scoped_instances:
                self._scoped_instances[scope_id] = {}
            
            if service_type not in self._scoped_instances[scope_id]:
                instance = self._create_instance(registration)
                self._scoped_instances[scope_id][service_type] = instance
            
            return self._scoped_instances[scope_id][service_type]
        
        # Transient 처리
        else:
            return self._create_instance(registration)
    
    def _create_instance(self, registration: ServiceRegistration) -> Any:
        """인스턴스 생성"""
        try:
            if registration.factory:
                return registration.factory()
            
            if registration.implementation is None:
                raise ValueError("No implementation or factory provided")
            
            # 생성자 의존성 주입
            constructor = registration.implementation.__init__
            if hasattr(constructor, '__annotations__'):
                annotations = constructor.__annotations__
                kwargs = {}
                
                for param_name, param_type in annotations.items():
                    if param_name == 'return':
                        continue
                    
                    if param_type in self._services:
                        kwargs[param_name] = self.resolve(param_type)
                
                return registration.implementation(**kwargs)
            else:
                return registration.implementation()
                
        except Exception as e:
            self._logger.error(f"Failed to create instance of {registration.service_type.__name__}: {e}")
            raise
    
    def clear_scope(self, scope_id: str):
        """특정 범위의 인스턴스들 정리"""
        if scope_id in self._scoped_instances:
            del self._scoped_instances[scope_id]
            self._logger.info(f"Cleared scope: {scope_id}")
    
    def is_registered(self, service_type: Type) -> bool:
        """서비스 등록 여부 확인"""
        return service_type in self._services
    
    def get_registered_services(self) -> Dict[Type, ServiceRegistration]:
        """등록된 서비스 목록 반환"""
        return self._services.copy()

class ComponentManager:
    """컴포넌트 관리자 - 모든 시스템 컴포넌트의 생명주기 관리"""
    
    def __init__(self, container: DIContainer):
        self.container = container
        self._logger = logging.getLogger(__name__)
        self._initialized_components: Dict[Type, Any] = {}
    
    async def initialize_all_components(self):
        """모든 등록된 컴포넌트 초기화"""
        for service_type, registration in self.container.get_registered_services().items():
            if registration.implementation and hasattr(registration.implementation, 'initialize'):
                try:
                    component = self.container.resolve(service_type)
                    await component.initialize()
                    self._initialized_components[service_type] = component
                    self._logger.info(f"Initialized component: {service_type.__name__}")
                except Exception as e:
                    self._logger.error(f"Failed to initialize component {service_type.__name__}: {e}")
                    raise
    
    async def shutdown_all_components(self):
        """모든 컴포넌트 종료"""
        for service_type, component in self._initialized_components.items():
            try:
                await component.stop()
                self._logger.info(f"Shutdown component: {service_type.__name__}")
            except Exception as e:
                self._logger.error(f"Failed to shutdown component {service_type.__name__}: {e}")
        
        self._initialized_components.clear()
    
    def get_component(self, component_type: Type[T]) -> T:
        """컴포넌트 인스턴스 가져오기"""
        return self.container.resolve(component_type)

# 글로벌 컨테이너 인스턴스
_container: Optional[DIContainer] = None
_component_manager: Optional[ComponentManager] = None

def get_container() -> DIContainer:
    """글로벌 DI 컨테이너 가져오기"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container

def get_component_manager() -> ComponentManager:
    """글로벌 컴포넌트 매니저 가져오기"""
    global _component_manager, _container
    if _component_manager is None:
        if _container is None:
            _container = DIContainer()
        _component_manager = ComponentManager(_container)
    return _component_manager

def register_default_services():
    """기본 서비스들 등록"""
    container = get_container()
    
    # 기본 구현체들을 여기서 등록할 수 있습니다
    # 예: container.register(AIEngineInterface, ConcreteAIEngine)
    
    logging.getLogger(__name__).info("Default services registered")

# 컨테이너 초기화
register_default_services()
