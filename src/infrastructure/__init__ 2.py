"""
Infrastructure Layer

시스템의 인프라스트럭처 관련 구성 요소를 제공합니다.
- 데몬 프로세스 관리
- 프로세스 생명주기 관리
"""

from .daemon import DaemonManager

__all__ = [
    'DaemonManager'
]
