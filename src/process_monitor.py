"""
프로세스 모니터링 및 헬스체크 모듈
"""
import time
import threading
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """헬스체크 결과 데이터 클래스"""
    timestamp: str
    status: str  # 'healthy', 'warning', 'critical'
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    memory_mb: Optional[float] = None
    uptime_seconds: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class ProcessMetrics:
    """프로세스 메트릭 데이터 클래스"""
    pid: int
    start_time: datetime
    last_heartbeat: datetime
    restart_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'pid': self.pid,
            'start_time': self.start_time.isoformat(),
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'restart_count': self.restart_count,
            'error_count': self.error_count,
            'last_error': self.last_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessMetrics':
        """딕셔너리에서 생성"""
        return cls(
            pid=data['pid'],
            start_time=datetime.fromisoformat(data['start_time']),
            last_heartbeat=datetime.fromisoformat(data['last_heartbeat']),
            restart_count=data.get('restart_count', 0),
            error_count=data.get('error_count', 0),
            last_error=data.get('last_error')
        )


class ProcessMonitor:
    """프로세스 모니터링 클래스"""
    
    def __init__(self, metrics_file: Path, heartbeat_interval: int = 30):
        self.metrics_file = metrics_file
        self.heartbeat_interval = heartbeat_interval
        self.metrics: Optional[ProcessMetrics] = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # 메트릭 파일 디렉토리 생성
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    def start_monitoring(self, pid: int):
        """모니터링 시작"""
        logger.info(f"프로세스 모니터링 시작 (PID: {pid})")
        
        now = datetime.now()
        
        # 기존 메트릭 로드 또는 새로 생성
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                self.metrics = ProcessMetrics.from_dict(data)
                self.metrics.pid = pid
                self.metrics.last_heartbeat = now
                self.metrics.restart_count += 1
                logger.info(f"기존 메트릭 로드됨 (재시작 횟수: {self.metrics.restart_count})")
            except Exception as e:
                logger.warning(f"메트릭 파일 로드 실패, 새로 생성: {e}")
                self.metrics = ProcessMetrics(
                    pid=pid,
                    start_time=now,
                    last_heartbeat=now
                )
        else:
            self.metrics = ProcessMetrics(
                pid=pid,
                start_time=now,
                last_heartbeat=now
            )
        
        # 메트릭 저장
        self._save_metrics()
        
        # 백그라운드 모니터링 시작
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """모니터링 중지"""
        logger.info("프로세스 모니터링 중지")
        self._monitoring = False
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        # 메트릭 파일 삭제
        if self.metrics_file.exists():
            try:
                self.metrics_file.unlink()
                logger.debug("메트릭 파일 삭제됨")
            except Exception as e:
                logger.warning(f"메트릭 파일 삭제 실패: {e}")
    
    def update_heartbeat(self):
        """하트비트 업데이트"""
        if self.metrics:
            self.metrics.last_heartbeat = datetime.now()
            self._save_metrics()
    
    def record_error(self, error_message: str):
        """에러 기록"""
        if self.metrics:
            self.metrics.error_count += 1
            self.metrics.last_error = error_message
            self._save_metrics()
            logger.error(f"프로세스 에러 기록: {error_message}")
    
    def get_health_status(self) -> HealthCheckResult:
        """헬스 상태 확인"""
        now = datetime.now()
        
        if not self.metrics:
            return HealthCheckResult(
                timestamp=now.isoformat(),
                status='critical',
                last_error='메트릭 정보 없음'
            )
        
        # 프로세스 존재 확인
        try:
            import os
            os.kill(self.metrics.pid, 0)
        except (ProcessLookupError, PermissionError):
            return HealthCheckResult(
                timestamp=now.isoformat(),
                status='critical',
                last_error='프로세스가 존재하지 않음'
            )
        
        # 하트비트 확인 (5분 이내)
        heartbeat_threshold = timedelta(minutes=5)
        if now - self.metrics.last_heartbeat > heartbeat_threshold:
            return HealthCheckResult(
                timestamp=now.isoformat(),
                status='warning',
                error_count=self.metrics.error_count,
                last_error='하트비트 타임아웃'
            )
        
        # 시스템 메트릭 수집
        cpu_usage, memory_usage, memory_mb = self._get_system_metrics()
        uptime_seconds = (now - self.metrics.start_time).total_seconds()
        
        # 상태 결정
        status = 'healthy'
        if self.metrics.error_count > 10:
            status = 'warning'
        if cpu_usage and cpu_usage > 90:
            status = 'warning'
        if memory_mb and memory_mb > 1000:  # 1GB 이상
            status = 'warning'
        
        return HealthCheckResult(
            timestamp=now.isoformat(),
            status=status,
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            memory_mb=memory_mb,
            uptime_seconds=uptime_seconds,
            error_count=self.metrics.error_count,
            last_error=self.metrics.last_error
        )
    
    def _monitor_loop(self):
        """모니터링 백그라운드 루프"""
        logger.debug("모니터링 루프 시작")
        
        while self._monitoring:
            try:
                # 하트비트 업데이트
                self.update_heartbeat()
                
                # 헬스체크 수행
                health = self.get_health_status()
                
                # 경고 상태 로깅
                if health.status == 'warning':
                    logger.warning(f"프로세스 상태 경고: {health.last_error}")
                elif health.status == 'critical':
                    logger.error(f"프로세스 상태 심각: {health.last_error}")
                
                # 대기
                time.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"모니터링 루프 에러: {e}")
                if self.metrics:
                    self.record_error(str(e))
                time.sleep(5)  # 에러 시 짧게 대기
    
    def _save_metrics(self):
        """메트릭 저장"""
        if self.metrics:
            try:
                with open(self.metrics_file, 'w') as f:
                    json.dump(self.metrics.to_dict(), f, indent=2)
            except Exception as e:
                logger.error(f"메트릭 저장 실패: {e}")
    
    def _get_system_metrics(self) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """시스템 메트릭 수집"""
        try:
            import psutil
            
            if self.metrics:
                process = psutil.Process(self.metrics.pid)
                
                # CPU 사용률 (1초 간격으로 측정)
                cpu_usage = process.cpu_percent(interval=1)
                
                # 메모리 사용률
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                # 시스템 전체 메모리 대비 사용률
                system_memory = psutil.virtual_memory()
                memory_usage = (memory_info.rss / system_memory.total) * 100
                
                return cpu_usage, memory_usage, memory_mb
                
        except (ImportError, Exception) as e:
            logger.debug(f"시스템 메트릭 수집 실패: {e}")
        
        return None, None, None


class AutoRestartManager:
    """자동 재시작 관리 클래스"""
    
    def __init__(self, max_restarts: int = 5, restart_window: int = 300):
        """
        Args:
            max_restarts: 재시작 윈도우 내 최대 재시작 횟수
            restart_window: 재시작 카운트 윈도우 (초)
        """
        self.max_restarts = max_restarts
        self.restart_window = restart_window
        self.restart_history: List[datetime] = []
        
    def can_restart(self) -> bool:
        """재시작 가능 여부 확인"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.restart_window)
        
        # 윈도우 내 재시작 기록만 유지
        self.restart_history = [
            restart_time for restart_time in self.restart_history
            if restart_time > cutoff
        ]
        
        return len(self.restart_history) < self.max_restarts
    
    def record_restart(self):
        """재시작 기록"""
        self.restart_history.append(datetime.now())
        logger.info(f"재시작 기록됨 (총 {len(self.restart_history)}회)")
    
    def get_restart_info(self) -> Dict[str, Any]:
        """재시작 정보 반환"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.restart_window)
        
        recent_restarts = [
            restart_time for restart_time in self.restart_history
            if restart_time > cutoff
        ]
        
        return {
            'recent_restarts': len(recent_restarts),
            'max_restarts': self.max_restarts,
            'restart_window': self.restart_window,
            'can_restart': self.can_restart(),
            'last_restart': recent_restarts[-1].isoformat() if recent_restarts else None
        }
