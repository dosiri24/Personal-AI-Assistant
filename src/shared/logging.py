"""
통합 로깅 시스템

구조화된 로깅과 성능 메트릭을 지원하는 로깅 시스템입니다.
"""

import logging
import json
import time
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """구조화된 로그 포맷터 (JSON)"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 예외 정보 포함
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # 추가 컨텍스트 정보
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        if hasattr(record, "session_id"):
            log_entry["session_id"] = record.session_id
        if hasattr(record, "execution_time"):
            log_entry["execution_time"] = record.execution_time
        
        return json.dumps(log_entry, ensure_ascii=False)


class PerformanceLogger:
    """성능 측정용 로거"""
    
    def __init__(self, logger: logging.Logger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.info(f"시작: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            execution_time = time.time() - self.start_time
            if exc_type:
                self.logger.error(
                    f"실패: {self.operation} ({execution_time:.2f}초)",
                    extra={"execution_time": execution_time, "operation": self.operation}
                )
            else:
                self.logger.info(
                    f"완료: {self.operation} ({execution_time:.2f}초)",
                    extra={"execution_time": execution_time, "operation": self.operation}
                )


def setup_logging(
    log_level: str = "INFO",
    logs_dir: str = "logs",
    enable_console: bool = True,
    enable_file: bool = True,
    enable_structured: bool = True
) -> None:
    """로깅 시스템 설정"""
    
    # 로그 디렉토리 생성
    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        if enable_structured:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
        root_logger.addHandler(console_handler)
    
    # 파일 핸들러
    if enable_file:
        # 메인 로그 파일
        file_handler = logging.FileHandler(
            logs_path / "personal_ai_assistant.log",
            encoding="utf-8"
        )
        if enable_structured:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
        root_logger.addHandler(file_handler)
        
        # 에러 전용 로그 파일
        error_handler = logging.FileHandler(
            logs_path / "errors.log",
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        if enable_structured:
            error_handler.setFormatter(StructuredFormatter())
        else:
            error_handler.setFormatter(
                logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
            )
        root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """로거 인스턴스 반환"""
    return logging.getLogger(name)


def log_performance(logger: logging.Logger, operation: str):
    """성능 측정 데코레이터"""
    return PerformanceLogger(logger, operation)


# 컨텍스트 로거 클래스
class ContextLogger:
    """컨텍스트 정보를 포함한 로거"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
    
    def _log_with_context(self, level: int, message: str, **kwargs):
        """컨텍스트와 함께 로그 기록"""
        extra = {**self.context, **kwargs}
        self.logger.log(level, message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        self._log_with_context(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log_with_context(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log_with_context(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log_with_context(logging.CRITICAL, message, **kwargs)


def get_context_logger(name: str, **context) -> ContextLogger:
    """컨텍스트 로거 생성"""
    logger = get_logger(name)
    return ContextLogger(logger, **context)