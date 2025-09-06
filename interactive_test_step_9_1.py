#!/usr/bin/env python3
"""
Step 9.1 대화형 테스트 및 데모

이 스크립트를 사용하여 Step 9.1의 각 구성 요소를 개별적으로 테스트하고
실제 동작을 확인할 수 있습니다.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.integration import (
    initialize_step_9_1,
    shutdown_step_9_1,
    get_step_9_1_status,
    get_integration_manager
)
from src.integration.event_bus import get_event_bus, EventType
from src.integration.container import get_container, ServiceScope
from src.integration.interfaces import BaseComponent, ComponentStatus, HealthStatus

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class DemoComponent(BaseComponent):
    """데모용 컴포넌트"""
    
    def __init__(self, name: str = "DemoComponent"):
        super().__init__(name)
        self.message_count = 0
        
    async def initialize(self) -> bool:
        print(f"🔧 {self.name} 초기화 중...")
        await asyncio.sleep(0.2)
        self.status = ComponentStatus.READY
        self.health = HealthStatus.HEALTHY
        print(f"✅ {self.name} 초기화 완료")
        return True
    
    async def start(self) -> bool:
        print(f"🚀 {self.name} 시작 중...")
        self.status = ComponentStatus.RUNNING
        return True
    
    async def stop(self) -> bool:
        print(f"🛑 {self.name} 중지 중...")
        self.status = ComponentStatus.STOPPED
        return True
    
    async def health_check(self):
        from src.integration.interfaces import HealthCheckResult
        return HealthCheckResult(
            status=self.health,
            message=f"{self.name} is running smoothly",
            details={"message_count": self.message_count},
            timestamp=datetime.now(),
            response_time_ms=1.5
        )
    
    def get_description(self) -> str:
        return f"Demo component for testing Step 9.1 integration"
    
    async def handle_message(self, event):
        """메시지 처리"""
        self.message_count += 1
        print(f"📨 {self.name}이 메시지를 받았습니다: {event.data.get('message', 'No message')}")
        print(f"   총 처리된 메시지: {self.message_count}개")

async def demo_event_bus():
    """이벤트 버스 데모"""
    print("\n" + "="*50)
    print("🎯 이벤트 버스 데모")
    print("="*50)
    
    event_bus = get_event_bus()
    
    # 데모 컴포넌트 생성
    demo_comp = DemoComponent("EventBusDemo")
    await demo_comp.initialize()
    
    # 이벤트 구독
    event_bus.subscribe(EventType.DISCORD_MESSAGE_RECEIVED, demo_comp.handle_message, "EventBusDemo")
    event_bus.subscribe(EventType.AI_ANALYSIS_COMPLETED, demo_comp.handle_message, "EventBusDemo")
    
    print("📡 이벤트 구독 완료")
    print("   - DISCORD_MESSAGE_RECEIVED")
    print("   - AI_ANALYSIS_COMPLETED")
    
    # 이벤트 발행
    print("\n📤 이벤트 발행 중...")
    
    await event_bus.publish_event(
        EventType.DISCORD_MESSAGE_RECEIVED,
        "TestUser",
        {"message": "안녕하세요! 이것은 테스트 메시지입니다.", "user": "테스트유저"}
    )
    
    await event_bus.publish_event(
        EventType.AI_ANALYSIS_COMPLETED,
        "AIEngine",
        {"message": "AI 분석이 완료되었습니다.", "result": "positive", "confidence": 0.95}
    )
    
    # 이벤트 처리 대기
    await asyncio.sleep(1)
    
    # 통계 출력
    stats = event_bus.get_stats()
    print(f"\n📊 이벤트 버스 통계:")
    print(f"   발행된 이벤트: {stats['events_published']}개")
    print(f"   처리된 이벤트: {stats['events_processed']}개")
    print(f"   실패한 이벤트: {stats['events_failed']}개")
    print(f"   등록된 핸들러: {stats['handlers_registered']}개")

async def demo_container():
    """의존성 주입 컨테이너 데모"""
    print("\n" + "="*50)
    print("🏗️ 의존성 주입 컨테이너 데모")
    print("="*50)
    
    container = get_container()
    
    # 여러 서비스 등록
    container.register(BaseComponent, DemoComponent, ServiceScope.SINGLETON)
    
    # 팩토리 함수로 등록
    def create_special_component():
        comp = DemoComponent("SpecialComponent")
        print("🏭 팩토리에서 특별한 컴포넌트 생성됨")
        return comp
    
    container.register_factory(DemoComponent, create_special_component, ServiceScope.TRANSIENT)
    
    print("📝 서비스 등록 완료:")
    print("   - BaseComponent -> DemoComponent (Singleton)")
    print("   - DemoComponent -> Factory Function (Transient)")
    
    # 서비스 해결
    print("\n🔍 서비스 해결 테스트:")
    
    # Singleton 테스트
    comp1 = container.resolve(BaseComponent)
    comp2 = container.resolve(BaseComponent)
    print(f"   Singleton 테스트: {comp1 is comp2} (같은 인스턴스여야 함)")
    
    # Transient 테스트
    demo1 = container.resolve(DemoComponent)
    demo2 = container.resolve(DemoComponent)
    print(f"   Transient 테스트: {demo1 is demo2} (다른 인스턴스여야 함)")
    
    # 등록된 서비스 목록
    services = container.get_registered_services()
    print(f"\n📋 등록된 서비스: {len(services)}개")
    for service_type, registration in services.items():
        print(f"   - {service_type.__name__} ({registration.scope.value})")

async def demo_interfaces():
    """인터페이스 데모"""
    print("\n" + "="*50)
    print("🔌 표준 인터페이스 데모")
    print("="*50)
    
    # 여러 컴포넌트 생성
    components = [
        DemoComponent("Component-A"),
        DemoComponent("Component-B"),
        DemoComponent("Component-C")
    ]
    
    print("🎭 컴포넌트 생명주기 테스트:")
    
    for comp in components:
        print(f"\n--- {comp.name} ---")
        
        # 초기 상태
        print(f"   초기 상태: {comp.status.value}")
        
        # 초기화
        await comp.initialize()
        print(f"   초기화 후: {comp.status.value}")
        
        # 시작
        await comp.start()
        print(f"   시작 후: {comp.status.value}")
        
        # 헬스 체크
        health = await comp.health_check()
        print(f"   헬스 체크: {health.status.value} - {health.message}")
        
        # 정보 조회
        info = comp.get_info()
        print(f"   컴포넌트 정보: {info.name} v{info.version}")
        
        # 중지
        await comp.stop()
        print(f"   중지 후: {comp.status.value}")

async def demo_full_integration():
    """전체 통합 데모"""
    print("\n" + "="*50)
    print("🚀 전체 통합 데모")
    print("="*50)
    
    # Step 9.1 초기화
    print("🔄 Step 9.1 통합 레이어 초기화 중...")
    success = await initialize_step_9_1()
    print(f"   초기화 결과: {'✅ 성공' if success else '❌ 실패'}")
    
    if not success:
        return
    
    # 시스템 상태 확인
    status = get_step_9_1_status()
    print(f"\n📊 시스템 상태:")
    print(f"   통합 레이어 초기화: {status['integration_layer_initialized']}")
    print(f"   등록된 서비스: {status['registered_services_count']}개")
    print(f"   초기화된 컴포넌트: {status['components_initialized']}개")
    
    # 통합 관리자를 통한 이벤트 발행
    manager = get_integration_manager()
    print(f"\n📡 통합 관리자를 통한 이벤트 발행...")
    
    await manager.event_bus.publish_event(
        EventType.SYSTEM_HEALTH_CHECK,
        "DemoScript",
        {"timestamp": datetime.now().isoformat(), "test": "integration"}
    )
    
    await asyncio.sleep(0.5)
    
    # 최종 상태 확인
    final_status = get_step_9_1_status()
    print(f"\n📈 이벤트 발행 후 상태:")
    events_stats = final_status['event_bus_stats']
    print(f"   발행된 이벤트: {events_stats['events_published']}개")
    print(f"   처리된 이벤트: {events_stats['events_processed']}개")
    
    # Step 9.1 종료
    print(f"\n🔄 Step 9.1 통합 레이어 종료 중...")
    success = await shutdown_step_9_1()
    print(f"   종료 결과: {'✅ 성공' if success else '❌ 실패'}")

async def interactive_menu():
    """대화형 메뉴"""
    print("\n" + "="*60)
    print("🎮 Step 9.1 대화형 테스트 메뉴")
    print("="*60)
    print("1. 이벤트 버스 데모")
    print("2. 의존성 주입 컨테이너 데모")
    print("3. 표준 인터페이스 데모")
    print("4. 전체 통합 데모")
    print("5. 모든 데모 실행")
    print("0. 종료")
    print("="*60)
    
    while True:
        try:
            choice = input("\n선택하세요 (0-5): ").strip()
            
            if choice == "0":
                print("👋 테스트를 종료합니다.")
                break
            elif choice == "1":
                await demo_event_bus()
            elif choice == "2":
                await demo_container()
            elif choice == "3":
                await demo_interfaces()
            elif choice == "4":
                await demo_full_integration()
            elif choice == "5":
                await demo_event_bus()
                await demo_container()
                await demo_interfaces()
                await demo_full_integration()
                print("\n🎉 모든 데모 완료!")
            else:
                print("❌ 잘못된 선택입니다. 0-5 사이의 숫자를 입력하세요.")
                
        except KeyboardInterrupt:
            print("\n👋 사용자가 중단했습니다.")
            break
        except Exception as e:
            print(f"❌ 오류 발생: {e}")

async def main():
    """메인 함수"""
    print("🎯 Step 9.1 컴포넌트 통합 대화형 테스트")
    print("이 도구를 사용하여 구현된 기능들을 자세히 테스트할 수 있습니다.")
    
    # 자동 실행 모드 체크
    if len(sys.argv) > 1 and sys.argv[1] == "--auto":
        print("\n🤖 자동 실행 모드")
        await demo_event_bus()
        await demo_container()
        await demo_interfaces()
        await demo_full_integration()
        print("\n🎉 모든 자동 테스트 완료!")
    else:
        await interactive_menu()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 프로그램이 중단되었습니다.")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
