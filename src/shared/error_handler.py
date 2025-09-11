"""
고도화된 에러 처리 시스템

이 모듈은 Personal AI Assistant의 전역 에러 처리, 재시도 전략, 에러 보고 시스템을 제공합니다.
"""

import asyncio
import functools
import logging
import traceback
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """에러 심각도 레벨"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """에러 카테고리"""
    NETWORK = "network"
    API = "api"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    SYSTEM = "system"
    USER_INPUT = "user_input"
    EXTERNAL_SERVICE = "external_service"
    UNKNOWN = "unknown"


class AISystemError(Exception):
    """시스템 관련 에러"""
    def __init__(self, message: str, context: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class AINetworkError(Exception):
    """네트워크 관련 에러"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AIValidationError(Exception):
    """검증 관련 에러"""
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass
class ErrorContext:
    """에러 컨텍스트 정보"""
    error_id: str
    timestamp: datetime
    severity: ErrorSeverity
    category: ErrorCategory
    component: str
    operation: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """재시도 설정"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (Exception,)
    non_retryable_exceptions: tuple = ()


class PersonalAIError(Exception):
    """Personal AI Assistant 기본 에러 클래스"""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        component: str = "unknown",
        operation: str = "unknown",
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.component = component
        self.operation = operation
        self.original_error = original_error
        self.context = context or {}
        self.timestamp = datetime.now()
        self.error_id = f"{component}_{operation}_{int(time.time())}"


class NetworkError(PersonalAIError):
    """네트워크 관련 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.NETWORK, **kwargs)


class APIError(PersonalAIError):
    """API 관련 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.API, **kwargs)


class DatabaseError(PersonalAIError):
    """데이터베이스 관련 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.DATABASE, **kwargs)


class AuthenticationError(PersonalAIError):
    """인증 관련 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.AUTHENTICATION, severity=ErrorSeverity.HIGH, **kwargs)


class ValidationError(PersonalAIError):
    """유효성 검사 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.VALIDATION, severity=ErrorSeverity.LOW, **kwargs)


class SystemError(PersonalAIError):
    """시스템 관련 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, category=ErrorCategory.SYSTEM, severity=ErrorSeverity.HIGH, **kwargs)


class ErrorReporter:
    """에러 보고 시스템"""
    
    def __init__(self):
        self.error_history: List[ErrorContext] = []
        self.error_counts: Dict[str, int] = {}
        self.last_report_time: Dict[str, datetime] = {}
    
    def report_error(
        self,
        error: Exception,
        component: str = "unknown",
        operation: str = "unknown",
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorContext:
        """에러 보고"""
        
        # PersonalAIError인 경우 기존 정보 사용
        if isinstance(error, PersonalAIError):
            severity = error.severity
            category = error.category
            error_component = error.component
            error_operation = error.operation
            error_context = error.context
        else:
            # 일반 예외인 경우 분류
            severity = self._classify_severity(error)
            category = self._classify_category(error)
            error_component = component
            error_operation = operation
            error_context = context or {}
        
        # 에러 컨텍스트 생성
        error_ctx = ErrorContext(
            error_id=f"{error_component}_{error_operation}_{int(time.time())}",
            timestamp=datetime.now(),
            severity=severity,
            category=category,
            component=error_component,
            operation=error_operation,
            additional_data=error_context
        )
        
        # 에러 히스토리에 추가
        self.error_history.append(error_ctx)
        
        # 에러 카운트 증가
        error_key = f"{error_component}_{error_operation}_{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # 로깅
        self._log_error(error, error_ctx)
        
        # 심각한 에러인 경우 즉시 알림
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._send_alert(error, error_ctx)
        
        return error_ctx
    
    def _classify_severity(self, error: Exception) -> ErrorSeverity:
        """에러 심각도 자동 분류"""
        error_type = type(error).__name__
        
        # 심각한 에러들
        if any(keyword in error_type.lower() for keyword in ['critical', 'fatal', 'system']):
            return ErrorSeverity.CRITICAL
        
        # 높은 심각도 에러들
        if any(keyword in error_type.lower() for keyword in ['auth', 'permission', 'security']):
            return ErrorSeverity.HIGH
        
        # 중간 심각도 에러들
        if any(keyword in error_type.lower() for keyword in ['connection', 'timeout', 'api']):
            return ErrorSeverity.MEDIUM
        
        # 낮은 심각도 에러들
        if any(keyword in error_type.lower() for keyword in ['validation', 'input', 'format']):
            return ErrorSeverity.LOW
        
        return ErrorSeverity.MEDIUM
    
    def _classify_category(self, error: Exception) -> ErrorCategory:
        """에러 카테고리 자동 분류"""
        error_type = type(error).__name__.lower()
        error_msg = str(error).lower()
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['network', 'connection', 'timeout']):
            return ErrorCategory.NETWORK
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['api', 'http', 'rest']):
            return ErrorCategory.API
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['database', 'sql', 'db']):
            return ErrorCategory.DATABASE
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['auth', 'token', 'permission']):
            return ErrorCategory.AUTHENTICATION
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['validation', 'invalid', 'format']):
            return ErrorCategory.VALIDATION
        
        if any(keyword in error_type or keyword in error_msg for keyword in ['system', 'os', 'file']):
            return ErrorCategory.SYSTEM
        
        return ErrorCategory.UNKNOWN
    
    def _log_error(self, error: Exception, context: ErrorContext):
        """에러 로깅"""
        log_data = {
            "error_id": context.error_id,
            "timestamp": context.timestamp.isoformat(),
            "severity": context.severity.value,
            "category": context.category.value,
            "component": context.component,
            "operation": context.operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context.additional_data
        }
        
        if context.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {json.dumps(log_data, indent=2)}")
        elif context.severity == ErrorSeverity.HIGH:
            logger.error(f"HIGH SEVERITY ERROR: {json.dumps(log_data, indent=2)}")
        elif context.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"MEDIUM SEVERITY ERROR: {json.dumps(log_data, indent=2)}")
        else:
            logger.info(f"LOW SEVERITY ERROR: {json.dumps(log_data, indent=2)}")
    
    def _send_alert(self, error: Exception, context: ErrorContext):
        """심각한 에러 알림 발송"""
        # TODO: Discord 채널이나 이메일로 알림 발송
        logger.error(f"🚨 ALERT: {context.severity.value.upper()} error in {context.component}: {str(error)}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """에러 통계 반환"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        last_hour = now - timedelta(hours=1)
        
        # 최근 24시간 에러
        recent_errors = [e for e in self.error_history if e.timestamp >= last_24h]
        
        # 최근 1시간 에러
        hourly_errors = [e for e in self.error_history if e.timestamp >= last_hour]
        
        # 심각도별 통계
        severity_stats = {}
        for severity in ErrorSeverity:
            severity_stats[severity.value] = len([e for e in recent_errors if e.severity == severity])
        
        # 카테고리별 통계
        category_stats = {}
        for category in ErrorCategory:
            category_stats[category.value] = len([e for e in recent_errors if e.category == category])
        
        return {
            "total_errors_24h": len(recent_errors),
            "total_errors_1h": len(hourly_errors),
            "severity_breakdown": severity_stats,
            "category_breakdown": category_stats,
            "error_counts": self.error_counts,
            "most_frequent_errors": sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        }


class RetryHandler:
    """재시도 처리기"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
    
    def retry(
        self,
        func: Optional[Callable] = None,
        *,
        max_attempts: Optional[int] = None,
        base_delay: Optional[float] = None,
        max_delay: Optional[float] = None,
        exponential_base: Optional[float] = None,
        jitter: Optional[bool] = None,
        retryable_exceptions: Optional[tuple] = None,
        non_retryable_exceptions: Optional[tuple] = None
    ):
        """재시도 데코레이터"""
        
        # 설정 오버라이드
        config = RetryConfig(
            max_attempts=max_attempts or self.config.max_attempts,
            base_delay=base_delay or self.config.base_delay,
            max_delay=max_delay or self.config.max_delay,
            exponential_base=exponential_base or self.config.exponential_base,
            jitter=jitter if jitter is not None else self.config.jitter,
            retryable_exceptions=retryable_exceptions or self.config.retryable_exceptions,
            non_retryable_exceptions=non_retryable_exceptions or self.config.non_retryable_exceptions
        )
        
        def decorator(f):
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                return self._execute_with_retry(f, config, *args, **kwargs)
            
            @functools.wraps(f)
            async def async_wrapper(*args, **kwargs):
                return await self._execute_with_retry_async(f, config, *args, **kwargs)
            
            if asyncio.iscoroutinefunction(f):
                return async_wrapper
            else:
                return wrapper
        
        if func is None:
            return decorator
        else:
            return decorator(func)
    
    def _execute_with_retry(self, func: Callable, config: RetryConfig, *args, **kwargs):
        """동기 함수 재시도 실행"""
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                return func(*args, **kwargs)
            except config.non_retryable_exceptions:
                # 재시도하지 않는 예외는 즉시 re-raise
                raise
            except config.retryable_exceptions as e:
                last_exception = e
                
                if attempt == config.max_attempts - 1:
                    # 마지막 시도였으면 예외 발생
                    break
                
                # 지연 시간 계산
                delay = self._calculate_delay(attempt, config)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                time.sleep(delay)
        
        # 모든 재시도 실패
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("모든 재시도가 실패했습니다")
    
    async def _execute_with_retry_async(self, func: Callable, config: RetryConfig, *args, **kwargs):
        """비동기 함수 재시도 실행"""
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                return await func(*args, **kwargs)
            except config.non_retryable_exceptions:
                # 재시도하지 않는 예외는 즉시 re-raise
                raise
            except config.retryable_exceptions as e:
                last_exception = e
                
                if attempt == config.max_attempts - 1:
                    # 마지막 시도였으면 예외 발생
                    break
                
                # 지연 시간 계산
                delay = self._calculate_delay(attempt, config)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_attempts} failed: {str(e)}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                
                await asyncio.sleep(delay)
        
        # 모든 재시도 실패
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("모든 재시도가 실패했습니다")
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """지연 시간 계산 (지수 백오프 + 지터)"""
        delay = config.base_delay * (config.exponential_base ** attempt)
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            # 지터 추가 (±25%)
            import random
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class GlobalErrorHandler:
    """전역 에러 핸들러"""
    
    def __init__(self):
        self.reporter = ErrorReporter()
        self.retry_handler = RetryHandler()
        self._original_excepthook: Optional[Callable] = None
    
    def install_global_handler(self):
        """전역 예외 핸들러 설치"""
        import sys
        
        self._original_excepthook = sys.excepthook
        sys.excepthook = self._handle_exception
    
    def uninstall_global_handler(self):
        """전역 예외 핸들러 제거"""
        import sys
        
        if self._original_excepthook:
            sys.excepthook = self._original_excepthook
    
    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        """전역 예외 처리"""
        # 시스템 종료 관련 예외는 처리하지 않음
        if issubclass(exc_type, KeyboardInterrupt):
            if self._original_excepthook:
                return self._original_excepthook(exc_type, exc_value, exc_traceback)
            return
        
        # 에러 보고
        self.reporter.report_error(
            exc_value,
            component="global",
            operation="unhandled_exception",
            context={
                "exc_type": exc_type.__name__,
                "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback)
            }
        )
        
        # 원본 핸들러 호출
        if self._original_excepthook:
            return self._original_excepthook(exc_type, exc_value, exc_traceback)


# 전역 인스턴스
global_error_handler = GlobalErrorHandler()
error_reporter = global_error_handler.reporter
retry_handler = global_error_handler.retry_handler


def handle_errors(
    component: str,
    operation: str = "unknown",
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    category: ErrorCategory = ErrorCategory.UNKNOWN,
    reraise: bool = True
):
    """에러 처리 데코레이터"""
    
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_reporter.report_error(
                    e,
                    component=component,
                    operation=operation,
                    context={"args": str(args), "kwargs": str(kwargs)}
                )
                
                if reraise:
                    raise
                
                return None
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_reporter.report_error(
                    e,
                    component=component,
                    operation=operation,
                    context={"args": str(args), "kwargs": str(kwargs)}
                )
                
                if reraise:
                    raise
                
                return None
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return wrapper
    
    return decorator


def retry_on_failure(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    non_retryable_exceptions: tuple = ()
):
    """재시도 데코레이터 (편의 함수)"""
    return retry_handler.retry(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions
    )


# 모듈 초기화 시 전역 핸들러 설치
global_error_handler.install_global_handler()
logger.info("고도화된 에러 처리 시스템이 초기화되었습니다.")
