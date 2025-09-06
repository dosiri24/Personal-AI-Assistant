from .event_bus import get_event_bus, EventType
from .container import get_container, get_component_manager

async def initialize_step_9_1() -> bool:
    """Step 9.1 초기화"""
    print("Step 9.1 integration layer initialized")
    return True

async def shutdown_step_9_1() -> bool:
    """Step 9.1 종료"""
    print("Step 9.1 integration layer shutdown")
    return True

def get_step_9_1_status():
    """Step 9.1 상태 확인"""
    return {
        "integration_layer_initialized": True,
        "event_bus_stats": get_event_bus().get_stats(),
        "registered_services_count": len(get_container().get_registered_services()),
        "components_initialized": 0
    }

def get_integration_manager():
    """통합 관리자 Mock"""
    class MockManager:
        def __init__(self):
            self.event_bus = get_event_bus()
            
    return MockManager()
