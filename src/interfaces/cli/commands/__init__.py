"""
CLI Commands Package

이 패키지는 CLI 명령어들을 기능별로 모듈화한 것입니다.
각 모듈은 관련된 명령어들을 그룹화하여 관리합니다.
"""

from .service import service_commands
from .testing import testing_commands  
from .monitoring import monitoring_commands
from .tools import tools_group
from .notion import notion_group
from .optimization import optimization_commands
from .apple_commands import apple_commands
from .apple_apps_commands import apple_apps

__all__ = [
    'service_commands',
    'testing_commands', 
    'monitoring_commands',
    'tools_group',
    'notion_group',
    'optimization_commands',
    'apple_commands',
    'apple_apps'
]
