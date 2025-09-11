"""
Apple Integration Module

Apple 앱들과의 통합을 위한 모듈입니다.
- Apple MCP 클라이언트들
- Apple 앱 도구들
- Apple MCP 서버 관리자
"""

from .apple_agent_v2 import AppleAppsAgent
from .apple_client import (
    AppleAppsManager, 
    AppleApp,
    AppleMCPManager,
    AppleMCPClient,
    autostart_if_configured
)
from .apple_tools import (
    AppleContactsTool,
    AppleNotesTool, 
    AppleMessagesTool,
    AppleMailTool,
    AppleRemindersTool,
    AppleCalendarTool,
    AppleMapsTool,
    register_apple_tools
)

__all__ = [
    "AppleAppsAgent",
    "AppleAppsManager", 
    "AppleApp",
    "AppleMCPManager",
    "AppleMCPClient",
    "autostart_if_configured",
    "AppleContactsTool",
    "AppleNotesTool",
    "AppleMessagesTool", 
    "AppleMailTool",
    "AppleRemindersTool",
    "AppleCalendarTool",
    "AppleMapsTool",
    "register_apple_tools"
]
