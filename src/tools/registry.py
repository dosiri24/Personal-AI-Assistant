"""
MCP 도구 레지스트리

도구들의 등록, 발견, 관리를 담당하는 중앙 레지스트리입니다.
런타임에 도구 추가/제거 및 메타데이터 관리를 지원합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Set, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
import importlib
import inspect
from pathlib import Path

from .base_tool import BaseTool, ToolMetadata, ToolCategory, ExecutionStatus

logger = logging.getLogger(__name__)


@dataclass
class ToolRegistration:
    """도구 등록 정보"""
    tool_class: Type[BaseTool]
    instance: Optional[BaseTool] = None
    registered_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    usage_count: int = 0
    enabled: bool = True
    
    @property
    def is_initialized(self) -> bool:
        """초기화 여부"""
        return self.instance is not None and self.instance._initialized


class ToolRegistry:
    """
    도구 레지스트리
    
    모든 MCP 도구들을 중앙에서 관리합니다.
    """
    
    def __init__(self):
        self._tools: Dict[str, ToolRegistration] = {}
        self._categories: Dict[ToolCategory, Set[str]] = {}
        self._tags: Dict[str, Set[str]] = {}
        self._listeners: List[Callable] = []
        self._lock = asyncio.Lock()
        
    async def register_tool(self, tool_class: Type[BaseTool], 
                           auto_initialize: bool = True) -> bool:
        """
        도구 등록
        
        Args:
            tool_class: 등록할 도구 클래스
            auto_initialize: 자동 초기화 여부
            
        Returns:
            등록 성공 여부
        """
        async with self._lock:
            try:
                # 임시 인스턴스 생성하여 메타데이터 확인
                temp_instance = tool_class()
                metadata = temp_instance.metadata
                tool_name = metadata.name
                
                # 이미 등록된 도구인지 확인
                if tool_name in self._tools:
                    logger.warning(f"도구가 이미 등록되어 있습니다: {tool_name}")
                    return False
                
                # 등록 정보 생성
                registration = ToolRegistration(tool_class=tool_class)
                
                # 자동 초기화
                if auto_initialize:
                    registration.instance = temp_instance
                    if not await temp_instance.initialize():
                        logger.error(f"도구 초기화 실패: {tool_name}")
                        return False
                else:
                    registration.instance = None
                
                # 레지스트리에 등록
                self._tools[tool_name] = registration
                
                # 카테고리별 인덱싱
                if metadata.category not in self._categories:
                    self._categories[metadata.category] = set()
                self._categories[metadata.category].add(tool_name)
                
                # 태그별 인덱싱
                for tag in metadata.tags:
                    if tag not in self._tags:
                        self._tags[tag] = set()
                    self._tags[tag].add(tool_name)
                
                logger.info(f"도구 등록 완료: {tool_name} (카테고리: {metadata.category.value})")
                
                # 리스너에게 알림
                await self._notify_listeners("tool_registered", tool_name, metadata)
                
                return True
                
            except Exception as e:
                logger.error(f"도구 등록 실패: {e}")
                return False

    async def register_tool_instance(self, instance: BaseTool) -> bool:
        """이미 생성된 도구 인스턴스를 레지스트리에 등록

        Apple MCP와 같이 생성자 인자가 필요한 도구들을 주입 방식으로 등록할 때 사용합니다.
        """
        async with self._lock:
            try:
                metadata = instance.metadata
                tool_name = metadata.name

                if tool_name in self._tools:
                    logger.warning(f"도구가 이미 등록되어 있습니다: {tool_name}")
                    return False

                # 초기화 보장
                if not instance._initialized:
                    ok = await instance.initialize()
                    if not ok:
                        logger.error(f"도구 초기화 실패: {tool_name}")
                        return False

                registration = ToolRegistration(tool_class=instance.__class__, instance=instance)
                self._tools[tool_name] = registration

                # 카테고리/태그 인덱싱
                if metadata.category not in self._categories:
                    self._categories[metadata.category] = set()
                self._categories[metadata.category].add(tool_name)

                for tag in metadata.tags:
                    if tag not in self._tags:
                        self._tags[tag] = set()
                    self._tags[tag].add(tool_name)

                logger.info(f"도구 인스턴스 등록 완료: {tool_name} (카테고리: {metadata.category.value})")
                await self._notify_listeners("tool_registered", tool_name, metadata)
                return True
            except Exception as e:
                logger.error(f"도구 인스턴스 등록 실패: {e}")
                return False
    
    async def unregister_tool(self, tool_name: str) -> bool:
        """
        도구 등록 해제
        
        Args:
            tool_name: 도구 이름
            
        Returns:
            해제 성공 여부
        """
        async with self._lock:
            if tool_name not in self._tools:
                logger.warning(f"등록되지 않은 도구입니다: {tool_name}")
                return False
            
            registration = self._tools[tool_name]
            
            try:
                # 인스턴스 정리
                if registration.instance:
                    await registration.instance.cleanup()
                
                # 메타데이터 가져오기
                temp_instance = registration.tool_class()
                metadata = temp_instance.metadata
                
                # 카테고리에서 제거
                if metadata.category in self._categories:
                    self._categories[metadata.category].discard(tool_name)
                    if not self._categories[metadata.category]:
                        del self._categories[metadata.category]
                
                # 태그에서 제거
                for tag in metadata.tags:
                    if tag in self._tags:
                        self._tags[tag].discard(tool_name)
                        if not self._tags[tag]:
                            del self._tags[tag]
                
                # 레지스트리에서 제거
                del self._tools[tool_name]
                
                logger.info(f"도구 등록 해제 완료: {tool_name}")
                
                # 리스너에게 알림
                await self._notify_listeners("tool_unregistered", tool_name, metadata)
                
                return True
                
            except Exception as e:
                logger.error(f"도구 등록 해제 실패: {tool_name} - {e}")
                return False
    
    async def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """
        도구 인스턴스 가져오기
        
        Args:
            tool_name: 도구 이름
            
        Returns:
            도구 인스턴스 또는 None
        """
        if tool_name not in self._tools:
            return None
        
        registration = self._tools[tool_name]
        
        # 비활성화된 도구
        if not registration.enabled:
            return None
        
        # 인스턴스가 없으면 생성 및 초기화
        if registration.instance is None:
            try:
                registration.instance = registration.tool_class()
                if not await registration.instance.initialize():
                    logger.error(f"도구 초기화 실패: {tool_name}")
                    return None
            except Exception as e:
                logger.error(f"도구 인스턴스 생성 실패: {tool_name} - {e}")
                return None
        
        # 사용 통계 업데이트
        registration.last_used = datetime.now()
        registration.usage_count += 1
        
        return registration.instance
    
    def get_tool_metadata(self, tool_name: str) -> Optional[ToolMetadata]:
        """
        도구 메타데이터 가져오기
        
        Args:
            tool_name: 도구 이름
            
        Returns:
            도구 메타데이터 또는 None
        """
        if tool_name not in self._tools:
            return None
        
        registration = self._tools[tool_name]
        
        try:
            if registration.instance:
                return registration.instance.metadata
            else:
                # 임시 인스턴스 생성하여 메타데이터 반환
                temp_instance = registration.tool_class()
                return temp_instance.metadata
        except Exception as e:
            logger.error(f"메타데이터 조회 실패: {tool_name} - {e}")
            return None
    
    def list_tools(self, category: Optional[ToolCategory] = None,
                  tag: Optional[str] = None, enabled_only: bool = True) -> List[str]:
        """
        도구 목록 조회
        
        Args:
            category: 필터링할 카테고리
            tag: 필터링할 태그
            enabled_only: 활성화된 도구만 포함할지 여부
            
        Returns:
            도구 이름 목록
        """
        tools = set(self._tools.keys())
        
        # 활성화 필터
        if enabled_only:
            tools = {name for name in tools if self._tools[name].enabled}
        
        # 카테고리 필터
        if category:
            category_tools = self._categories.get(category, set())
            tools &= category_tools
        
        # 태그 필터
        if tag:
            tag_tools = self._tags.get(tag, set())
            tools &= tag_tools
        
        return sorted(list(tools))
    
    def get_categories(self) -> List[ToolCategory]:
        """등록된 도구 카테고리 목록"""
        return sorted(list(self._categories.keys()), key=lambda x: x.value)
    
    def get_tags(self) -> List[str]:
        """등록된 태그 목록"""
        return sorted(list(self._tags.keys()))
    
    async def enable_tool(self, tool_name: str) -> bool:
        """도구 활성화"""
        if tool_name not in self._tools:
            return False
        
        self._tools[tool_name].enabled = True
        logger.info(f"도구 활성화: {tool_name}")
        return True
    
    async def disable_tool(self, tool_name: str) -> bool:
        """도구 비활성화"""
        if tool_name not in self._tools:
            return False
        
        registration = self._tools[tool_name]
        registration.enabled = False
        
        # 인스턴스가 있으면 정리
        if registration.instance:
            await registration.instance.cleanup()
            registration.instance = None
        
        logger.info(f"도구 비활성화: {tool_name}")
        return True
    
    def get_tool_stats(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """도구 사용 통계"""
        if tool_name not in self._tools:
            return None
        
        registration = self._tools[tool_name]
        
        return {
            "name": tool_name,
            "registered_at": registration.registered_at.isoformat(),
            "last_used": registration.last_used.isoformat() if registration.last_used else None,
            "usage_count": registration.usage_count,
            "enabled": registration.enabled,
            "initialized": registration.is_initialized
        }
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """레지스트리 전체 통계"""
        total_tools = len(self._tools)
        enabled_tools = sum(1 for reg in self._tools.values() if reg.enabled)
        initialized_tools = sum(1 for reg in self._tools.values() if reg.is_initialized)
        
        category_counts = {}
        for category, tools in self._categories.items():
            category_counts[category.value] = len(tools)
        
        return {
            "total_tools": total_tools,
            "enabled_tools": enabled_tools,
            "initialized_tools": initialized_tools,
            "categories": category_counts,
            "total_tags": len(self._tags)
        }
    
    def add_listener(self, listener: Callable) -> None:
        """이벤트 리스너 추가"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable) -> None:
        """이벤트 리스너 제거"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    async def _notify_listeners(self, event_type: str, tool_name: str, 
                               metadata: ToolMetadata) -> None:
        """리스너들에게 이벤트 알림"""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event_type, tool_name, metadata)
                else:
                    listener(event_type, tool_name, metadata)
            except Exception as e:
                logger.error(f"리스너 실행 실패: {e}")
    
    async def discover_tools(self, package_path: str) -> int:
        """
        패키지에서 도구 자동 발견 및 등록 (재귀적 검색)
        
        Args:
            package_path: 도구가 있는 패키지 경로 (예: "src.tools")
            
        Returns:
            발견된 도구 수
        """
        discovered_count = 0
        
        try:
            # 패키지 임포트
            package = importlib.import_module(package_path)
            if package.__file__ is None:
                logger.error(f"패키지 파일 경로를 찾을 수 없습니다: {package_path}")
                return 0
            
            package_dir = Path(package.__file__).parent
            
            # 재귀적으로 모든 .py 파일 검사
            for py_file in package_dir.rglob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                # 상대 경로를 모듈 경로로 변환
                relative_path = py_file.relative_to(package_dir)
                module_parts = list(relative_path.parts[:-1]) + [relative_path.stem]
                module_name = f"{package_path}.{'.'.join(module_parts)}"
                
                try:
                    module = importlib.import_module(module_name)
                    
                    # 모듈에서 BaseTool 하위 클래스 찾기
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (issubclass(obj, BaseTool) and 
                            obj != BaseTool and 
                            not inspect.isabstract(obj)):
                            
                            if await self.register_tool(obj):
                                discovered_count += 1
                                logger.info(f"자동 발견된 도구: {obj.__name__} (모듈: {module_name})")
                
                except Exception as e:
                    logger.error(f"모듈 검사 실패: {module_name} - {e}")
        
        except Exception as e:
            logger.error(f"도구 발견 실패: {package_path} - {e}")
        
        logger.info(f"도구 자동 발견 완료: {discovered_count}개 발견")
        return discovered_count
    
    async def reload_tool(self, tool_name: str) -> bool:
        """도구 재로드"""
        if tool_name not in self._tools:
            return False
        
        registration = self._tools[tool_name]
        
        try:
            # 기존 인스턴스 정리
            if registration.instance:
                await registration.instance.cleanup()
            
            # 새 인스턴스 생성 및 초기화
            registration.instance = registration.tool_class()
            success = await registration.instance.initialize()
            
            if success:
                logger.info(f"도구 재로드 완료: {tool_name}")
            else:
                logger.error(f"도구 재로드 실패: {tool_name}")
                registration.instance = None
            
            return success
            
        except Exception as e:
            logger.error(f"도구 재로드 중 예외: {tool_name} - {e}")
            registration.instance = None
            return False
    
    async def cleanup_all(self) -> None:
        """모든 도구 정리"""
        logger.info("모든 도구 정리 시작...")
        
        for tool_name, registration in self._tools.items():
            if registration.instance:
                try:
                    await registration.instance.cleanup()
                    logger.info(f"도구 정리 완료: {tool_name}")
                except Exception as e:
                    logger.error(f"도구 정리 실패: {tool_name} - {e}")
        
        logger.info("모든 도구 정리 완료")


# 전역 레지스트리 인스턴스
_global_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """전역 레지스트리 인스턴스 반환"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


async def register_tool(tool_class: Type[BaseTool], auto_initialize: bool = True) -> bool:
    """편의 함수: 전역 레지스트리에 도구 등록"""
    return await get_registry().register_tool(tool_class, auto_initialize)


async def get_tool(tool_name: str) -> Optional[BaseTool]:
    """편의 함수: 전역 레지스트리에서 도구 가져오기"""
    return await get_registry().get_tool(tool_name)
