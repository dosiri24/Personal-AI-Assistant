"""
간소화된 성능 모니터링 시스템

Personal AI Assistant의 기본적인 성능 모니터링 기능을 제공합니다.
"""

import time
import psutil
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """성능 메트릭"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_usage_mb: float
    active_threads: int


class SimpleCache:
    """간소화된 캐시 시스템"""
    
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        with self._lock:
            if key in self._cache:
                self.hits += 1
                return self._cache[key]
            else:
                self.misses += 1
                return None
    
    def set(self, key: str, value: Any):
        """캐시에 값 저장"""
        with self._lock:
            if len(self._cache) >= self.max_size:
                # 가장 오래된 항목 제거 (FIFO)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            
            self._cache[key] = value
    
    def clear(self):
        """캐시 전체 삭제"""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "cache_size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "usage_percent": (len(self._cache) / self.max_size) * 100
        }


class SimplePerformanceMonitor:
    """간소화된 성능 모니터"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.metrics_history = []
        self.max_history = 100
    
    def collect_metrics(self) -> PerformanceMetrics:
        """현재 성능 메트릭 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent
            memory_usage_mb = memory_info.used / (1024 * 1024)
            active_threads = threading.active_count()
            
            metrics = PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_usage_mb=memory_usage_mb,
                active_threads=active_threads
            )
            
            # 기록 저장
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history:
                self.metrics_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.warning(f"성능 메트릭 수집 실패: {e}")
            return PerformanceMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_usage_mb=0.0,
                active_threads=0
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        if not self.metrics_history:
            self.collect_metrics()
        
        if self.metrics_history:
            latest = self.metrics_history[-1]
            return {
                "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
                "current_cpu_percent": latest.cpu_percent,
                "current_memory_percent": latest.memory_percent,
                "current_memory_mb": latest.memory_usage_mb,
                "active_threads": latest.active_threads,
                "metrics_count": len(self.metrics_history)
            }
        else:
            return {
                "uptime_seconds": 0,
                "current_cpu_percent": 0,
                "current_memory_percent": 0,
                "current_memory_mb": 0,
                "active_threads": 0,
                "metrics_count": 0
            }


# 전역 인스턴스들
global_performance_monitor = SimplePerformanceMonitor()
global_cache = SimpleCache()


def monitor_performance(func):
    """성능 모니터링 데코레이터"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.debug(f"{func.__name__} 실행 시간: {execution_time:.3f}초")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} 실행 실패 ({execution_time:.3f}초): {e}")
            raise
    return wrapper