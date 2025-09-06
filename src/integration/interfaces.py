from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class ComponentStatus(Enum):
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"

@dataclass
class HealthCheckResult:
    status: HealthStatus
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    response_time_ms: float

class BaseComponent(ABC):
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.status = ComponentStatus.READY
        self.health = HealthStatus.HEALTHY
        
    @abstractmethod
    async def initialize(self) -> bool:
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        pass
