"""
자연어 기반 ReAct Engine 어댑터

기존 ReactEngine을 자연어 기반으로 사용할 수 있도록 하는 어댑터
"""

import asyncio
from typing import Optional, Dict, Any
from ..agent_state import AgentContext, AgentResult
from ..llm_provider import LLMProvider
from .natural_planning import NaturalPlanningExecutor
from ...utils.logger import get_logger

logger = get_logger(__name__)


class NaturalReactEngine:
    """
    자연어 기반 ReAct Engine
    
    기존의 구조화된 ReactEngine을 자연어 기반으로 래핑하여
    JSON 구조 없이 순수 LLM 추론으로 동작하도록 합니다.
    """
    
    def __init__(
        self, 
        llm_provider: LLMProvider, 
        tool_registry=None,  # 기존 인터페이스 호환성
        tool_executor=None, 
        prompt_manager=None,  # 기존 인터페이스 호환성
        max_iterations: int = 15,  # 기존 인터페이스 호환성
        **kwargs  # 추가 호환성
    ):
        self.llm_provider = llm_provider
        self.tool_executor = tool_executor
        self.tool_registry = tool_registry
        self.prompt_manager = prompt_manager
        self.max_iterations = max_iterations
        
        # 자연어 실행기 생성 (실제 작업 수행)
        self.natural_executor = NaturalPlanningExecutor(llm_provider, tool_executor)
        
    async def process_goal(
        self, 
        goal: str, 
        context: AgentContext,
        **kwargs
    ) -> AgentResult:
        """
        자연어 목표를 처리
        
        Args:
            goal: 자연어로 표현된 목표
            context: 실행 컨텍스트
            **kwargs: 추가 옵션
            
        Returns:
            AgentResult: 실행 결과
        """
        
        logger.info(f"자연어 기반 목표 처리 시작: {goal}")
        
        try:
            # 자연어 실행기를 통해 목표 달성
            result = await self.natural_executor.execute_goal(goal, context)
            
            logger.info(f"목표 처리 완료: 성공={result.success}")
            return result
            
        except Exception as e:
            logger.error(f"목표 처리 실패: {e}")
            
            # 실패 시 기본 결과 반환
            from ..agent_state import AgentScratchpad
            scratchpad = AgentScratchpad(goal=goal)
            scratchpad.add_thought(f"오류 발생: {str(e)}")
            scratchpad.finalize(f"목표 '{goal}' 처리 중 오류가 발생했습니다: {str(e)}", success=False)
            
            return AgentResult.failure_result(
                error=str(e),
                scratchpad=scratchpad,
                metadata={"error_type": type(e).__name__}
            )
    
    # 🔄 기존 ReactEngine 호환성 메서드들
    async def process_request(
        self, 
        user_input: str, 
        context: AgentContext,
        **kwargs
    ) -> AgentResult:
        """기존 ReactEngine.process_request 호환성 메서드"""
        return await self.process_goal(user_input, context, **kwargs)
    
    async def execute(
        self,
        goal: str,
        context: AgentContext,
        **kwargs
    ) -> AgentResult:
        """기존 ReactEngine.execute 호환성 메서드"""
        return await self.process_goal(goal, context, **kwargs)
    
    async def process_user_request(
        self, 
        user_input: str, 
        user_id: str = "default",
        session_id: str = "default_session",
        **kwargs
    ) -> Dict[str, Any]:
        """
        사용자 요청을 처리하고 응답 반환
        
        Args:
            user_input: 사용자 입력
            user_id: 사용자 ID
            session_id: 세션 ID
            **kwargs: 추가 옵션
            
        Returns:
            Dict: 처리 결과
        """
        
        try:
            # 컨텍스트 생성
            context = AgentContext(
                user_id=user_id,
                session_id=session_id,
                goal=user_input,
                max_iterations=kwargs.get('max_iterations', 15)
            )
            
            # 목표 처리
            result = await self.process_goal(user_input, context)
            
            # 응답 구성
            if result.success:
                response_text = result.final_answer if hasattr(result, 'final_answer') else str(result.scratchpad.final_result)
                return {
                    "success": True,
                    "text": response_text,
                    "metadata": getattr(result, 'metadata', {}),
                    "scratchpad": result.scratchpad.get_formatted_history()
                }
            else:
                error_text = result.metadata.get('partial_result', f"요청 '{user_input}' 처리에 실패했습니다.")
                return {
                    "success": False,
                    "text": error_text,
                    "error": getattr(result, 'error', '알 수 없는 오류'),
                    "metadata": getattr(result, 'metadata', {}),
                    "scratchpad": result.scratchpad.get_formatted_history()
                }
                
        except Exception as e:
            logger.error(f"사용자 요청 처리 실패: {e}")
            return {
                "success": False,
                "text": f"요청 처리 중 오류가 발생했습니다: {str(e)}",
                "error": str(e),
                "metadata": {"error_type": type(e).__name__}
            }


# 기존 ReactEngine과의 호환성을 위한 팩토리 함수
def create_natural_react_engine(llm_provider: LLMProvider, tool_executor) -> NaturalReactEngine:
    """자연어 기반 ReAct Engine 생성"""
    return NaturalReactEngine(llm_provider, tool_executor)


# 편의 함수들
async def process_natural_goal(
    goal: str,
    llm_provider: LLMProvider,
    tool_executor,
    user_id: str = "default",
    session_id: str = "default_session",
    max_iterations: int = 15
) -> AgentResult:
    """
    자연어 목표를 직접 처리하는 편의 함수
    
    Args:
        goal: 자연어 목표
        llm_provider: LLM 프로바이더
        tool_executor: 도구 실행기
        user_id: 사용자 ID
        session_id: 세션 ID
        max_iterations: 최대 반복 횟수
        
    Returns:
        AgentResult: 실행 결과
    """
    
    engine = NaturalReactEngine(llm_provider, tool_executor)
    
    context = AgentContext(
        user_id=user_id,
        session_id=session_id,
        goal=goal,
        max_iterations=max_iterations
    )
    
    return await engine.process_goal(goal, context)


__all__ = [
    'NaturalReactEngine',
    'create_natural_react_engine', 
    'process_natural_goal'
]
