"""Discord Bot AI 메시지 핸들러 (에이전틱 AI 엔진 통합)

Discord Bot과 에이전틱 AI 엔진 간의 메시지 처리를 담당하는 모듈
개발 계획서 Phase 3.3: 진정한 AI 에이전트 구현

에이전틱 AI 원칙:
- 키워드 매칭 없이 순수 LLM 기반 자연어 이해
- 직접 매핑: 자연어 → 도구 선택을 중간 단계 없이 바로 처리
- 높은 신뢰도: 0.95+ 신뢰도로 정확한 의사결정 달성
- 자율적 임무 완수: 목표 달성까지 AI가 독립적으로 실행
"""

import asyncio
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from loguru import logger

# AI 엔진 관련 import
from ..ai_engine.llm_provider import GeminiProvider, ChatMessage
from ..ai_engine.decision_engine import AgenticDecisionEngine, ActionType, DecisionResult
from ..mcp.registry import ToolRegistry  
from ..config import Settings


@dataclass
class AIResponse:
    """AI 응답 데이터 클래스"""
    content: str
    confidence: float = 1.0
    reasoning: str = "AI processing"
    needs_followup: bool = False
    tool_calls_made: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tool_calls_made is None:
            self.tool_calls_made = []


class AIMessageHandler:
    """Discord 메시지를 에이전틱 AI로 처리하는 핸들러
    
    개발 계획서 원칙:
    - 에이전틱 AI 방식: 키워드 매칭 없이 순수 LLM 추론
    - 직접 매핑: 자연어 → 도구 선택 직접 처리
    - 자율적 임무 완수: 목표 달성까지 AI가 독립적으로 실행
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_provider: Optional[GeminiProvider] = None
        self.decision_engine: Optional[AgenticDecisionEngine] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self._initialize_ai_engine()
        
    def _initialize_ai_engine(self):
        """에이전틱 AI 엔진 초기화"""
        try:
            if self.settings.has_valid_ai_api_key():
                # LLM Provider 초기화
                self.llm_provider = GeminiProvider(self.settings)
                
                # Tool Registry 초기화
                self.tool_registry = ToolRegistry()
                self._register_available_tools()
                
                # 에이전틱 의사결정 엔진 초기화
                self.decision_engine = AgenticDecisionEngine(
                    self.llm_provider, 
                    self.tool_registry
                )
                
                # 비동기 초기화
                asyncio.create_task(self._async_initialize_gemini())
                logger.info("에이전틱 AI 엔진 초기화 완료")
            else:
                logger.warning("AI API 키가 설정되지 않음. Mock 모드로 동작")
                self.llm_provider = None
                self.decision_engine = None
        except Exception as e:
            logger.error(f"에이전틱 AI 엔진 초기화 실패: {e}")
            self.llm_provider = None
            self.decision_engine = None
    
    def _register_available_tools(self):
        """사용 가능한 MCP 도구들을 레지스트리에 등록"""
        try:
            # TODO: 실제 도구들을 등록
            # 현재는 예시 도구들만 등록
            example_tools = [
                {
                    "name": "notion_memo_tool",
                    "description": "Notion에 메모나 할일을 추가합니다",
                    "capabilities": ["메모 작성", "할일 추가", "노트 생성"],
                    "required_params": ["content"],
                    "optional_params": ["priority", "due_date"]
                },
                {
                    "name": "calculator_tool", 
                    "description": "수학 계산을 수행합니다",
                    "capabilities": ["사칙연산", "복잡한 계산"],
                    "required_params": ["expression"],
                    "optional_params": []
                },
                {
                    "name": "echo_tool",
                    "description": "입력된 텍스트를 그대로 반환합니다",
                    "capabilities": ["텍스트 반복", "메시지 확인"],
                    "required_params": ["text"],
                    "optional_params": []
                }
            ]
            
            # 임시로 도구 정보를 registry에 저장
            if not hasattr(self.tool_registry, '_available_tools'):
                self.tool_registry._available_tools = example_tools
                
            logger.info(f"도구 {len(example_tools)}개 등록 완료")
            
        except Exception as e:
            logger.error(f"도구 등록 실패: {e}")
    
    async def _async_initialize_gemini(self):
        """비동기 Gemini 초기화"""
        try:
            if self.llm_provider:
                success = await self.llm_provider.initialize()
                if success:
                    logger.info("Gemini Provider 비동기 초기화 성공")
                else:
                    logger.error("Gemini Provider 비동기 초기화 실패")
        except Exception as e:
            logger.error(f"Gemini Provider 비동기 초기화 중 오류: {e}")

    async def process_message(self, user_id: str, content: str, 
                            session_context: Optional[Dict[str, Any]] = None) -> AIResponse:
        """메시지를 에이전틱 AI로 처리
        
        Args:
            user_id: Discord 사용자 ID
            content: 메시지 내용
            session_context: 세션 컨텍스트
            
        Returns:
            AIResponse: AI 처리 결과
        """
        logger.info(f"사용자 {user_id}의 메시지 처리 시작: {content}")
        
        try:
            # 에이전틱 AI 엔진이 있는지 확인
            if not self.decision_engine:
                logger.warning("에이전틱 AI 엔진이 초기화되지 않음. 기본 응답 반환")
                return await self._fallback_response(content)
            
            # 에이전틱 의사결정 엔진으로 메시지 분석 및 처리
            decision_result = await self.decision_engine.process_user_request(
                user_message=content,
                user_id=user_id,
                session_context=session_context or {}
            )
            
            # 결과를 AIResponse로 변환
            response = self._decision_to_response(decision_result)
            
            logger.info(f"메시지 처리 완료 - 액션: {decision_result.action_type}, "
                       f"신뢰도: {decision_result.confidence}, "
                       f"도구 사용: {len(response.tool_calls_made)}")
            
            return response
            
        except Exception as e:
            logger.error(f"메시지 처리 중 오류 발생: {e}")
            return AIResponse(
                content=f"죄송합니다. 메시지 처리 중 오류가 발생했습니다: {str(e)}",
                confidence=0.0,
                reasoning=f"Error: {str(e)}"
            )
    
    def _decision_to_response(self, decision: DecisionResult) -> AIResponse:
        """DecisionResult를 AIResponse로 변환"""
        
        # 도구 실행 정보 수집
        tool_calls = []
        if decision.execution_plan and "tool_calls" in decision.execution_plan:
            tool_calls = [call.get("tool_name", "unknown") 
                         for call in decision.execution_plan["tool_calls"]]
        
        # 메타데이터 구성
        metadata = {
            "action_type": decision.action_type.value,
            "execution_plan": decision.execution_plan,
            "tool_execution_results": decision.tool_execution_results,
            "reasoning_chain": decision.reasoning_chain
        }
        
        return AIResponse(
            content=decision.response_message,
            confidence=decision.confidence,
            reasoning=decision.reasoning_chain[-1] if decision.reasoning_chain else "No reasoning",
            needs_followup=decision.action_type in [ActionType.MULTI_STEP_TASK, ActionType.CLARIFICATION_NEEDED],
            tool_calls_made=tool_calls,
            metadata=metadata
        )
    
    async def _fallback_response(self, content: str) -> AIResponse:
        """에이전틱 AI가 없을 때 기본 응답"""
        if self.llm_provider:
            try:
                # 기본 LLM 응답
                messages = [ChatMessage(role="user", content=content)]
                response = await self.llm_provider.generate_response(messages)
                
                return AIResponse(
                    content=response,
                    confidence=0.5,
                    reasoning="Fallback LLM response (에이전틱 AI 미사용)"
                )
            except Exception as e:
                logger.error(f"기본 LLM 응답 생성 실패: {e}")
        
        # 최종 fallback
        return AIResponse(
            content="안녕하세요! AI 시스템을 초기화하는 중입니다. 잠시 후 다시 시도해주세요.",
            confidence=0.1,
            reasoning="System initialization fallback"
        )
    
    def is_ready(self) -> bool:
        """AI 핸들러가 사용 준비됐는지 확인"""
        return (self.llm_provider is not None and 
                self.decision_engine is not None and 
                self.tool_registry is not None)
    
    def get_status(self) -> Dict[str, Any]:
        """AI 핸들러 상태 정보 반환"""
        return {
            "llm_provider_ready": self.llm_provider is not None,
            "decision_engine_ready": self.decision_engine is not None,
            "tool_registry_ready": self.tool_registry is not None,
            "available_tools": len(getattr(self.tool_registry, '_available_tools', [])),
            "is_ready": self.is_ready()
        }
