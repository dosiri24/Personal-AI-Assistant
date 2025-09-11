"""
성능 최적화 시스템

이 모듈은 Personal AI Assistant의 성능을 모니터링하고 최적화하는 기능을 제공합니다.
"""

import asyncio
import time
import psutil
import functools
import threading
from typing import Dict, Any, Optional, Callable, List, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from enum import Enum
import weakref
import json
import gc
import sys

from src.utils.logger import get_logger
from src.utils.error_handler import handle_errors, retry_on_failure

logger = get_logger(__name__)


class CacheStrategy(Enum):
    """캐시 전략"""
    LRU = "lru"  # Least Recently Used
    TTL = "ttl"  # Time To Live
    LFU = "lfu"  # Least Frequently Used
    FIFO = "fifo"  # First In, First Out


@dataclass
class PerformanceMetrics:
    """성능 메트릭"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_usage_mb: float
    active_threads: int
    async_tasks: int
    cache_hit_rate: float
    average_response_time: float
    requests_per_second: float
    error_rate: float


@dataclass
class CacheEntry:
    """캐시 엔트리"""
    key: str
    value: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[float] = None
    
    def is_expired(self) -> bool:
        """캐시 항목 만료 여부 확인"""
        if self.ttl_seconds is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl_seconds
    
    def touch(self):
        """캐시 항목 접근 기록"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class AdvancedCache:
    """고도화된 캐시 시스템"""
    
    def __init__(
        self,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.LRU,
        default_ttl: Optional[float] = None
    ):
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        
        # 통계
        self.hits = 0
        self.misses = 0
        self.evictions = 0
    
    def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 조회"""
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self.misses += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self.misses += 1
                return None
            
            entry.touch()
            self.hits += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """캐시에 값 저장"""
        with self._lock:
            # TTL 설정
            effective_ttl = ttl or self.default_ttl
            
            # 새로운 엔트리 생성
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                ttl_seconds=effective_ttl
            )
            
            # 기존 엔트리가 있으면 교체
            if key in self._cache:
                self._cache[key] = entry
                return
            
            # 캐시 크기 확인 및 필요시 eviction
            if len(self._cache) >= self.max_size:
                self._evict()
            
            self._cache[key] = entry
    
    def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """캐시 전체 삭제"""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
    
    def _evict(self) -> None:
        """캐시 eviction 수행"""
        if not self._cache:
            return
        
        key_to_remove = None
        
        if self.strategy == CacheStrategy.LRU:
            # 가장 오래 전에 접근된 항목 제거
            key_to_remove = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed
            )
        
        elif self.strategy == CacheStrategy.LFU:
            # 가장 적게 접근된 항목 제거
            key_to_remove = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
        
        elif self.strategy == CacheStrategy.FIFO:
            # 가장 먼저 생성된 항목 제거
            key_to_remove = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
        
        elif self.strategy == CacheStrategy.TTL:
            # 만료된 항목들 먼저 제거, 없으면 LRU 방식
            expired_keys = [
                k for k, v in self._cache.items() if v.is_expired()
            ]
            if expired_keys:
                key_to_remove = expired_keys[0]
            else:
                key_to_remove = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].last_accessed
                )
        
        if key_to_remove:
            del self._cache[key_to_remove]
            self.evictions += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": hit_rate,
            "strategy": self.strategy.value
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 반환 (모니터링용)"""
        return self.get_stats()


class ResourcePool:
    """리소스 풀 관리"""
    
    def __init__(
        self,
        max_threads: int = 10,
        max_processes: int = 4,
        max_async_tasks: int = 100
    ):
        self.max_threads = max_threads
        self.max_processes = max_processes
        self.max_async_tasks = max_async_tasks
        
        # Thread pool
        self._thread_pool = ThreadPoolExecutor(max_workers=max_threads)
        
        # Process pool  
        self._process_pool = ProcessPoolExecutor(max_workers=max_processes)
        
        # Async semaphore for limiting concurrent tasks
        self._async_semaphore = asyncio.Semaphore(max_async_tasks)
        
        # 활성 태스크 추적
        self._active_tasks: weakref.WeakSet = weakref.WeakSet()
        
        logger.info(f"리소스 풀 초기화: 스레드 {max_threads}, 프로세스 {max_processes}, 비동기 태스크 {max_async_tasks}")
    
    async def run_async_with_limit(self, coro):
        """제한된 비동기 태스크 실행"""
        async with self._async_semaphore:
            task = asyncio.current_task()
            if task:
                self._active_tasks.add(task)
            return await coro
    
    def run_in_thread(self, func: Callable, *args, **kwargs):
        """스레드 풀에서 함수 실행"""
        return self._thread_pool.submit(func, *args, **kwargs)
    
    def run_in_process(self, func: Callable, *args, **kwargs):
        """프로세스 풀에서 함수 실행"""
        return self._process_pool.submit(func, *args, **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """리소스 풀 통계"""
        return {
            "thread_pool": {
                "max_workers": self.max_threads,
                "active_threads": threading.active_count()
            },
            "process_pool": {
                "max_workers": self.max_processes
            },
            "async_tasks": {
                "max_concurrent": self.max_async_tasks,
                "active_tasks": len(self._active_tasks),
                "semaphore_available": self._async_semaphore._value
            }
        }
    
    def shutdown(self):
        """리소스 풀 종료"""
        logger.info("리소스 풀 종료 중...")
        self._thread_pool.shutdown(wait=True)
        self._process_pool.shutdown(wait=True)
        logger.info("리소스 풀 종료 완료")


class PerformanceMonitor:
    """성능 모니터"""
    
    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.metrics_history: List[PerformanceMetrics] = []
        self.request_times: List[float] = []
        self.error_count = 0
        self.request_count = 0
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # 시스템 메트릭 수집을 위한 프로세스 정보
        self.process = psutil.Process()
    
    async def start_monitoring(self):
        """성능 모니터링 시작"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("성능 모니터링 시작")
    
    async def stop_monitoring(self):
        """성능 모니터링 중지"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("성능 모니터링 중지")
    
    async def _monitor_loop(self):
        """모니터링 루프"""
        while self._monitoring:
            try:
                metrics = await self._collect_metrics()
                self.metrics_history.append(metrics)
                
                # 히스토리 크기 제한 (최근 1000개만 유지)
                if len(self.metrics_history) > 1000:
                    self.metrics_history = self.metrics_history[-1000:]
                
                await asyncio.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error(f"성능 메트릭 수집 중 오류: {e}")
                await asyncio.sleep(self.sample_interval)
    
    async def _collect_metrics(self) -> PerformanceMetrics:
        """성능 메트릭 수집"""
        # CPU 사용률
        cpu_percent = self.process.cpu_percent()
        
        # 메모리 사용률
        memory_info = self.process.memory_info()
        memory_usage_mb = memory_info.rss / 1024 / 1024
        memory_percent = self.process.memory_percent()
        
        # 스레드 수
        active_threads = threading.active_count()
        
        # 비동기 태스크 수 (현재 이벤트 루프의 태스크)
        try:
            loop = asyncio.get_running_loop()
            async_tasks = len([task for task in asyncio.all_tasks(loop) if not task.done()])
        except RuntimeError:
            async_tasks = 0
        
        # 캐시 히트율 (전역 캐시가 있다면)
        cache_hit_rate = 0.0  # 기본값
        
        # 평균 응답 시간
        avg_response_time = 0.0
        if self.request_times:
            avg_response_time = sum(self.request_times[-100:]) / min(len(self.request_times), 100)
        
        # 초당 요청 수 (최근 1분 기준)
        recent_requests = len([t for t in self.request_times if time.time() - t < 60])
        requests_per_second = recent_requests / 60.0
        
        # 에러율
        error_rate = 0.0
        if self.request_count > 0:
            error_rate = (self.error_count / self.request_count) * 100
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_usage_mb=memory_usage_mb,
            active_threads=active_threads,
            async_tasks=async_tasks,
            cache_hit_rate=cache_hit_rate,
            average_response_time=avg_response_time,
            requests_per_second=requests_per_second,
            error_rate=error_rate
        )
    
    def record_request(self, response_time: float, success: bool = True):
        """요청 기록"""
        self.request_times.append(time.time())
        self.request_count += 1
        
        if not success:
            self.error_count += 1
    
    def get_current_stats(self) -> Dict[str, Any]:
        """현재 성능 통계"""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        
        # 최근 10개 메트릭의 평균
        recent_metrics = self.metrics_history[-10:]
        
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        avg_response_time = sum(m.average_response_time for m in recent_metrics) / len(recent_metrics)
        
        return {
            "timestamp": latest.timestamp.isoformat(),
            "current": {
                "cpu_percent": latest.cpu_percent,
                "memory_percent": latest.memory_percent,
                "memory_usage_mb": latest.memory_usage_mb,
                "active_threads": latest.active_threads,
                "async_tasks": latest.async_tasks,
                "requests_per_second": latest.requests_per_second,
                "error_rate": latest.error_rate
            },
            "averages": {
                "cpu_percent": avg_cpu,
                "memory_percent": avg_memory,
                "response_time": avg_response_time
            },
            "totals": {
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "metrics_collected": len(self.metrics_history)
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """상세 통계 반환"""
        stats = {
            'total_requests': self.request_count,
            'successful_requests': self.request_count - self.error_count,
            'failed_requests': self.error_count,
            'avg_response_time': 0.0,
            'active_sessions': len(asyncio.all_tasks()) if self.is_monitoring else 0,
            'queue_size': 0,
            'tokens_processed': getattr(self, 'tokens_processed', 0)
        }
        
        # 평균 응답 시간 계산
        if self.request_times:
            total_time = sum(self.request_times[-100:])  # 최근 100개
            count = min(len(self.request_times), 100)
            stats['avg_response_time'] = total_time / count if count > 0 else 0.0
        
        return stats


class AsyncBatchProcessor:
    """비동기 배치 처리기"""
    
    def __init__(
        self,
        batch_size: int = 10,
        flush_interval: float = 5.0,
        max_queue_size: int = 1000
    ):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_queue_size = max_queue_size
        
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self._batch: List[Any] = []
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False
        
        # 통계
        self.processed_count = 0
        self.batch_count = 0
    
    async def start(self):
        """배치 처리기 시작"""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._process_loop())
        logger.info(f"배치 처리기 시작: 배치 크기 {self.batch_size}, 플러시 간격 {self.flush_interval}초")
    
    async def stop(self):
        """배치 처리기 중지"""
        self._running = False
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # 남은 배치 처리
        if self._batch:
            await self._flush_batch()
        
        logger.info("배치 처리기 중지")
    
    async def add_item(self, item: Any) -> bool:
        """배치에 아이템 추가"""
        try:
            await self._queue.put(item)
            return True
        except asyncio.QueueFull:
            logger.warning("배치 처리 큐가 가득참")
            return False
    
    async def _process_loop(self):
        """배치 처리 루프"""
        last_flush = time.time()
        
        while self._running:
            try:
                # 큐에서 아이템 가져오기 (타임아웃 설정)
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                    self._batch.append(item)
                except asyncio.TimeoutError:
                    pass
                
                # 배치 크기 도달 또는 플러시 시간 도달시 배치 처리
                current_time = time.time()
                should_flush = (
                    len(self._batch) >= self.batch_size or
                    (self._batch and (current_time - last_flush) >= self.flush_interval)
                )
                
                if should_flush:
                    await self._flush_batch()
                    last_flush = current_time
                
            except Exception as e:
                logger.error(f"배치 처리 중 오류: {e}")
                await asyncio.sleep(1.0)
    
    async def _flush_batch(self):
        """배치 플러시 (하위 클래스에서 구현)"""
        if not self._batch:
            return
        
        batch_to_process = self._batch.copy()
        self._batch.clear()
        
        # 기본 구현: 로그 출력
        logger.info(f"배치 처리: {len(batch_to_process)}개 아이템")
        
        self.processed_count += len(batch_to_process)
        self.batch_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """배치 처리기 통계"""
        return {
            "queue_size": self._queue.qsize(),
            "current_batch_size": len(self._batch),
            "processed_count": self.processed_count,
            "batch_count": self.batch_count,
            "running": self._running
        }


def performance_monitor(monitor: PerformanceMonitor):
    """성능 모니터링 데코레이터"""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    success = False
                    raise
                finally:
                    response_time = time.time() - start_time
                    monitor.record_request(response_time, success)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                success = True
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    success = False
                    raise
                finally:
                    response_time = time.time() - start_time
                    monitor.record_request(response_time, success)
            
            return sync_wrapper
    
    return decorator


def cache_result(
    cache: AdvancedCache,
    ttl: Optional[float] = None,
    key_func: Optional[Callable] = None
):
    """캐시 결과 데코레이터"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 캐시 키 생성
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash((args, tuple(sorted(kwargs.items()))))}"
            
            # 캐시에서 확인
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 함수 실행 및 결과 캐싱
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        return wrapper
    
    return decorator


# 전역 인스턴스
global_cache = AdvancedCache(max_size=10000, strategy=CacheStrategy.LRU, default_ttl=3600)
global_resource_pool = ResourcePool()
global_performance_monitor = PerformanceMonitor()

logger.info("성능 최적화 시스템이 초기화되었습니다.")
