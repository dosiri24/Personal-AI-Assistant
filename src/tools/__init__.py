"""
Tools Module (리팩토링됨)

새로운 모듈 구조:
- base/: 도구 기본 클래스들
- core/: 핵심 시스템 도구들 (Calculator, SystemTime, Filesystem)
- apple/: Apple 생태계 통합 도구들
- notion/: Notion 통합 도구들
- web_scraper/: 웹 스크래핑 도구들
"""

# Base classes
from .base import (
    ParameterType, ToolCategory, ExecutionStatus,
    ToolParameter, ToolMetadata, ToolResult, BaseTool
)

# Core tools
from .core import CalculatorTool, SystemTimeTool, SimpleFilesystemTool

# Apple tools  
from .apple import (
    IntelligentAutoResponder, NotificationAutoResponseSystem, 
    AppleNotesTool, MacOSNotificationMonitor, NotificationData
)

# Notion tools
from .notion import NotionClient, CalendarTool, TodoTool

# Web scraper tools
try:
    from .web_scraper import WebScraperTool, HTMLAnalyzer
except ImportError:
    WebScraperTool = None
    HTMLAnalyzer = None

# Registry
from .registry import ToolRegistry

__all__ = [
    # Base classes
    "ParameterType", "ToolCategory", "ExecutionStatus",
    "ToolParameter", "ToolMetadata", "ToolResult", "BaseTool",
    
    # Core tools
    "CalculatorTool", "SystemTimeTool", "SimpleFilesystemTool",
    
    # Apple tools
    "IntelligentAutoResponder", "NotificationAutoResponseSystem", 
    "AppleNotesTool", "MacOSNotificationMonitor", "NotificationData",
    
    # Notion tools  
    "NotionClient", "CalendarTool", "TodoTool",
    
    # Web scraper tools
    "WebScraperTool", "HTMLAnalyzer",
    
    # Registry
    "ToolRegistry"
]
