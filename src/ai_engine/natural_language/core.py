"""
자연어 처리 시스템의 메인 코어 모듈
모든 하위 모듈을 통합하여 완전한 자연어 처리 파이프라인 제공
"""

from typing import Dict, List, Optional, Any
from loguru import logger

from .types import ParsedCommand, TaskPlan, ExecutionResult, FeedbackData
from .command_processing import CommandProcessor
from .task_planning import TaskPlanner
from .tool_integration import ToolIntegrator
from .personalization import PersonalizationManager
from .learning import LearningOptimizer

from ..llm_provider import LLMManager
from ..prompt_templates import PromptTemplateManager
from ..prompt_optimizer import PromptOptimizer
from ...config import Settings
from ...mcp.registry import ToolRegistry
from ...mcp.executor import ToolExecutor


class NaturalLanguageProcessor:
    """통합 자연어 처리기 - 모든 자연어 처리 기능의 중앙 허브"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.initialized = False
        
        # 핵심 컴포넌트들
        self.llm_manager = LLMManager(config)
        self.prompt_manager = PromptTemplateManager()
        self.prompt_optimizer = PromptOptimizer()
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor()
        
        # 모듈화된 기능 컴포넌트들
        self.command_processor = CommandProcessor(self.llm_manager, self.prompt_manager)
        self.task_planner = TaskPlanner(self.llm_manager, self.prompt_manager)
        self.tool_integrator = ToolIntegrator(self.llm_manager, self.tool_registry, self.tool_executor)
        self.personalization_manager = PersonalizationManager(self.llm_manager, self.prompt_manager, self.prompt_optimizer)
        self.learning_optimizer = LearningOptimizer(self.prompt_optimizer, self.llm_manager)
        
    async def initialize(self) -> bool:
        """자연어 처리기 초기화"""
        try:
            # LLM 프로바이더 초기화
            if not await self.llm_manager.initialize():
                logger.error("LLM 프로바이더 초기화 실패")
                return False
            
            # MCP 도구 레지스트리 초기화
            tool_count = await self.tool_registry.discover_tools("src.tools")
            logger.info(f"도구 레지스트리 초기화 완료: {tool_count}개 도구 등록")
                
            self.initialized = True
            logger.info("자연어 처리기 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"자연어 처리기 초기화 중 오류: {e}")
            return False
    
    async def process_user_command(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        사용자 명령의 완전한 처리 파이프라인
        
        1. 명령 파싱 및 의도 분류
        2. 작업 계획 생성
        3. 도구를 통한 실제 실행
        4. 개인화된 응답 생성
        """
        try:
            if not self.initialized:
                raise RuntimeError("자연어 처리기가 초기화되지 않았습니다")
            
            # 1단계: 명령 파싱
            parsed_command = await self.command_processor.parse_command(
                user_command, user_id, context
            )
            
            logger.info(f"명령 파싱 완료: {parsed_command.intent.value} (신뢰도: {parsed_command.confidence:.2f})")
            
            # 신뢰도가 낮거나 명확화가 필요한 경우
            if self.command_processor.should_request_clarification(parsed_command):
                return ExecutionResult(
                    status="clarification_needed",
                    message=f"요청을 더 명확히 해주실 수 있나요? (신뢰도: {parsed_command.confidence:.2f})",
                    clarifications=parsed_command.clarification_needed
                )
            
            # 2단계: 작업 계획 생성
            available_tools = await self.tool_integrator.get_available_tools()
            task_plan = await self.task_planner.create_task_plan(
                parsed_command, available_tools, context
            )
            
            logger.info(f"작업 계획 생성 완료: {task_plan.goal} ({len(task_plan.steps)}단계)")
            
            # 3단계: 작업 실행
            execution_result = await self.tool_integrator.execute_command(
                parsed_command, user_id, context
            )
            
            logger.info(f"작업 실행 완료: {execution_result.status}")
            
            return execution_result
            
        except Exception as e:
            logger.error(f"사용자 명령 처리 중 오류: {e}")
            return ExecutionResult(
                status="error",
                message=f"명령 처리 중 오류가 발생했습니다: {str(e)}"
            )
    
    async def parse_command(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ParsedCommand:
        """명령 파싱 (기존 호환성)"""
        return await self.command_processor.parse_command(user_command, user_id, context)
    
    async def create_task_plan(
        self,
        parsed_command: ParsedCommand,
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """작업 계획 생성 (기존 호환성)"""
        return await self.task_planner.create_task_plan(parsed_command, available_tools, context)
    
    async def execute_command(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """명령 실행 (기존 호환성 - 반환 타입 변경)"""
        result = await self.tool_integrator.execute_command(parsed_command, user_id, context)
        
        # 기존 dict 형식으로 변환
        return {
            "status": result.status,
            "message": result.message,
            "data": result.data,
            "clarifications": result.clarifications
        }
    
    async def generate_personalized_response(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """개인화된 응답 생성"""
        return await self.personalization_manager.generate_personalized_response(
            user_id, message, context
        )
    
    async def analyze_user_feedback(
        self,
        user_id: str,
        feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """사용자 피드백 분석"""
        # Dict를 FeedbackData로 변환
        feedback_data = FeedbackData(
            user_id=user_id,
            feedback_type=feedback.get("type", "general"),
            content=feedback.get("content", ""),
            context=feedback.get("context"),
            timestamp=feedback.get("timestamp"),
            rating=feedback.get("rating")
        )
        
        return await self.personalization_manager.analyze_user_feedback(user_id, feedback_data)
    
    async def create_context_aware_task_plan(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """컨텍스트 인식 작업 계획 생성"""
        return await self.task_planner.create_context_aware_task_plan(
            user_command, user_id, context
        )
    
    async def optimize_prompt_performance(self, test_duration_days: int = 7) -> Dict[str, Any]:
        """프롬프트 성능 최적화"""
        return await self.learning_optimizer.optimize_prompt_performance(test_duration_days)
    
    # 추가 편의 메서드들
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 조회"""
        return self.personalization_manager.get_user_preferences_summary(user_id)
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> None:
        """사용자 선호도 업데이트"""
        self.personalization_manager.update_user_context(user_id, preferences)
    
    async def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        try:
            available_tools = await self.tool_integrator.get_available_tools()
            
            return {
                "initialized": self.initialized,
                "llm_status": "active" if self.llm_manager else "inactive",
                "available_tools_count": len(available_tools),
                "available_tools": available_tools,
                "active_ab_tests": len(getattr(self.prompt_optimizer, 'active_tests', {})),
                "user_contexts_count": len(self.personalization_manager.user_contexts)
            }
        except Exception as e:
            logger.error(f"시스템 상태 조회 중 오류: {e}")
            return {"error": str(e)}
    
    async def create_learning_session(self, session_name: str) -> str:
        """학습 세션 생성"""
        return await self.learning_optimizer.start_learning_session(session_name)
    
    def record_interaction_metric(
        self,
        user_id: str,
        interaction_type: str,
        success: bool,
        response_time: float = None
    ) -> None:
        """상호작용 메트릭 기록"""
        try:
            # 간단한 메트릭 로깅
            metric_data = {
                "user_id": user_id,
                "type": interaction_type,
                "success": success,
                "response_time": response_time,
                "timestamp": "현재시간"  # 실제로는 datetime.now().isoformat()
            }
            
            logger.info(f"상호작용 메트릭 기록: {metric_data}")
            
        except Exception as e:
            logger.error(f"메트릭 기록 중 오류: {e}")
    
    async def shutdown(self) -> None:
        """자연어 처리기 종료"""
        try:
            logger.info("자연어 처리기 종료 시작")
            
            # 각 컴포넌트 정리
            if hasattr(self.llm_manager, 'shutdown'):
                await self.llm_manager.shutdown()
            
            if hasattr(self.tool_registry, 'shutdown'):
                await self.tool_registry.shutdown()
            
            self.initialized = False
            logger.info("자연어 처리기 종료 완료")
            
        except Exception as e:
            logger.error(f"자연어 처리기 종료 중 오류: {e}")


# 하위 호환성을 위한 별칭
NLP = NaturalLanguageProcessor
