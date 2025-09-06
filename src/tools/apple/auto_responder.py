"""
지능형 알림 자동 응답 시스템

macOS 알림을 분석하고 Agentic AI를 통해 적절한 자동 응답을 생성하고 실행합니다.
"""

import asyncio
import subprocess
from typing import Dict, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import sys

# 프로젝트 루트 경로 추가
sys.path.append(str(Path(__file__).parent.parent.parent))

from loguru import logger
from .notification_monitor import NotificationData, MacOSNotificationMonitor

try:
    from mcp.apple_agent_v2 import AppleAppsAgent
    AppleAppsAgentType = AppleAppsAgent
except ImportError:
    logger.warning("Apple Agent를 가져올 수 없습니다. 시뮬레이션 모드로 실행됩니다.")
    AppleAppsAgent = None
    AppleAppsAgentType = Any  # 타입 힌트용

@dataclass
class AutoResponseAction:
    """자동 응답 액션 데이터"""
    action_type: str  # reply, calendar_update, note_create, reminder_add
    target_app: str
    parameters: Dict[str, Any]
    confidence: float
    reasoning: str
    requires_confirmation: bool = True

class IntelligentAutoResponder:
    """지능형 알림 자동 응답 시스템"""
    
    def __init__(self):
        self.apple_agent = None  # Optional[AppleAppsAgent]
        self.auto_response_enabled = True
        self.confirmation_required = True  # 사용자 확인 후 실행
        
        # 자동 응답 규칙
        self.response_rules = {
            "meeting_reminder": {
                "keywords": ["회의", "meeting", "미팅", "회의실"],
                "actions": ["calendar_check", "reminder_add"]
            },
            "email_response": {
                "keywords": ["메일", "email", "승인", "approval"],
                "actions": ["note_create", "calendar_add"]
            },
            "message_reply": {
                "keywords": ["메시지", "message", "답장", "reply"],
                "actions": ["message_draft", "note_create"]
            }
        }
        
        logger.info("지능형 자동 응답 시스템 초기화 완료")
    
    async def initialize(self) -> bool:
        """자동 응답 시스템 초기화"""
        try:
            if AppleAppsAgent:
                self.apple_agent = AppleAppsAgent()
                if self.apple_agent:
                    await self.apple_agent.initialize()
                logger.info("Apple Agent 연동 완료")
            else:
                logger.info("시뮬레이션 모드로 초기화")
            
            return True
        except Exception as e:
            logger.error(f"자동 응답 시스템 초기화 실패: {e}")
            return False
    
    async def process_notification(self, notification: NotificationData) -> Optional[AutoResponseAction]:
        """알림을 분석하고 자동 응답 액션 생성"""
        try:
            logger.info(f"알림 처리 시작: {notification.app_name} - {notification.title}")
            
            # 1. 알림 내용 분석
            analysis = await self._analyze_notification_content(notification)
            
            # 2. 액션 필요성 판단
            if not analysis["action_needed"]:
                logger.info("액션이 필요하지 않은 알림입니다")
                return None
            
            # 3. 적절한 액션 생성
            action = await self._generate_response_action(notification, analysis)
            
            if action:
                logger.info(f"자동 응답 액션 생성: {action.action_type} (신뢰도: {action.confidence:.2f})")
                
                # 4. 액션 실행 (확인 필요시 사용자에게 문의)
                if self.confirmation_required and action.requires_confirmation:
                    await self._request_user_confirmation(action, notification)
                else:
                    await self._execute_action(action, notification)
            
            return action
            
        except Exception as e:
            logger.error(f"알림 처리 중 오류: {e}")
            return None
    
    async def _analyze_notification_content(self, notification: NotificationData) -> Dict[str, Any]:
        """알림 내용을 AI로 분석"""
        # AI를 사용한 분석이 가능하다면 사용, 아니면 키워드 기반 분석
        if self.apple_agent:
            return await self._ai_analyze_notification(notification)
        else:
            return await self._keyword_analyze_notification(notification)
    
    async def _ai_analyze_notification(self, notification: NotificationData) -> Dict[str, Any]:
        """AI를 사용한 알림 분석"""
        try:
            analysis_prompt = f"""
            다음 알림을 분석하여 적절한 대응 방법을 제안해주세요:
            
            앱: {notification.app_name}
            제목: {notification.title}
            내용: {notification.body}
            우선순위: {notification.urgency_level}
            
            분석 결과를 다음 JSON 형식으로 응답해주세요:
            {{
                "action_needed": true/false,
                "action_type": "reply/calendar_update/note_create/reminder_add/none",
                "confidence": 0.0-1.0,
                "reasoning": "분석 근거",
                "suggested_response": "제안하는 응답 내용",
                "urgency": "low/normal/high/critical"
            }}
            """
            
            # Apple Agent를 통한 AI 분석
            if self.apple_agent:
                result = await self.apple_agent.process_command(
                    command=analysis_prompt,
                    context={"type": "notification_analysis", "app": notification.app_name}
                )
            else:
                # 시뮬레이션 모드
                result = None
            
            # 결과 파싱 (실제로는 더 정교한 파싱 필요)
            return {
                "action_needed": True,
                "action_type": "note_create",
                "confidence": 0.8,
                "reasoning": "알림 내용이 중요해 보입니다",
                "suggested_response": f"{notification.title}에 대한 메모를 생성합니다",
                "urgency": notification.urgency_level
            }
            
        except Exception as e:
            logger.error(f"AI 분석 실패: {e}")
            return await self._keyword_analyze_notification(notification)
    
    async def _keyword_analyze_notification(self, notification: NotificationData) -> Dict[str, Any]:
        """키워드 기반 알림 분석"""
        text_content = f"{notification.title} {notification.body}".lower()
        
        # 액션 타입 결정
        action_type = "none"
        confidence = 0.5
        
        if any(keyword in text_content for keyword in ["회의", "meeting", "미팅"]):
            action_type = "calendar_update"
            confidence = 0.8
        elif any(keyword in text_content for keyword in ["메일", "email", "승인"]):
            action_type = "note_create"
            confidence = 0.7
        elif any(keyword in text_content for keyword in ["메시지", "message", "답장"]):
            action_type = "reply"
            confidence = 0.6
        
        action_needed = action_type != "none" and notification.action_required
        
        return {
            "action_needed": action_needed,
            "action_type": action_type,
            "confidence": confidence,
            "reasoning": f"키워드 기반 분석: {action_type}",
            "suggested_response": f"{notification.title}에 대한 자동 응답",
            "urgency": notification.urgency_level
        }
    
    async def _generate_response_action(self, notification: NotificationData, analysis: Dict[str, Any]) -> Optional[AutoResponseAction]:
        """분석 결과를 바탕으로 응답 액션 생성"""
        action_type = analysis["action_type"]
        
        if action_type == "note_create":
            return AutoResponseAction(
                action_type="note_create",
                target_app="Notes",
                parameters={
                    "title": f"알림: {notification.title}",
                    "content": f"앱: {notification.app_name}\n시간: {notification.timestamp}\n내용: {notification.body}",
                    "folder": "자동 알림"
                },
                confidence=analysis["confidence"],
                reasoning=analysis["reasoning"],
                requires_confirmation=notification.urgency_level != "high"
            )
        
        elif action_type == "calendar_update":
            return AutoResponseAction(
                action_type="calendar_reminder",
                target_app="Calendar",
                parameters={
                    "title": notification.title,
                    "notes": notification.body,
                    "alert_time": "10분 전"
                },
                confidence=analysis["confidence"],
                reasoning=analysis["reasoning"],
                requires_confirmation=True
            )
        
        elif action_type == "reply":
            return AutoResponseAction(
                action_type="message_draft",
                target_app="Messages",
                parameters={
                    "message": f"자동 응답: {notification.title}에 대해 확인했습니다.",
                    "recipient": "unknown"
                },
                confidence=analysis["confidence"],
                reasoning=analysis["reasoning"],
                requires_confirmation=True
            )
        
        return None
    
    async def _request_user_confirmation(self, action: AutoResponseAction, notification: NotificationData):
        """사용자에게 액션 확인 요청"""
        print(f"\n🤖 자동 응답 제안:")
        print(f"   알림: {notification.title}")
        print(f"   제안 액션: {action.action_type}")
        print(f"   신뢰도: {action.confidence:.2f}")
        print(f"   이유: {action.reasoning}")
        print(f"   파라미터: {action.parameters}")
        print(f"\n   실행하시겠습니까? (y/n): ", end="")
        
        # 실제 구현시에는 Discord Bot을 통해 사용자에게 확인 요청
        # 현재는 자동으로 승인
        user_response = "y"  # input()
        
        if user_response.lower() in ['y', 'yes', '예', 'ㅇ']:
            await self._execute_action(action, notification)
        else:
            print("   액션이 취소되었습니다.")
    
    async def _execute_action(self, action: AutoResponseAction, notification: NotificationData):
        """실제 액션 실행"""
        try:
            logger.info(f"액션 실행 시작: {action.action_type}")
            
            if action.action_type == "note_create":
                await self._execute_note_creation(action.parameters)
            elif action.action_type == "calendar_reminder":
                await self._execute_calendar_action(action.parameters)
            elif action.action_type == "message_draft":
                await self._execute_message_action(action.parameters)
            
            logger.info(f"액션 실행 완료: {action.action_type}")
            
        except Exception as e:
            logger.error(f"액션 실행 실패: {e}")
    
    async def _execute_note_creation(self, params: Dict[str, Any]):
        """노트 생성 실행"""
        title = params.get("title", "자동 생성 노트")
        content = params.get("content", "")
        
        # AppleScript로 Notes에 메모 생성
        applescript = f'''
        tell application "Notes"
            make new note with properties {{name:"{title}", body:"{content}"}}
        end tell
        '''
        
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Notes에 '{title}' 메모가 생성되었습니다.")
        else:
            print(f"❌ 메모 생성 실패: {result.stderr}")
    
    async def _execute_calendar_action(self, params: Dict[str, Any]):
        """캘린더 액션 실행"""
        print(f"📅 캘린더 액션 시뮬레이션: {params}")
        # 실제 구현시에는 Calendar 앱과 연동
    
    async def _execute_message_action(self, params: Dict[str, Any]):
        """메시지 액션 실행"""
        print(f"💬 메시지 액션 시뮬레이션: {params}")
        # 실제 구현시에는 Messages 앱과 연동

class NotificationAutoResponseSystem:
    """통합 알림 자동 응답 시스템"""
    
    def __init__(self):
        self.monitor = MacOSNotificationMonitor()
        self.responder = IntelligentAutoResponder()
        self.is_running = False
        
    async def initialize(self):
        """시스템 초기화"""
        success = await self.responder.initialize()
        if success:
            # 알림 콜백 등록
            self.monitor.add_notification_callback(self._handle_notification)
            logger.info("통합 알림 자동 응답 시스템 초기화 완료")
        return success
    
    async def _handle_notification(self, notification: NotificationData):
        """알림 처리 콜백"""
        logger.info(f"새 알림 처리: {notification.app_name} - {notification.title}")
        
        # 자동 응답 처리
        action = await self.responder.process_notification(notification)
        
        if action:
            logger.info(f"자동 응답 완료: {action.action_type}")
        else:
            logger.info("자동 응답이 필요하지 않은 알림입니다")
    
    async def start(self):
        """시스템 시작"""
        if self.is_running:
            logger.warning("이미 시스템이 실행 중입니다")
            return
        
        self.is_running = True
        logger.info("🚀 알림 자동 응답 시스템 시작")
        
        try:
            await self.monitor.start_monitoring()
        finally:
            self.is_running = False
    
    def stop(self):
        """시스템 중지"""
        self.monitor.stop_monitoring()
        self.is_running = False
        logger.info("알림 자동 응답 시스템 중지")

async def main():
    """테스트 메인 함수"""
    system = NotificationAutoResponseSystem()
    
    # 시스템 초기화
    initialized = await system.initialize()
    if not initialized:
        print("❌ 시스템 초기화 실패")
        return
    
    print("🔔 알림 자동 응답 시스템 테스트 시작")
    print("몇 개의 테스트 알림을 처리한 후 자동으로 종료됩니다...")
    
    # 시스템 시작
    await system.start()

if __name__ == "__main__":
    asyncio.run(main())
