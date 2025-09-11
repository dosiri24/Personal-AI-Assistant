"""
도구 구현체 모듈

이 모듈은 표준화된 도구 구현체들을 제공합니다.
모든 도구는 src.tools.base.BaseTool을 상속받습니다.
"""

from .simple_calculator import create_calculator_tool
from .simple_filesystem import create_filesystem_tool

# 도구 팩토리 함수들을 노출
__all__ = [
    "create_calculator_tool",
    "create_filesystem_tool",
]

# 사용 가능한 도구들의 메타데이터
AVAILABLE_TOOLS = {
    "calculator": {
        "factory": create_calculator_tool,
        "description": "기본적인 수학 연산을 수행하는 계산기",
        "category": "utility"
    },
    "filesystem": {
        "factory": create_filesystem_tool, 
        "description": "안전한 파일시스템 조작 도구",
        "category": "system"
    }
}


def get_available_tools():
    """사용 가능한 도구 목록 반환"""
    return AVAILABLE_TOOLS


def create_tool_by_name(name: str):
    """이름으로 도구 생성"""
    if name not in AVAILABLE_TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    
    factory = AVAILABLE_TOOLS[name]["factory"]
    return factory()