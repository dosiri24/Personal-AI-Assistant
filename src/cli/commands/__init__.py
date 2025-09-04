"""
CLI Commands Module

이 모듈은 Personal AI Assistant의 모든 CLI 명령어들을 기능별로 분리하여 관리합니다.
"""

from .service_commands import register_service_commands
from .test_commands import register_test_commands
from .maintenance_commands import register_maintenance_commands
from .ai_commands import register_ai_commands
from .tools_commands import register_tools_commands
from .notion_commands import register_notion_commands

__all__ = [
    'register_service_commands',
    'register_test_commands', 
    'register_maintenance_commands',
    'register_ai_commands',
    'register_tools_commands',
    'register_notion_commands'
]
