"""
이벤트 버스 시스템

모든 컴포넌트 간의 비동기 통신을 담당하는 중앙 이벤트 버스입니다.
컴포넌트들이 서로 직접 의존하지 않고 이벤트를 통해 소통할 수 있게 합니다.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Any, Callable, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from loguru import logger
import uuid
import weakref


class EventType(Enum):
    """시스템 이벤트 타입 정의"""
    
    # Discord 관련 이벤트
    DISCORD_MESSAGE_RECEIVED = "discord.message.received"
    DISCORD_COMMAND_PARSED = "discord.command.parsed"
    DISCORD_RESPONSE_SENT = "discord.response.sent"
    
    # AI 엔진 관련 이벤트
    AI_ANALYSIS_STARTED = "ai.analysis.started"
    AI_ANALYSIS_COMPLETED = "ai.analysis.completed"
    AI_TOOL_SELECTED = "ai.tool.selected"
    AI_DECISION_MADE = "ai.decision.made"
    
    # 메모리 관련 이벤트
    MEMORY_SEARCH_REQUESTED = "memory.search.requested"
    MEMORY_SEARCH_COMPLETED = "memory.search.completed"
    MEMORY_STORED = "memory.stored"
    MEMORY_UPDATED = "memory.updated"
    
    # MCP 도구 관련 이벤트
    TOOL_EXECUTION_STARTED = "tool.execution.started"
    TOOL_EXECUTION_COMPLETED = "tool.execution.completed"
    TOOL_EXECUTION_FAILED = "tool.execution.failed"
    
    # Notion 관련 이벤트
    NOTION_TASK_CREATED = "notion.task.created"
    NOTION_CALENDAR_UPDATED = "notion.calendar.updated"
    
    # Apple 관련 이벤트
    APPLE_NOTIFICATION_RECEIVED = "apple.notification.received"
    APPLE_ACTION_EXECUTED = "apple.action.executed"
    
    # 웹 스크래핑 관련 이벤트
    WEB_SCRAPING_STARTED = "web.scraping.started"
    WEB_SCRAPING_COMPLETED = "web.scraping.completed"
    
    # 시스템 관련 이벤트
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH_CHECK = "system.health.check"


@dataclass
class Event:
    """이벤트 데이터 구조"""
    event_id: str
    event_type: EventType
    source: str  # 이벤트를 발생시킨 컴포넌트
    target: Optional[str]  # 특정 컴포넌트 대상 (None이면 브로드캐스트)
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None  # 관련 이벤트들을 연결하는 ID
    priority: int = 5  # 1(긴급) ~ 10(낮음)
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """이벤트를 딕셔너리로 변환"""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """딕셔너리에서 이벤트 생성"""
        data['event_type'] = EventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class EventHandler:
    """이벤트 핸들러 래퍼"""
    
    def __init__(self, handler: Callable, component_name: str):
        self.handler = handler
        self.component_name = component_name
        self.is_async = asyncio.iscoroutinefunction(handler)
        self.call_count = 0
        self.error_count = 0
        self.last_called = None
        
    async def __call__(self, event: Event) -> Any:
        """핸들러 실행"""
        try:
            self.call_count += 1
            self.last_called = datetime.now(timezone.utc)
            
            if self.is_async:
                return await self.handler(event)
            else:
                return self.handler(event)
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"이벤트 핸들러 오류 ({self.component_name}): {e}")
            raise


class EventBus:
    """중앙 이벤트 버스"""
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stats = {
            "events_published": 0,
            "events_processed": 0,
            "events_failed": 0,
            "handlers_registered": 0
        }
        self._component_registry: Dict[str, weakref.ref] = {}
        
        logger.info("이벤트 버스 초기화 완료")
    
    def register_component(self, name: str, component: Any) -> None:
        """컴포넌트를 이벤트 버스에 등록"""
        self._component_registry[name] = weakref.ref(component)
        logger.info(f"컴포넌트 등록: {name}")
    
    def subscribe(self, event_type: EventType, handler: Callable, component_name: str) -> None:
        """이벤트 구독"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        
        event_handler = EventHandler(handler, component_name)
        self._handlers[event_type].append(event_handler)
        self._stats["handlers_registered"] += 1
        
        logger.info(f"이벤트 구독: {component_name} -> {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, component_name: str) -> None:
        """이벤트 구독 해제"""
        if event_type in self._handlers:
            self._handlers[event_type] = [
                h for h in self._handlers[event_type] 
                if h.component_name != component_name
            ]
            logger.info(f"이벤트 구독 해제: {component_name} -> {event_type.value}")
    
    async def publish(self, event: Event) -> None:
        """이벤트 발행"""
        if not self._is_running:
            await self.start()
        
        await self._event_queue.put(event)
        self._stats["events_published"] += 1
        
        logger.debug(f"이벤트 발행: {event.event_type.value} from {event.source}")
    
    async def publish_event(
        self,
        event_type: EventType,
        source: str,
        data: Dict[str, Any],
        target: Optional[str] = None,
        correlation_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """편의 메서드: 이벤트 생성 및 발행"""
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            target=target,
            timestamp=datetime.now(timezone.utc),
            data=data,
            correlation_id=correlation_id,
            priority=priority
        )
        
        await self.publish(event)
        return event.event_id
    
    async def start(self) -> None:
        """이벤트 버스 시작"""
        if self._is_running:
            return
        
        self._is_running = True
        self._worker_task = asyncio.create_task(self._event_worker())
        
        await self.publish_event(
            event_type=EventType.SYSTEM_STARTUP,
            source="event_bus",
            data={"message": "이벤트 버스 시작됨"}
        )
        
        logger.info("이벤트 버스 시작됨")
    
    async def stop(self) -> None:
        """이벤트 버스 중지"""
        if not self._is_running:
            return
        
        await self.publish_event(
            event_type=EventType.SYSTEM_SHUTDOWN,
            source="event_bus",
            data={"message": "이벤트 버스 종료됨"}
        )
        
        self._is_running = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        logger.info("이벤트 버스 종료됨")
    
    async def _event_worker(self) -> None:
        """이벤트 처리 워커"""
        while self._is_running:
            try:
                # 우선순위 기반으로 이벤트 가져오기
                event = await self._event_queue.get()
                await self._process_event(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"이벤트 워커 오류: {e}")
                self._stats["events_failed"] += 1
    
    async def _process_event(self, event: Event) -> None:
        """단일 이벤트 처리"""
        try:
            handlers = self._handlers.get(event.event_type, [])
            
            if not handlers:
                logger.debug(f"핸들러 없음: {event.event_type.value}")
                return
            
            # 타겟이 지정된 경우 해당 컴포넌트 핸들러만 실행
            if event.target:
                handlers = [h for h in handlers if h.component_name == event.target]
            
            # 모든 핸들러에게 이벤트 전달
            tasks = []
            for handler in handlers:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            
            # 모든 핸들러 실행 완료 대기
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # 오류 처리
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"핸들러 실행 오류: {handlers[i].component_name} - {result}")
                        # 재시도 로직
                        if event.retry_count < event.max_retries:
                            event.retry_count += 1
                            await asyncio.sleep(2 ** event.retry_count)  # 지수 백오프
                            await self._event_queue.put(event)
                            return
            
            self._stats["events_processed"] += 1
            logger.debug(f"이벤트 처리 완료: {event.event_type.value}")
            
        except Exception as e:
            logger.error(f"이벤트 처리 오류: {e}")
            self._stats["events_failed"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """이벤트 버스 통계"""
        return {
            **self._stats,
            "queue_size": self._event_queue.qsize(),
            "is_running": self._is_running,
            "registered_components": list(self._component_registry.keys()),
            "event_types_with_handlers": list(self._handlers.keys())
        }
    
    def get_component_stats(self) -> Dict[str, Dict[str, Any]]:
        """컴포넌트별 통계"""
        stats = {}
        for event_type, handlers in self._handlers.items():
            for handler in handlers:
                component_name = handler.component_name
                if component_name not in stats:
                    stats[component_name] = {
                        "total_calls": 0,
                        "total_errors": 0,
                        "subscribed_events": []
                    }
                
                stats[component_name]["total_calls"] += handler.call_count
                stats[component_name]["total_errors"] += handler.error_count
                stats[component_name]["subscribed_events"].append(event_type.value)
        
        return stats


# 전역 이벤트 버스 인스턴스
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """전역 이벤트 버스 인스턴스 반환"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


async def publish_event(
    event_type: EventType,
    source: str,
    data: Dict[str, Any],
    target: Optional[str] = None,
    correlation_id: Optional[str] = None,
    priority: int = 5
) -> str:
    """편의 함수: 이벤트 발행"""
    event_bus = get_event_bus()
    return await event_bus.publish_event(
        event_type=event_type,
        source=source,
        data=data,
        target=target,
        correlation_id=correlation_id,
        priority=priority
    )


def subscribe_event(event_type: EventType, component_name: str):
    """데코레이터: 이벤트 구독"""
    def decorator(func):
        event_bus = get_event_bus()
        event_bus.subscribe(event_type, func, component_name)
        return func
    return decorator
