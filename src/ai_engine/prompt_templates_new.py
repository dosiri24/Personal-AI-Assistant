"""프롬프트 템플릿 시스템 (모듈화 완료)

원본 844줄 파일이 다음과 같이 모듈화되었습니다:
- prompt_templates/base.py: 기본 클래스와 타입 정의 (PromptType, PromptTemplate, BasePromptManager)
- prompt_templates/command.py: 명령 분석 및 처리 (CommandPromptManager)
- prompt_templates/memory.py: 메모리 및 검색 기능 (MemoryPromptManager)
- prompt_templates/results.py: 결과 처리 및 오류 관리 (ResultsPromptManager) 
- prompt_templates/tools.py: 도구 및 전문 기능 (ToolsPromptManager)
- prompt_templates/__init__.py: 통합 관리자 (PromptTemplateManager)

기존 코드와의 호환성을 위해 모든 클래스와 함수를 재내보냅니다.
"""

import warnings
from typing import Dict, List, Optional, Any

# 새로운 모듈화 시스템에서 모든 필요한 항목 가져오기
from .prompt_templates import (
    # 기본 클래스와 타입
    PromptTemplate,
    PromptType,
    BasePromptManager,
    
    # 카테고리별 매니저
    CommandPromptManager,
    MemoryPromptManager,
    ResultsPromptManager,
    ToolsPromptManager,
    
    # 통합 매니저 및 편의 함수
    PromptTemplateManager,
    get_prompt_manager,
    render_prompt,
    list_available_templates
)

from loguru import logger

# 호환성을 위한 경고 메시지 (운영 환경에서는 제거 가능)
warnings.warn(
    "prompt_templates.py가 모듈화되었습니다. "
    "향후 직접적으로 'from .prompt_templates import PromptTemplateManager'를 사용하는 것을 권장합니다.",
    DeprecationWarning,
    stacklevel=2
)


# 기존 코드와의 호환성을 위한 별칭
PromptManager = PromptTemplateManager  # 기존 클래스명과 호환
ContextAwarePromptManager = PromptTemplateManager  # 기존 확장 클래스와 호환


class UserContext:
    """사용자 컨텍스트 정보 (호환성을 위해 유지)"""
    def __init__(self, user_id: str, preferences: Optional[Dict[str, Any]] = None):
        self.user_id = user_id
        self.preferences = preferences or {}
        self.conversation_history = []
        self.recent_tasks = []
        self.current_mood = None
        self.time_patterns = {}
        self.feedback_history = []


class TaskContext:
    """작업 컨텍스트 정보 (호환성을 위해 유지)"""
    def __init__(self, task_type: str, priority: str = "medium"):
        self.task_type = task_type
        self.priority = priority
        self.deadline = None
        self.related_tasks = []
        self.required_resources = []
        self.complexity_level = "medium"
        self.previous_attempts = []


# 전역 매니저 인스턴스 (기존 코드 호환성)
_global_prompt_manager = None


def get_global_prompt_manager():
    """전역 프롬프트 매니저 인스턴스 반환 (기존 코드 호환성)"""
    global _global_prompt_manager
    if _global_prompt_manager is None:
        _global_prompt_manager = PromptTemplateManager()
    return _global_prompt_manager


# 모든 공개 항목 내보내기
__all__ = [
    # 기본 클래스와 타입
    'PromptTemplate',
    'PromptType', 
    'BasePromptManager',
    
    # 카테고리별 매니저
    'CommandPromptManager',
    'MemoryPromptManager',
    'ResultsPromptManager', 
    'ToolsPromptManager',
    
    # 통합 매니저
    'PromptTemplateManager',
    'PromptManager',  # 호환성 별칭
    'ContextAwarePromptManager',  # 호환성 별칭
    
    # 편의 함수
    'get_prompt_manager',
    'get_global_prompt_manager',  # 호환성 함수
    'render_prompt',
    'list_available_templates',
    
    # 컨텍스트 클래스 (호환성)
    'UserContext',
    'TaskContext'
]
