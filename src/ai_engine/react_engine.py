"""
ReAct 엔진 - 모듈화된 버전

기존의 단일 파일을 여러 모듈로 분리하여 유지보수성과 가독성을 향상시킨 버전
"""

# 하위 호환성을 위해 기존 import 구조 유지
from .react_engine.core import ReactEngine

__all__ = ['ReactEngine']
