"""
데몬 프로세스 관리 모듈
"""
import os
import sys
import signal
import time
import atexit
from pathlib import Path
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DaemonManager:
    """데몬 프로세스 생명주기 관리 클래스"""
    
    def __init__(self, pid_file: Path):
        self.pid_file = pid_file
        self.pid_dir = pid_file.parent
        
        # PID 디렉토리 생성
        self.pid_dir.mkdir(parents=True, exist_ok=True)
        
        # 모니터링 관련 초기화
        self.process_monitor = None
        self.auto_restart_manager = None
        self._initialize_monitoring()
    
    def _initialize_monitoring(self):
        """모니터링 시스템 초기화"""
        try:
            from .monitoring.process_monitor import ProcessMonitor, AutoRestartManager
            
            metrics_file = self.pid_dir / "process_metrics.json"
            self.process_monitor = ProcessMonitor(metrics_file)
            self.auto_restart_manager = AutoRestartManager(max_restarts=5, restart_window=300)
            
            logger.debug("프로세스 모니터링 시스템 초기화 완료")
            
        except ImportError:
            logger.warning("프로세스 모니터링 모듈을 찾을 수 없음")
        except Exception as e:
            logger.warning(f"프로세스 모니터링 초기화 실패: {e}")
    
    def is_running(self) -> bool:
        """데몬 프로세스가 실행 중인지 확인"""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 프로세스 존재 확인 (시그널 0 전송)
            os.kill(pid, 0)
            return True
            
        except (ValueError, ProcessLookupError, PermissionError):
            # 잘못된 PID 또는 프로세스 없음
            self._cleanup_pid_file()
            return False
    
    def get_pid(self) -> Optional[int]:
        """실행 중인 데몬의 PID 반환"""
        if not self.is_running():
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except (ValueError, FileNotFoundError):
            return None
    
    def start_daemon(self, target_function, *args, **kwargs):
        """데몬 프로세스 시작"""
        if self.is_running():
            raise RuntimeError("데몬이 이미 실행 중입니다")
        
        logger.info("데몬 프로세스 시작")
        
        # 첫 번째 포크
        pid = os.fork()
        if pid > 0:
            # 부모 프로세스 - 종료
            sys.exit(0)
        
        # 세션 리더가 되기
        os.setsid()
        
        # 두 번째 포크 (데몬 고아 프로세스 방지)
        pid = os.fork()
        if pid > 0:
            # 부모 프로세스 - 종료
            sys.exit(0)
        
        # 작업 디렉토리 변경
        os.chdir('/')
        
        # 파일 생성 마스크 리셋
        os.umask(0)
        
        # 표준 파일 디스크립터 리다이렉션
        self._redirect_standard_files()
        
        # PID 파일 생성
        self._write_pid_file()
        
        # 종료 시 정리 함수 등록
        atexit.register(self._cleanup_on_exit)
        
        # 시그널 핸들러 등록
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # 프로세스 모니터링 시작
        if self.process_monitor:
            self.process_monitor.start_monitoring(os.getpid())
        
        logger.info(f"데몬 프로세스 시작됨 (PID: {os.getpid()})")
        
        try:
            # 대상 함수 실행
            target_function(*args, **kwargs)
        except Exception as e:
            logger.error(f"데몬 실행 중 오류: {e}")
            if self.process_monitor:
                self.process_monitor.record_error(str(e))
            raise
        finally:
            self._cleanup_on_exit()
    
    def stop_daemon(self, timeout: int = 10) -> bool:
        """데몬 프로세스 중지"""
        if not self.is_running():
            logger.warning("중지할 데몬 프로세스가 없습니다")
            return True
        
        pid = self.get_pid()
        if pid is None:
            return True
        
        logger.info(f"데몬 프로세스 중지 요청 (PID: {pid})")
        
        try:
            # SIGTERM 전송
            os.kill(pid, signal.SIGTERM)
            
            # 정상 종료 대기
            for _ in range(timeout):
                try:
                    os.kill(pid, 0)
                    time.sleep(1)
                except ProcessLookupError:
                    logger.info("데몬 프로세스가 정상적으로 종료되었습니다")
                    self._cleanup_pid_file()
                    return True
            
            # 강제 종료
            logger.warning("정상 종료 시간 초과, 강제 종료합니다")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
            
            self._cleanup_pid_file()
            return True
            
        except ProcessLookupError:
            logger.info("데몬 프로세스가 이미 종료되었습니다")
            self._cleanup_pid_file()
            return True
        except PermissionError:
            logger.error("데몬 프로세스 종료 권한이 없습니다")
            return False
        except Exception as e:
            logger.error(f"데몬 중지 중 오류: {e}")
            return False
    
    def restart_daemon(self, target_function, *args, **kwargs):
        """데몬 프로세스 재시작"""
        logger.info("데몬 프로세스 재시작")
        
        if self.is_running():
            if not self.stop_daemon():
                raise RuntimeError("기존 데몬 프로세스 중지 실패")
        
        # 잠시 대기
        time.sleep(1)
        
        self.start_daemon(target_function, *args, **kwargs)
    
    def _write_pid_file(self):
        """PID 파일 생성"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            logger.debug(f"PID 파일 생성됨: {self.pid_file}")
        except Exception as e:
            logger.error(f"PID 파일 생성 실패: {e}")
            raise
    
    def _cleanup_pid_file(self):
        """PID 파일 정리"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
                logger.debug(f"PID 파일 삭제됨: {self.pid_file}")
        except Exception as e:
            logger.error(f"PID 파일 삭제 실패: {e}")
    
    def _cleanup_on_exit(self):
        """종료 시 정리 작업"""
        # 프로세스 모니터링 중지
        if self.process_monitor:
            self.process_monitor.stop_monitoring()
        
        # PID 파일 정리
        self._cleanup_pid_file()
        
        logger.info("데몬 프로세스 정리 완료")
    
    def _redirect_standard_files(self):
        """표준 입출력을 /dev/null로 리다이렉션"""
        try:
            # stdin을 /dev/null로
            with open('/dev/null', 'r') as dev_null:
                os.dup2(dev_null.fileno(), sys.stdin.fileno())
            
            # stdout, stderr를 로그 파일로 (또는 /dev/null)
            # 여기서는 로깅 시스템이 있으므로 /dev/null로 리다이렉션
            with open('/dev/null', 'w') as dev_null:
                os.dup2(dev_null.fileno(), sys.stdout.fileno())
                os.dup2(dev_null.fileno(), sys.stderr.fileno())
                
        except Exception as e:
            logger.error(f"표준 파일 리다이렉션 실패: {e}")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        logger.info(f"시그널 수신: {signum}")
        
        if signum in (signal.SIGTERM, signal.SIGINT):
            logger.info("종료 시그널 수신, 정리 작업 시작")
            self._cleanup_pid_file()
            sys.exit(0)


class ServiceStatus:
    """서비스 상태 정보 클래스"""
    
    def __init__(self, daemon_manager: DaemonManager):
        self.daemon_manager = daemon_manager
    
    def get_status_info(self) -> dict:
        """서비스 상태 정보 반환"""
        is_running = self.daemon_manager.is_running()
        pid = self.daemon_manager.get_pid() if is_running else None
        
        status_info = {
            'running': is_running,
            'pid': pid,
            'uptime': self._get_uptime(pid) if pid else None,
            'memory_usage': self._get_memory_usage(pid) if pid else None,
            'cpu_usage': self._get_cpu_usage(pid) if pid else None,
        }
        
        # 프로세스 모니터링 정보 추가
        if is_running and self.daemon_manager.process_monitor:
            try:
                health_check = self.daemon_manager.process_monitor.get_health_status()
                status_info.update({
                    'health_status': health_check.status,
                    'error_count': health_check.error_count,
                    'last_error': health_check.last_error,
                    'last_heartbeat': health_check.timestamp
                })
            except Exception as e:
                logger.warning(f"헬스체크 정보 수집 실패: {e}")
        
        # 자동 재시작 정보 추가
        if self.daemon_manager.auto_restart_manager:
            try:
                restart_info = self.daemon_manager.auto_restart_manager.get_restart_info()
                status_info['restart_info'] = restart_info
            except Exception as e:
                logger.warning(f"재시작 정보 수집 실패: {e}")
        
        return status_info
    
    def _get_uptime(self, pid: int) -> Optional[str]:
        """프로세스 업타임 반환"""
        try:
            import psutil
            process = psutil.Process(pid)
            create_time = process.create_time()
            uptime_seconds = time.time() - create_time
            
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            seconds = int(uptime_seconds % 60)
            
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
        except (ImportError, Exception):
            return None
    
    def _get_memory_usage(self, pid: int) -> Optional[str]:
        """메모리 사용량 반환"""
        try:
            import psutil
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            return f"{memory_mb:.1f} MB"
            
        except (ImportError, Exception):
            return None
    
    def _get_cpu_usage(self, pid: int) -> Optional[str]:
        """CPU 사용률 반환"""
        try:
            import psutil
            process = psutil.Process(pid)
            cpu_percent = process.cpu_percent(interval=1)
            return f"{cpu_percent:.1f}%"
            
        except (ImportError, Exception):
            return None
