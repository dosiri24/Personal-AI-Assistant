"""
자연어 처리 모듈화 시스템
원본 natural_language.py (662줄)을 기능별로 분리하여 관리성 향상

모듈 구조:
- types.py: 기본 타입 및 데이터 클래스
- command_processing.py: 명령 파싱 및 의도 분류
- task_planning.py: 작업 계획 생성 및 관리
- tool_integration.py: MCP 도구 시스템 연계
- personalization.py: 개인화 및 컨텍스트 관리
- learning.py: 학습 및 최적화
- core.py: 메인 통합 처리기

통합 관리자를 통해 모든 기능에 일관된 접근 제공
"""

import warnings
from typing import Dict, List, Optional, Any

# 핵심 타입 및 데이터 클래스
from .types import (
    IntentType,
    UrgencyLevel,
    ParsedCommand,
    TaskPlan,
    ExecutionResult,
    PersonalizationContext,
    FeedbackData,
    create_error_result,
    create_success_result,
    create_clarification_result
)

# 기능별 모듈들
from .command_processing import CommandProcessor
from .task_planning import TaskPlanner
from .tool_integration import ToolIntegrator
from .personalization import PersonalizationManager
from .learning import LearningOptimizer

# 메인 통합 처리기
from .core import NaturalLanguageProcessor, NLP

from loguru import logger

# 기존 코드와의 호환성을 위한 경고 메시지
warnings.warn(
    "natural_language.py가 모듈화되었습니다. "
    "향후 직접적으로 'from .natural_language import NaturalLanguageProcessor'를 사용하는 것을 권장합니다.",
    DeprecationWarning,
    stacklevel=2
)


# 편의를 위한 전역 인스턴스
_global_processor: Optional[NaturalLanguageProcessor] = None


def get_natural_language_processor(config=None) -> NaturalLanguageProcessor:
    """전역 자연어 처리기 인스턴스 반환"""
    global _global_processor
    if _global_processor is None:
        if config is None:
            from ...config import Settings
            config = Settings()
        _global_processor = NaturalLanguageProcessor(config)
    return _global_processor


async def process_command(
    user_command: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
    config=None
) -> ExecutionResult:
    """편의 함수: 사용자 명령 처리"""
    processor = get_natural_language_processor(config)
    if not processor.initialized:
        await processor.initialize()
    return await processor.process_user_command(user_command, user_id, context)


async def parse_user_intent(
    user_command: str,
    user_id: str,
    context: Optional[Dict[str, Any]] = None,
    config=None
) -> ParsedCommand:
    """편의 함수: 사용자 의도 파싱"""
    processor = get_natural_language_processor(config)
    if not processor.initialized:
        await processor.initialize()
    return await processor.parse_command(user_command, user_id, context)


def get_supported_intents() -> List[str]:
    """지원하는 의도 목록 반환"""
    return [intent.value for intent in IntentType]


def get_urgency_levels() -> List[str]:
    """지원하는 긴급도 레벨 반환"""
    return [level.value for level in UrgencyLevel]


class NaturalLanguageManager:
    """
    자연어 처리 시스템 통합 관리자
    모든 모듈화된 기능을 통합 관리하는 고수준 인터페이스
    """
    
    def __init__(self, config=None):
        """
        Args:
            config: 시스템 설정 객체
        """
        if config is None:
            from ...config import Settings
            config = Settings()
        
        self.processor = NaturalLanguageProcessor(config)
        self.initialized = False
    
    async def initialize(self) -> bool:
        """시스템 초기화"""
        try:
            success = await self.processor.initialize()
            self.initialized = success
            if success:
                logger.info("자연어 처리 시스템 초기화 완료")
            return success
        except Exception as e:
            logger.error(f"자연어 처리 시스템 초기화 실패: {e}")
            return False
    
    async def process_user_input(
        self,
        user_input: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """사용자 입력 처리 (메인 인터페이스)"""
        if not self.initialized:
            await self.initialize()
        
        return await self.processor.process_user_command(user_input, user_id, context)
    
    async def analyze_intent(
        self,
        user_input: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ParsedCommand:
        """의도 분석"""
        if not self.initialized:
            await self.initialize()
        
        return await self.processor.parse_command(user_input, user_id, context)
    
    async def create_execution_plan(
        self,
        parsed_command: ParsedCommand,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """실행 계획 생성"""
        if not self.initialized:
            await self.initialize()
        
        available_tools = await self.processor.tool_integrator.get_available_tools()
        return await self.processor.create_task_plan(parsed_command, available_tools, context)
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """사용자 프로필 조회"""
        return self.processor.get_user_preferences(user_id)
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> None:
        """사용자 프로필 업데이트"""
        self.processor.update_user_preferences(user_id, updates)
    
    async def submit_feedback(
        self,
        user_id: str,
        feedback_content: str,
        rating: Optional[float] = None,
        feedback_type: str = "general"
    ) -> Dict[str, Any]:
        """사용자 피드백 제출"""
        feedback_data = {
            "type": feedback_type,
            "content": feedback_content,
            "rating": rating
        }
        
        return await self.processor.analyze_user_feedback(user_id, feedback_data)
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """시스템 통계 조회"""
        return await self.processor.get_system_status()
    
    async def optimize_performance(self) -> Dict[str, Any]:
        """성능 최적화 실행"""
        return await self.processor.optimize_prompt_performance()
    
    async def shutdown(self) -> None:
        """시스템 종료"""
        await self.processor.shutdown()
        self.initialized = False


# 모든 공개 클래스와 함수 내보내기
__all__ = [
    # 핵심 타입
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
