"""자연어 처리 시스템 (모듈화 완료)

원본 662줄 파일이 다음과 같이 모듈화되었습니다:
- natural_language/types.py: 기본 타입 및 데이터 클래스
- natural_language/command_processing.py: 명령 파싱 및 의도 분류  
- natural_language/task_planning.py: 작업 계획 생성 및 관리
- natural_language/tool_integration.py: MCP 도구 시스템 연계
- natural_language/personalization.py: 개인화 및 컨텍스트 관리
- natural_language/learning.py: 학습 및 최적화
- natural_language/core.py: 메인 통합 처리기
- natural_language/__init__.py: 통합 관리자

기존 코드와의 호환성을 위해 모든 클래스와 함수를 재내보냅니다.
"""

import warnings
from typing import Dict, List, Optional, Any

# 새로운 모듈화 시스템에서 모든 필요한 항목 가져오기
from .natural_language import (
    # 기본 타입
    IntentType,
    UrgencyLevel,
    ParsedCommand,
    TaskPlan,
    ExecutionResult,
    PersonalizationContext,
    FeedbackData,
    
    # 기능 모듈들
    CommandProcessor,
    TaskPlanner,
    ToolIntegrator,
    PersonalizationManager,
    LearningOptimizer,
    
    # 메인 처리기
    NaturalLanguageProcessor,
    NLP,
    NaturalLanguageManager,
    
    # 편의 함수들
    get_natural_language_processor,
    process_command,
    parse_user_intent,
    get_supported_intents,
    get_urgency_levels,
    
    # 유틸리티 함수들
    create_error_result,
    create_success_result,
    create_clarification_result
)

from loguru import logger

# 호환성을 위한 경고 메시지 (운영 환경에서는 제거 가능)
warnings.warn(
    "natural_language.py가 모듈화되었습니다. "
    "향후 직접적으로 'from .natural_language import NaturalLanguageProcessor'를 사용하는 것을 권장합니다.",
    DeprecationWarning,
    stacklevel=2
)

# 모든 공개 항목 내보내기
__all__ = [
    # 기본 타입
    'IntentType',
    'UrgencyLevel',
    'ParsedCommand', 
    'TaskPlan',
    'ExecutionResult',
    'PersonalizationContext',
    'FeedbackData',
    
    # 기능 모듈들
    'CommandProcessor',
    'TaskPlanner',
    'ToolIntegrator',
    'PersonalizationManager', 
    'LearningOptimizer',
    
    # 메인 처리기
    'NaturalLanguageProcessor',
    'NLP',  # 별칭
    'NaturalLanguageManager',
    
    # 편의 함수들
    'get_natural_language_processor',
    'process_command',
    'parse_user_intent', 
    'get_supported_intents',
    'get_urgency_levels',
    
    # 유틸리티 함수들
    'create_error_result',
    'create_success_result',
    'create_clarification_result'
]
