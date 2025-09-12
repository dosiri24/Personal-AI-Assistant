"""
레거시 AI Handler 인터페이스 (호환성 유지)

리팩토링 후 bot/ai_handler.py로 이동했지만, 
기존 코드와의 호환성을 위해 이 인터페이스를 제공합니다.
"""

import warnings
from typing import Optional, Any

# 실제 구현은 새로운 위치에서 가져오기
try:
    from ..mcp.mcp_integration import MCPIntegration
    from ..integration.agentic_controller import AgenticController
except ImportError:
    # 모듈이 없는 경우 None으로 설정
    MCPIntegration = None
    AgenticController = None

# 전역 인스턴스 (레거시 호환성)
_ai_handler_instance: Optional[Any] = None


def get_ai_handler():
    """
    AI Handler 인스턴스를 반환 (레거시 호환성)
    
    리팩토링된 시스템에서는 AgenticController 또는 MCPIntegration을 사용합니다.
    """
    global _ai_handler_instance
    
    if _ai_handler_instance is None:
        warnings.warn(
            "레거시 ai_handler를 사용하고 있습니다. "
            "새로운 AgenticController 또는 MCPIntegration 사용을 권장합니다.",
            DeprecationWarning,
            stacklevel=2
        )
        
        # MCP Integration 시스템 사용 시도
        if MCPIntegration:
            try:
                from ..mcp.mcp_integration import get_unified_mcp_system
                _ai_handler_instance = get_unified_mcp_system()
            except Exception:
                pass
        
        # 아직 초기화되지 않은 경우 더미 핸들러 생성
        if _ai_handler_instance is None:
            _ai_handler_instance = LegacyAIHandler()
    
    return _ai_handler_instance


class AIResponse:
    """AI 응답 클래스 (Discord Bot 호환성)"""
    def __init__(self, content: str):
        self.content = content
    
    def __str__(self):
        return self.content


class LegacyAIHandler:
    """
    레거시 AI Handler 구현 (호환성 유지)
    
    기존 코드가 작동할 수 있도록 최소한의 인터페이스를 제공합니다.
    """
    
    def __init__(self):
        self.session_manager = None
        
    async def process_message(self, user_message: Optional[str] = None, content: Optional[str] = None, user_id: str = "default", **kwargs):
        """
        메시지 처리 - 자연어 기반 실행기 사용
        
        Args:
            user_message: 사용자 메시지 (새 인터페이스)
            content: 사용자 메시지 (구 인터페이스, 호환성)
            user_id: 사용자 ID
            **kwargs: 추가 파라미터 (channel_id, metadata 등)
            
        Returns:
            처리된 응답 메시지
        """
        # user_message와 content 중 하나는 반드시 있어야 함
        message_content = user_message or content
        if not message_content:
            return "오류: 메시지 내용이 없습니다."
        
        try:
            # 🌟 기존에 초기화된 MCP 시스템 사용
            from ..mcp.mcp_integration import get_unified_mcp_system
            mcp_system = get_unified_mcp_system()
            
            # MCP 시스템의 도구 실행기와 LLM 프로바이더 가져오기
            tool_executor = mcp_system.tool_executor
            llm_provider = mcp_system.llm_provider
            
            # 🚀 자연어 기반 실행기 생성 (기존 도구들 활용)
            from ..ai_engine.react_engine.natural_planning import NaturalPlanningExecutor
            from ..ai_engine.agent_state import AgentContext
            
            natural_executor = NaturalPlanningExecutor(llm_provider, tool_executor)
            
            # 컨텍스트 생성
            context = AgentContext(
                user_id=user_id,
                session_id=kwargs.get('channel_id', 'discord_channel'),
                goal=message_content,
                max_iterations=15  # Discord 응답 시간 고려
            )
            
            # 🎯 자연어 기반 목표 실행
            result = await natural_executor.execute_goal(message_content, context)
            
            # 응답 구성 - 자연스럽고 친근한 답변만 전달
            if result.success:
                response_text = result.final_answer if hasattr(result, 'final_answer') else str(result.scratchpad.final_result)
            else:
                response_text = result.metadata.get('partial_result', '죄송해요, 작업을 완료하지 못했네요. 다시 시도해보시겠어요?')
            
            return AIResponse(response_text)
            
        except ImportError as e:
            # 자연어 시스템을 가져올 수 없는 경우 기존 시스템 시도
            try:
                from ..mcp.mcp_integration import get_unified_mcp_system
                mcp_system = get_unified_mcp_system()
                
                if hasattr(mcp_system, 'process_user_request'):
                    response = await mcp_system.process_user_request(
                        user_input=message_content,
                        user_id=user_id
                    )
                    if isinstance(response, dict):
                        result_text = response.get('text', str(response))
                    else:
                        result_text = str(response)
                    
                    return AIResponse(result_text)
                
            except Exception:
                pass
            
            return AIResponse(f"🤖 AI 시스템 로딩 중입니다.\n\n📝 **요청**: {message_content}\n\n⚠️ 잠시 후 다시 시도해주세요. (ImportError: {str(e)})")
            
        except Exception as e:
            # 오류 발생 시 상세 정보 제공
            error_msg = f"🤖 요청 처리 중 오류가 발생했습니다.\n\n📝 **요청**: {message_content}\n\n❌ **오류**: {str(e)}\n\n💡 시스템 관리자에게 문의하거나 잠시 후 다시 시도해주세요."
            return AIResponse(error_msg)


# 편의 함수들 (레거시 호환성)
def create_ai_handler():
    """AI Handler 인스턴스 생성"""
    return LegacyAIHandler()


def initialize_ai_handler():
    """AI Handler 초기화"""
    global _ai_handler_instance
    _ai_handler_instance = create_ai_handler()
    return _ai_handler_instance


# 모듈 초기화 시 핸들러 생성
initialize_ai_handler()


__all__ = [
    'get_ai_handler',
    'create_ai_handler', 
    'initialize_ai_handler',
    'LegacyAIHandler',
    'AIResponse'
]
