"""
macOS 시스템 알림 모니터링 시스템

macOS Notification Center의 알림을 실시간으로 감지하고 
중요도를 판단하여 Agentic AI에게 전달하는 시스템입니다.
"""

import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Callable
from dataclasses import dataclass
from loguru import logger

@dataclass
class NotificationData:
    """알림 데이터 구조"""
    app_name: str
    title: str
    body: str
    timestamp: datetime
    bundle_id: str
    is_delivered: bool = True
    urgency_level: str = "normal"  # low, normal, high, critical
    action_required: bool = False

class MacOSNotificationMonitor:
    """macOS 알림 모니터링 클래스"""
    
    def __init__(self):
        self.is_monitoring = False
        self.notification_callbacks: List[Callable] = []
        self.filtered_apps: set = {
            "com.apple.dt.Xcode",  # Xcode 빌드 알림 제외
            "com.apple.loginwindow",  # 로그인 창 알림 제외
            "com.apple.Finder"  # Finder 알림 제외
        }
        
        # 중요한 키워드들 (높은 우선순위)
        self.high_priority_keywords = {
            "긴급", "urgent", "중요", "important", "deadline", "meeting", "회의",
            "승인", "approval", "결제", "payment", "오류", "error", "실패", "failed"
        }
        
        # 스팸성 키워드들 (낮은 우선순위)
        self.low_priority_keywords = {
            "광고", "ad", "promotion", "newsletter", "업데이트", "update",
            "알림", "notification", "spam", "marketing"
        }
        
        logger.info("macOS 알림 모니터링 시스템 초기화 완료")
    
    def add_notification_callback(self, callback: Callable):
        """알림 콜백 함수 등록"""
        self.notification_callbacks.append(callback)
        logger.info(f"알림 콜백 등록: {callback.__name__}")
    
    async def start_monitoring(self):
        """알림 모니터링 시작"""
        if self.is_monitoring:
            logger.warning("이미 모니터링이 실행 중입니다")
            return
        
        self.is_monitoring = True
        logger.info("🔔 macOS 알림 모니터링 시작")
        
        try:
            await self._run_notification_listener()
        except KeyboardInterrupt:
            logger.info("모니터링이 중단되었습니다")
        except Exception as e:
            logger.error(f"모니터링 중 오류 발생: {e}")
        finally:
            self.is_monitoring = False
    
    def stop_monitoring(self):
        """알림 모니터링 중지"""
        self.is_monitoring = False
        logger.info("알림 모니터링 중지")
    
    async def _run_notification_listener(self):
        """실제 알림 리스너 실행"""
        # AppleScript를 이용한 알림 모니터링
        applescript = '''
        on run
            tell application "System Events"
                -- 알림 센터 모니터링을 위한 준비
                return "알림 모니터링 준비 완료"
            end tell
        end run
        '''
        
        # 시뮬레이션용 테스트 알림들
        test_notifications = [
            {
                "app": "Mail",
                "title": "새 메일",
                "body": "프로젝트 승인 요청이 도착했습니다",
                "bundle": "com.apple.mail"
            },
            {
                "app": "Calendar",
                "title": "회의 알림",
                "body": "10분 후 팀 미팅이 시작됩니다",
                "bundle": "com.apple.iCal"
            },
            {
                "app": "Messages",
                "title": "새 메시지",
                "body": "회의 시간이 변경되었습니다",
                "bundle": "com.apple.MobileSMS"
            }
        ]
        
        logger.info("테스트 알림 모니터링 모드로 실행")
        
        for i, notif_data in enumerate(test_notifications):
            if not self.is_monitoring:
                break
                
            # 테스트 알림 생성
            notification = NotificationData(
                app_name=notif_data["app"],
                title=notif_data["title"],
                body=notif_data["body"],
                timestamp=datetime.now(),
                bundle_id=notif_data["bundle"]
            )
            
            # 중요도 분석
            await self._analyze_notification_urgency(notification)
            
            # 콜백 함수들에게 알림 전달
            await self._notify_callbacks(notification)
            
            # 다음 테스트 알림까지 대기
            await asyncio.sleep(5)
        
        logger.info("테스트 알림 모니터링 완료")
    
    async def _analyze_notification_urgency(self, notification: NotificationData):
        """알림 중요도 분석"""
        text_content = f"{notification.title} {notification.body}".lower()
        
        # 높은 우선순위 키워드 검사
        high_priority_found = any(keyword in text_content for keyword in self.high_priority_keywords)
        
        # 낮은 우선순위 키워드 검사
        low_priority_found = any(keyword in text_content for keyword in self.low_priority_keywords)
        
        # 시간 기반 우선순위 (회의 알림 등)
        time_urgent = any(time_word in text_content for time_word in 
                         ["분 후", "곧", "soon", "now", "즉시", "immediately"])
        
        # 중요도 결정
        if high_priority_found or time_urgent:
            notification.urgency_level = "high"
            notification.action_required = True
        elif low_priority_found:
            notification.urgency_level = "low"
            notification.action_required = False
        else:
            notification.urgency_level = "normal"
            notification.action_required = self._determine_action_needed(notification)
        
        logger.info(f"알림 분석 완료: {notification.app_name} - {notification.urgency_level} 우선순위")
    
    def _determine_action_needed(self, notification: NotificationData) -> bool:
        """액션이 필요한지 판단"""
        action_keywords = {
            "승인", "approval", "확인", "confirm", "응답", "reply", "회신", "response",
            "참석", "attend", "예약", "booking", "결제", "payment", "주문", "order"
        }
        
        text_content = f"{notification.title} {notification.body}".lower()
        return any(keyword in text_content for keyword in action_keywords)
    
    async def _notify_callbacks(self, notification: NotificationData):
        """등록된 콜백 함수들에게 알림 전달"""
        for callback in self.notification_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(notification)
                else:
                    callback(notification)
            except Exception as e:
                logger.error(f"콜백 실행 중 오류: {callback.__name__}: {e}")
    
    async def get_recent_notifications(self, hours: int = 1) -> List[NotificationData]:
        """최근 알림 목록 조회"""
        # 실제 구현시에는 macOS 알림 데이터베이스에서 조회
        # 현재는 시뮬레이션 데이터 반환
        return []
    
    def get_monitoring_status(self) -> Dict[str, Any]:
        """모니터링 상태 조회"""
        return {
            "is_monitoring": self.is_monitoring,
            "callback_count": len(self.notification_callbacks),
            "filtered_apps": list(self.filtered_apps),
            "high_priority_keywords": list(self.high_priority_keywords),
            "low_priority_keywords": list(self.low_priority_keywords)
        }


# 실제 macOS 알림 API 사용을 위한 헬퍼 함수들

def get_macos_notifications_via_applescript() -> List[Dict[str, str]]:
    """AppleScript를 통한 실제 알림 조회"""
    try:
        # 실제 macOS 알림 센터에서 알림 조회하는 AppleScript
        applescript = '''
        tell application "System Events"
            tell process "NotificationCenter"
                try
                    set notifList to {}
                    -- 여기에 실제 알림 조회 로직 구현
                    return notifList
                end try
            end tell
        end tell
        '''
        
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # 결과 파싱 및 반환
            return []
        else:
            logger.error(f"AppleScript 실행 실패: {result.stderr}")
            return []
            
    except Exception as e:
        logger.error(f"알림 조회 중 오류: {e}")
        return []

async def main():
    """테스트 메인 함수"""
    monitor = MacOSNotificationMonitor()
    
    # 테스트 콜백 함수
    async def test_callback(notification: NotificationData):
        print(f"\n📱 새 알림 수신:")
        print(f"   앱: {notification.app_name}")
        print(f"   제목: {notification.title}")
        print(f"   내용: {notification.body}")
        print(f"   우선순위: {notification.urgency_level}")
        print(f"   액션 필요: {notification.action_required}")
        print(f"   시간: {notification.timestamp.strftime('%H:%M:%S')}")
    
    # 콜백 등록
    monitor.add_notification_callback(test_callback)
    
    # 모니터링 시작
    await monitor.start_monitoring()

if __name__ == "__main__":
    asyncio.run(main())
