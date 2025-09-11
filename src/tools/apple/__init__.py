"""
Apple Tools Module

Apple 생태계 통합 도구들을 제공합니다.
- IntelligentAutoResponder: 지능형 알림 자동 응답
- AppleNotesTool: Apple Notes 통합  
- MacOSNotificationMonitor: macOS 알림 모니터링
"""

from .auto_responder import IntelligentAutoResponder, NotificationAutoResponseSystem, AutoResponseAction
from .notes_tool import AppleNotesTool
from .notification_monitor import MacOSNotificationMonitor, NotificationData

__all__ = [
    "IntelligentAutoResponder",
    "NotificationAutoResponseSystem", 
    "AutoResponseAction",
    "AppleNotesTool",
    "MacOSNotificationMonitor",
    "NotificationData"
]
