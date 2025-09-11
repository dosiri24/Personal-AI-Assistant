"""
간소화된 에러 핸들링 시스템

Personal AI Assistant의 기본적인 에러 처리 기능을 제공합니다.
"""

import time
import traceback
from typing import Any, Callable, Optional, Type
from functools import wraps

from .logger import get_logger

logger = get_logger(__name__)


class AISystemError(Exception):
    """AI 시스템 관련 에러"""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code or "AI_SYSTEM_ERROR"
        super().__init__(self.message)


class AINetworkError(AISystemError):
    """네트워크 관련 에러"""
    
    def __init__(self, message: str, status_code: Optional[int] = None):
        self.status_code = status_code
        super().__init__(message, "AI_NETWORK_ERROR")


class AIValidationError(AISystemError):
    """데이터 검증 관련 에러"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message, "AI_VALIDATION_ERROR")


class SimpleErrorHandler:
    """간소화된 에러 핸들러"""
    
    def __init__(self):
        self.error_count = 0
        self.last_error_time = None
    
    def handle_error(self, error: Exception, context: str = ""):
        """에러 처리"""
        self.error_count += 1
        self.last_error_time = time.time()
        
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        if isinstance(error, AISystemError):
            logger.error(f"AI 시스템 에러 [{error.error_code}]: {error.message}")
        else:
            logger.error(f"일반 에러 in {context}: {error}")
        
        return error_info
    
    def handle_errors(self, func: Callable) -> Callable:
        """에러 처리 데코레이터"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.handle_error(e, func.__name__)
                raise
        return wrapper
    
    def get_error_statistics(self):
        """에러 통계 반환"""
        return {
            "total_errors": self.error_count,
            "last_error_time": self.last_error_time
        }


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """실패 시 재시도 데코레이터"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"{func.__name__} 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 최종 실패: {e}")
            
            # 모든 재시도 실패시 마지막 예외를 발생
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError(f"{func.__name__}: 알 수 없는 오류로 실패")
        
        return wrapper
    return decorator


# 전역 에러 핸들러 인스턴스
global_error_handler = SimpleErrorHandler()


def handle_error(error: Exception, context: str = ""):
    """전역 에러 처리 함수"""
    return global_error_handler.handle_error(error, context)


def safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """안전한 함수 실행"""
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        handle_error(e, f"safe_execute({func.__name__})")
        return False, None
