"""
통합된 MCP 시스템

AI 에이전트와 도구 시스템을 연결하는 통합 인터페이스입니다.
중복된 MCP 통합 코드를 하나로 통합했습니다.
"""

import asyncio
import json
import os
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime

if TYPE_CHECKING:
    from ..integration.legacy_adapter import LegacyMCPAdapter

from .agent.llm_provider import GeminiProvider, MockLLMProvider, ChatMessage, LLMProviderError
from .agent.decision_engine import AgenticDecisionEngine, DecisionContext
from ..tools.registry import ToolRegistry
from ..tools.base_tool import ToolExecutor
from ..infrastructure.config.config import get_settings
from ..shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IntegratedExecutionResult:
    """통합 실행 결과"""
    decision: Optional[Any] = None
    execution_results: List[Any] = field(default_factory=list)
    overall_success: bool = False
    total_execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "decision": self.decision.to_dict() if self.decision else None,
            "execution_results": [result.to_dict() if hasattr(result, 'to_dict') else result for result in self.execution_results],
            "overall_success": self.overall_success,
            "total_execution_time": self.total_execution_time,
            "errors": self.errors,
            "warnings": self.warnings,
            "executed_at": datetime.now().isoformat()
        }


class UnifiedMCPSystem:
    """
    통합된 MCP 시스템
    
    AI 에이전트와 도구 시스템을 연결하는 단일 진입점입니다.
    기존의 중복된 MCP 통합 코드를 하나로 통합했습니다.
    """
    
    def __init__(self):
        self.config = get_settings()
        self.llm_provider = GeminiProvider()
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor()
        self.agentic_adapter = None
        self.agentic_enabled = True
        self._initialized = False
    
    async def initialize(self):
        """시스템 초기화"""
        if self._initialized:
            return
            
        logger.info("통합된 MCP 시스템 초기화 시작")
        
        # 도구 등록
        await self._register_tools()
        
        self._initialized = True
        logger.info("통합된 MCP 시스템 초기화 완료")
    
    async def _register_tools(self):
        """도구 등록"""
        # 기본 도구들 자동 검색
        package_path = "src.tools.implementations"
        discovered_count = await self.tool_registry.discover_tools(package_path)
        logger.info(f"발견된 도구 수: {discovered_count}")
        
        # 시스템 시간 도구 등록
        try:
            from ..tools.implementations.system_time_tool import create_system_time_tool
            system_time_tool = create_system_time_tool()
            await system_time_tool.initialize()
            await self.tool_registry.register_tool_instance(system_time_tool)
            logger.info("시스템 시간 도구 등록 완료")
        except Exception as e:
            logger.warning(f"시스템 시간 도구 등록 실패: {e}")
    
    async def process_user_request(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """사용자 요청 처리"""
        await self.initialize()
        
        if self.agentic_enabled:
            return await self._process_with_agentic_ai(
                user_input, user_id, conversation_history
            )
        else:
            return await self._process_legacy(
                user_input, user_id, conversation_history
            )
    
    async def _process_with_agentic_ai(
        self,
        user_input: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> str:
        """에이전틱 AI로 처리"""
        # 에이전틱 어댑터 초기화
        if self.agentic_adapter is None:
            from ..integration.legacy_adapter import LegacyMCPAdapter
            self.agentic_adapter = LegacyMCPAdapter()
        
        return await self.agentic_adapter.process_user_request(
            user_input=user_input,
            user_id=user_id,
            conversation_history=conversation_history
        )
    
    async def _process_legacy(
        self,
        user_input: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> str:
        """레거시 방식 처리"""
        # 기본 처리 로직
        return f"레거시 모드로 처리됨: {user_input}"
    
    async def get_available_tools(self) -> List[str]:
        """사용 가능한 도구 목록 반환"""
        await self.initialize()
        return list(self.tool_registry.get_all_tools().keys())
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> IntegratedExecutionResult:
        """도구 실행"""
        await self.initialize()
        
        result = IntegratedExecutionResult()
        start_time = datetime.now()
        
        try:
            execution_result = await self.tool_executor.execute_tool(
                tool_name, parameters
            )
            result.execution_results.append(execution_result)
            result.overall_success = execution_result.success if hasattr(execution_result, 'success') else True
        except Exception as e:
            result.errors.append(str(e))
            result.overall_success = False
        
        result.total_execution_time = (datetime.now() - start_time).total_seconds()
        return result


# 전역 인스턴스 (싱글톤 패턴)
_mcp_system = None

def get_unified_mcp_system() -> UnifiedMCPSystem:
    """통합된 MCP 시스템 인스턴스 반환"""
    global _mcp_system
    if _mcp_system is None:
        _mcp_system = UnifiedMCPSystem()
    return _mcp_system