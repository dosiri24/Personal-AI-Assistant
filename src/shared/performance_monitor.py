"""
성능 모니터링 및 최적화 시스템

메모리 사용량, 실행 시간, API 호출 등을 모니터링하고 최적화합니다.
"""

import time
import psutil
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """성능 지표"""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass  
class ToolExecutionStats:
    """도구 실행 통계"""
    tool_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    last_executed: Optional[datetime] = None
    recent_execution_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_execution(self, execution_time: float, success: bool):
        """실행 통계 업데이트"""
        self.total_executions += 1
        if success:
            self.successful_executions += 1
        else:
            self.failed_executions += 1
        
        self.total_execution_time += execution_time
        self.average_execution_time = self.total_execution_time / self.total_executions
        self.last_executed = datetime.now()
        self.recent_execution_times.append(execution_time)
    
    @property
    def success_rate(self) -> float:
        """성공률"""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100
    
    @property
    def recent_average_time(self) -> float:
        """최근 평균 실행 시간"""
        if not self.recent_execution_times:
            return 0.0
        return sum(self.recent_execution_times) / len(self.recent_execution_times)


class PerformanceMonitor:
    """성능 모니터"""
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.tool_stats: Dict[str, ToolExecutionStats] = {}
        self.system_stats: Dict[str, Any] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
    
    def start_monitoring(self, interval: int = 60):
        """모니터링 시작"""
        if self._running:
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f"성능 모니터링 시작 (간격: {interval}초)")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        if not self._running:
            return
        
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("성능 모니터링 중지")
    
    async def _monitor_loop(self, interval: int):
        """모니터링 루프"""
        while self._running:
            try:
                await self._collect_system_metrics()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"모니터링 중 오류: {str(e)}")
                await asyncio.sleep(interval)
    
    async def _collect_system_metrics(self):
        """시스템 메트릭 수집"""
        try:
            # CPU 사용률
            cpu_percent = psutil.cpu_percent(interval=1)
            self.add_metric("cpu_usage", cpu_percent, "percent")
            
            # 메모리 사용률
            memory = psutil.virtual_memory()
            self.add_metric("memory_usage", memory.percent, "percent")
            self.add_metric("memory_used", memory.used / (1024**3), "GB")  # GB 단위
            
            # 프로세스별 메모리
            process = psutil.Process()
            process_memory = process.memory_info()
            self.add_metric("process_memory", process_memory.rss / (1024**2), "MB")  # MB 단위
            
            # 디스크 사용률 
            disk = psutil.disk_usage('/')
            self.add_metric("disk_usage", (disk.used / disk.total) * 100, "percent")
            
            # 시스템 통계 업데이트
            with self._lock:
                self.system_stats.update({
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3),
                    "process_memory_mb": process_memory.rss / (1024**2),
                    "disk_usage_percent": (disk.used / disk.total) * 100,
                    "last_updated": datetime.now()
                })
                
        except Exception as e:
            logger.error(f"시스템 메트릭 수집 실패: {str(e)}")
    
    def add_metric(self, name: str, value: float, unit: str, **metadata):
        """메트릭 추가"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            metadata=metadata
        )
        
        with self._lock:
            self.metrics.append(metric)
    
    def record_tool_execution(self, tool_name: str, execution_time: float, success: bool):
        """도구 실행 기록"""
        with self._lock:
            if tool_name not in self.tool_stats:
                self.tool_stats[tool_name] = ToolExecutionStats(tool_name)
            
            self.tool_stats[tool_name].add_execution(execution_time, success)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """시스템 통계 조회"""
        with self._lock:
            return self.system_stats.copy()
    
    def get_tool_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """도구 통계 조회"""
        with self._lock:
            if tool_name:
                return self.tool_stats.get(tool_name, ToolExecutionStats(tool_name)).__dict__
            else:
                return {name: stats.__dict__ for name, stats in self.tool_stats.items()}
    
    def get_recent_metrics(self, metric_name: str, minutes: int = 10) -> List[PerformanceMetric]:
        """최근 메트릭 조회"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            return [
                metric for metric in self.metrics
                if metric.name == metric_name and metric.timestamp >= cutoff_time
            ]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보"""
        with self._lock:
            summary = {
                "system": self.system_stats.copy(),
                "tools": {},
                "alerts": []
            }
            
            # 도구별 요약
            for tool_name, stats in self.tool_stats.items():
                summary["tools"][tool_name] = {
                    "total_executions": stats.total_executions,
                    "success_rate": stats.success_rate,
                    "average_time": stats.average_execution_time,
                    "recent_average_time": stats.recent_average_time
                }
            
            # 성능 알림 생성
            if "memory_percent" in self.system_stats:
                if self.system_stats["memory_percent"] > 80:
                    summary["alerts"].append({
                        "type": "high_memory",
                        "message": f"메모리 사용률이 높습니다: {self.system_stats['memory_percent']:.1f}%"
                    })
                
                if self.system_stats["cpu_percent"] > 80:
                    summary["alerts"].append({
                        "type": "high_cpu", 
                        "message": f"CPU 사용률이 높습니다: {self.system_stats['cpu_percent']:.1f}%"
                    })
            
            # 도구 성능 알림
            for tool_name, stats in self.tool_stats.items():
                if stats.success_rate < 90 and stats.total_executions > 10:
                    summary["alerts"].append({
                        "type": "low_success_rate",
                        "message": f"도구 '{tool_name}'의 성공률이 낮습니다: {stats.success_rate:.1f}%"
                    })
            
            return summary
    
    def clear_stats(self):
        """통계 초기화"""
        with self._lock:
            self.metrics.clear()
            self.tool_stats.clear()
            self.system_stats.clear()


# 전역 성능 모니터 인스턴스
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """전역 성능 모니터 인스턴스 반환"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# 성능 측정 데코레이터
def monitor_performance(tool_name: str = None):
    """성능 모니터링 데코레이터"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                # 결과가 ExecutionResult인 경우 성공 여부 확인
                if hasattr(result, 'success'):
                    success = result.success
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                func_tool_name = tool_name or func.__name__
                monitor.record_tool_execution(func_tool_name, execution_time, success)
        
        def sync_wrapper(*args, **kwargs):
            monitor = get_performance_monitor()
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                if hasattr(result, 'success'):
                    success = result.success
                return result
            except Exception as e:
                success = False
                raise
            finally:
                execution_time = time.time() - start_time
                func_tool_name = tool_name or func.__name__
                monitor.record_tool_execution(func_tool_name, execution_time, success)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator