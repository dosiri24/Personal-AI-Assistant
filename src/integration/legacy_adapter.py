"""
레거시 시스템 어댑터

기존 MCPIntegration 클래스와의 완전한 호환성을 보장하면서
내부적으로는 새로운 에이전틱 AI 시스템을 활용하는 어댑터입니다.
"""

import asyncio
from typing import Dict, List, Any, Optional

from .agentic_controller import AgenticController
from ..ai_engine.llm_provider import LLMProvider, GeminiProvider
from ..ai_engine.prompt_templates import PromptManager
from ..mcp.registry import ToolRegistry
from ..mcp.executor import ToolExecutor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LegacyMCPAdapter:
    """
    레거시 MCP 통합 어댑터
    
    기존 MCPIntegration 클래스의 인터페이스를 완전히 유지하면서
    내부적으로는 새로운 AgenticController를 사용합니다.
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        tool_executor: Optional[ToolExecutor] = None,
        prompt_manager: Optional[PromptManager] = None
    ):
        self._llm_provider: Optional[LLMProvider] = llm_provider
        self._tool_registry: Optional[ToolRegistry] = tool_registry
        self._tool_executor: Optional[ToolExecutor] = tool_executor
        self._prompt_manager: Optional[PromptManager] = prompt_manager
        
        # AgenticController는 도구 등록 후에 초기화
        self.agentic_controller = None
        
        # 호환성을 위한 설정
        self._config: Dict[str, Any] = {}
        
        logger.info("레거시 MCP 어댑터 초기화 완료")
    
    async def initialize(self):
        """
        MCP 시스템 초기화 (기존 인터페이스 유지)
        """
        logger.info("레거시 어댑터 초기화 중...")
        
        # 컴포넌트들이 없으면 생성
        if self.llm_provider is None:
            self.llm_provider = GeminiProvider()
        
        if self.tool_registry is None:
            self.tool_registry = ToolRegistry()
            
        if self.tool_executor is None:
            self.tool_executor = ToolExecutor(self.tool_registry)
            
        if self.prompt_manager is None:
            self.prompt_manager = PromptManager()
        
        # LLM Provider 초기화
        if not await self.llm_provider.initialize():
            raise RuntimeError("LLM Provider 초기화 실패")
        
        if not self.llm_provider.is_available():
            raise RuntimeError("LLM Provider를 사용할 수 없습니다")
        
        # 도구 자동 발견 및 등록 (기존 방식)
        await self._discover_and_register_tools()
        
        # 도구 등록 완료 후 AgenticController 초기화
        logger.info("AgenticController 초기화 중...")
        self.agentic_controller = AgenticController(
            llm_provider=self.llm_provider,
            tool_registry=self.tool_registry,
            tool_executor=self.tool_executor,
            prompt_manager=self.prompt_manager
        )
        
        logger.info(f"레거시 어댑터 초기화 완료. 등록된 도구 수: {len(self.tool_registry.list_tools())}")
        
        # 등록된 도구 목록 로깅
        tools = self.tool_registry.list_tools()
        logger.info(f"등록된 도구들: {tools}")
        
        # notion_todo 도구 특별 확인
        if 'notion_todo' in tools:
            metadata = self.tool_registry.get_tool_metadata('notion_todo')
            if metadata:
                logger.info(f"notion_todo 도구 확인됨: {metadata.description}")
            else:
                logger.warning("notion_todo 도구가 등록되었지만 메타데이터 없음")
        else:
            logger.error("❌ notion_todo 도구가 등록되지 않음!")
    
    async def _discover_and_register_tools(self):
        """도구 자동 발견 및 등록 (기존 방식 유지)"""
        # 1) 일반 도구 자동 발견
        package_path = "src.tools"
        discovered_count = await self._tool_registry.discover_tools(package_path) if self._tool_registry else 0
        logger.info(f"발견된 도구 수: {discovered_count} (패키지: {package_path})")

        # 1-1) 수동으로 Notion Todo 도구 등록 (자동 발견으로 등록되지 않은 경우만)
        current_tools = self._tool_registry.list_tools() if self._tool_registry else []
        if 'notion_todo' not in current_tools:
            try:
                from ..tools.notion.todo_tool import TodoTool
                todo_tool = TodoTool()
                logger.info(f"TodoTool 생성 완료: {todo_tool}")
                
                await todo_tool.initialize()
                logger.info(f"TodoTool 초기화 완료")
                
                ok = await self._tool_registry.register_tool_instance(todo_tool) if self._tool_registry else False
                logger.info(f"TodoTool 등록 시도 결과: {ok}")
                
                if ok:
                    logger.info("✅ Notion Todo 도구 수동 등록 완료")
                    discovered_count += 1
                else:
                    logger.warning("❌ Notion Todo 도구 수동 등록 실패")
            except Exception as e:
                logger.warning(f"⚠️ Notion Todo 도구 수동 등록 건너뜀: {e}")
                logger.exception("상세 오류 정보:")  # 스택 트레이스 추가
        else:
            logger.info("✅ Notion Todo 도구가 이미 등록되어 있음 (자동 발견)")
            discovered_count += 1

        # 2) Apple MCP 도구 수동 등록
        try:
            from ..mcp.apple.apple_tools import register_apple_tools
            from ..mcp.apple.apple_client import AppleAppsManager

            apple_manager = AppleAppsManager()
            apple_tools = register_apple_tools(apple_manager)

            registered = 0
            for tool in apple_tools:
                ok = await self._tool_registry.register_tool_instance(tool) if self._tool_registry else False
                if ok:
                    registered += 1

            if registered > 0:
                logger.info(f"Apple MCP 도구 등록: {registered}개")
            else:
                logger.warning("Apple MCP 도구 등록 0개 (권한/환경 확인 필요)")
        except Exception as e:
            logger.warning(f"Apple MCP 도구 등록 건너뜀: {e}")
    
    async def process_user_request(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        사용자 요청 처리 (기존 인터페이스 유지)
        
        기존 MCPIntegration의 process_user_request와 동일한 시그니처를 유지하면서
        내부적으로는 새로운 에이전틱 시스템을 사용합니다.
        
        Args:
            user_input: 사용자 입력
            user_id: 사용자 ID
            conversation_history: 대화 히스토리
            
        Returns:
            str: 처리 결과 텍스트
        """
        try:
            logger.info(f"레거시 인터페이스로 요청 처리: {user_input[:50]}...")
            
            # AgenticController 초기화 확인
            if self.agentic_controller is None:
                raise RuntimeError("AgenticController가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")
            
            # 새로운 에이전틱 컨트롤러를 통해 처리
            result = await self.agentic_controller.process_request(
                user_input=user_input,
                user_id=user_id,
                conversation_history=conversation_history
            )
            
            # 기존 인터페이스에 맞게 텍스트만 반환
            return result.get("text", "처리 완료")
            
        except Exception as e:
            logger.error(f"레거시 요청 처리 실패: {e}")
            return f"요청 처리 중 오류가 발생했습니다: {str(e)}"
    
    async def process_user_request_detailed(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        사용자 요청 처리 (상세 결과 반환, 기존 인터페이스 유지)
        
        Args:
            user_input: 사용자 입력
            user_id: 사용자 ID
            conversation_history: 대화 히스토리
            
        Returns:
            Dict[str, Any]: 상세 처리 결과
        """
        try:
            logger.info(f"레거시 상세 인터페이스로 요청 처리: {user_input[:50]}...")
            
            # AgenticController 초기화 확인
            if self.agentic_controller is None:
                raise RuntimeError("AgenticController가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")
            
            # 새로운 에이전틱 컨트롤러를 통해 처리
            result = await self.agentic_controller.process_request(
                user_input=user_input,
                user_id=user_id,
                conversation_history=conversation_history
            )
            
            # 기존 인터페이스에 맞게 형식 조정
            return {
                "text": result.get("text", "처리 완료"),
                "execution": result.get("execution", {}),
                # 메타데이터는 선택적으로 포함
                **({} if not result.get("metadata") else {"metadata": result["metadata"]})
            }
            
        except Exception as e:
            logger.error(f"레거시 상세 요청 처리 실패: {e}")
            return {
                "text": f"요청 처리 중 오류가 발생했습니다: {str(e)}",
                "execution": {
                    "status": "error",
                    "error": str(e)
                }
            }
    
    # 기존 MCPIntegration의 다른 메서드들을 위한 호환성 메서드들
    
    def get_available_tools(self) -> List[str]:
        """사용 가능한 도구 목록 반환 (기존 인터페이스)"""
        return list(self._tool_registry.list_tools()) if self._tool_registry else []
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """직접 도구 실행 (기존 인터페이스)"""
        try:
            result = await self._tool_executor.execute_tool(tool_name, parameters) if self._tool_executor else None
            
            if result and result.result.is_success:
                return {
                    "success": True,
                    "data": result.result.data,
                    "message": "도구 실행 성공"
                }
            elif result:
                return {
                    "success": False,
                    "error": result.result.error_message,
                    "message": "도구 실행 실패"
                }
            else:
                return {
                    "success": False,
                    "error": "Tool executor not available",
                    "message": "도구 실행기가 초기화되지 않음"
                }
                
        except Exception as e:
            logger.error(f"도구 실행 실패: {tool_name} - {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "도구 실행 중 예외 발생"
            }
    
    def get_tool_metadata(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """도구 메타데이터 조회 (기존 인터페이스)"""
        metadata = self._tool_registry.get_tool_metadata(tool_name) if self._tool_registry else None
        if metadata:
            return {
                "name": metadata.name,
                "description": metadata.description,
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "description": param.description,
                        "required": param.required
                    }
                    for param in metadata.parameters
                ]
            }
        return None
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인 (기존 인터페이스 확장)"""
        # AgenticController 초기화 확인
        if self.agentic_controller is None:
            return {
                "status": "error",
                "llm_available": False,
                "tools_count": 0,
                "agentic_enabled": False,
                "error": "AgenticController가 초기화되지 않았습니다"
            }
        
        # 에이전틱 컨트롤러의 상태 확인 사용
        agentic_health = await self.agentic_controller.health_check()
        
        # 기존 형식에 맞게 조정
        return {
            "status": agentic_health.get("status", "unknown"),
            "llm_available": agentic_health.get("components", {}).get("llm_provider") == "available",
            "tools_count": len(self.get_available_tools()),
            "agentic_enabled": True,
            "details": agentic_health
        }
    
    # 새로운 기능에 대한 접근 제공 (선택적)
    
    async def process_request_with_react(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        max_iterations: int = 10,
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        ReAct 엔진 강제 사용 (새로운 기능)
        
        기존 사용자가 새로운 에이전틱 기능을 명시적으로 사용하고 싶을 때 호출
        """
        # AgenticController 초기화 확인
        if self.agentic_controller is None:
            raise RuntimeError("AgenticController가 초기화되지 않았습니다. initialize()를 먼저 호출하세요.")
            
        return await self.agentic_controller.process_request(
            user_input=user_input,
            user_id=user_id,
            conversation_history=conversation_history,
            force_react=True,
            max_iterations=max_iterations,
            timeout_seconds=timeout_seconds
        )
    
    def get_agentic_stats(self) -> Dict[str, Any]:
        """에이전틱 시스템 통계 (새로운 기능)"""
        # AgenticController 초기화 확인
        if self.agentic_controller is None:
            return {
                "error": "AgenticController가 초기화되지 않았습니다",
                "requests_processed": 0,
                "react_steps": 0,
                "tools_used": 0
            }
            
        return self.agentic_controller.get_stats()
    
    def enable_legacy_mode(self, enabled: bool = True):
        """레거시 모드 강제 설정 (개발/테스트용)"""
        # 향후 구현 가능한 기능
        # 모든 요청을 레거시 방식으로만 처리하도록 설정
        pass
    
    # 기존 MCPIntegration과의 완전한 호환성을 위한 속성들
    
    @property
    def config(self) -> Dict[str, Any]:
        """설정 정보 (기존 호환성)"""
        return self._config
    
    @config.setter
    def config(self, value: Dict[str, Any]):
        """설정 정보 설정"""
        self._config = value
    
    @property
    def llm_provider(self) -> Optional[LLMProvider]:
        """LLM 프로바이더 (기존 호환성)"""
        return self._llm_provider
    
    @llm_provider.setter
    def llm_provider(self, value: LLMProvider):
        """LLM 프로바이더 설정"""
        self._llm_provider = value
    
    @property
    def tool_registry(self) -> Optional[ToolRegistry]:
        """도구 레지스트리 (기존 호환성)"""
        return self._tool_registry
    
    @tool_registry.setter
    def tool_registry(self, value: ToolRegistry):
        """도구 레지스트리 설정"""
        self._tool_registry = value
    
    @property
    def tool_executor(self) -> Optional[ToolExecutor]:
        """도구 실행기 (기존 호환성)"""
        return self._tool_executor
    
    @tool_executor.setter  
    def tool_executor(self, value: ToolExecutor):
        """도구 실행기 설정"""
        self._tool_executor = value
    
    @property
    def prompt_manager(self) -> Optional[PromptManager]:
        """프롬프트 관리자 (기존 호환성)"""
        return self._prompt_manager
    
    @prompt_manager.setter
    def prompt_manager(self, value: PromptManager):
        """프롬프트 관리자 설정"""
        self._prompt_manager = value
