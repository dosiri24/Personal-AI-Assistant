"""
MCP 시스템 통합 모듈

AI 엔진과 MCP 도구들을 통합하여 실제 작업을 수행할 수 있도록 하는 모듈입니다.
"""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..ai_engine.llm_provider import GeminiProvider, MockLLMProvider
from ..ai_engine.decision_engine import AgenticDecisionEngine, DecisionContext
from ..ai_engine.prompt_templates import PromptManager
from .registry import ToolRegistry
from .executor import ToolExecutor
from .protocol import MCPMessage, MCPRequest, MCPResponse
from ..config import get_settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MCPIntegration:
    """MCP 시스템과 AI 엔진을 통합하는 클래스"""
    
    def __init__(self):
        self.config = get_settings()
        
        # 우선 Mock LLM Provider 사용 (Gemini 초기화 문제 해결용)
        logger.info("Mock LLM Provider를 사용합니다.")
        self.llm_provider = MockLLMProvider()
        
        self.prompt_manager = PromptManager()
        self.decision_engine = AgenticDecisionEngine(
            llm_provider=self.llm_provider,
            prompt_manager=self.prompt_manager
        )
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        
    async def initialize(self):
        """MCP 시스템 초기화"""
        logger.info("MCP 시스템 초기화 중...")
        
        # LLM Provider 초기화
        await self.llm_provider.initialize()
        
        # 도구 자동 발견 및 등록
        await self._discover_and_register_tools()
        
        logger.info(f"MCP 시스템 초기화 완료. 등록된 도구 수: {len(self.tool_registry.list_tools())}")
    
    async def _discover_and_register_tools(self):
        """도구 자동 발견 및 등록"""
        # 예제 도구들 디렉토리 검색
        tools_dir = Path(__file__).parent / "example_tools"
        
        if tools_dir.exists():
            # 패키지 경로로 변환
            package_path = "src.mcp.example_tools"
            discovered_count = await self.tool_registry.discover_tools(package_path)
            logger.info(f"발견된 도구 수: {discovered_count}")
        else:
            logger.warning(f"도구 디렉토리가 없습니다: {tools_dir}")
    
    async def process_user_request(self, user_input: str, user_id: str = "default") -> str:
        """사용자 요청을 처리하여 MCP 도구들을 실행하고 결과를 반환"""
        try:
            logger.info(f"사용자 요청 처리 시작: {user_input}")
            
            # 1. AI 엔진으로 의사결정
            context = DecisionContext(
                user_message=user_input,
                user_id=user_id
            )
            decision = await self.decision_engine.make_decision(context)
            logger.info(f"AI 결정: {decision.selected_tools}, 신뢰도: {decision.confidence_score}")
            
            if decision.confidence_score < 0.7:
                return f"죄송합니다. 요청을 이해하지 못했습니다. (신뢰도: {decision.confidence_score:.2f})"
            
            if not decision.selected_tools:
                return "죄송합니다. 적절한 도구를 선택하지 못했습니다."
            
            # 첫 번째 선택된 도구 사용
            tool_name = decision.selected_tools[0]
            
            # 2. 선택된 도구가 등록되어 있는지 확인
            available_tools = self.tool_registry.list_tools()
            if tool_name not in available_tools:
                return f"죄송합니다. '{tool_name}' 도구를 찾을 수 없습니다."
            
            # 실행 계획에서 매개변수 추출
            parameters = {}
            if decision.execution_plan:
                parameters = decision.execution_plan[0].get("parameters", {})
            
            # 3. 도구 실행
            execution_result = await self.tool_executor.execute_tool(
                tool_name=tool_name,
                parameters=parameters
            )
            
            # 4. 결과 처리
            if execution_result.result.is_success:
                logger.info(f"도구 실행 성공: {tool_name}")
                return f"✅ 작업이 완료되었습니다!\n\n결과:\n{execution_result.result.data}"
            else:
                logger.error(f"도구 실행 실패: {execution_result.result.error_message}")
                return f"❌ 작업 중 오류가 발생했습니다: {execution_result.result.error_message}"
                
        except Exception as e:
            logger.error(f"요청 처리 중 오류: {e}")
            return f"❌ 시스템 오류가 발생했습니다: {str(e)}"
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록 반환"""
        tool_names = self.tool_registry.list_tools()
        tools = []
        
        for tool_name in tool_names:
            metadata = self.tool_registry.get_tool_metadata(tool_name)
            if metadata:
                tools.append({
                    "name": metadata.name,
                    "description": metadata.description,
                    "parameters": [param.to_dict() for param in metadata.parameters]
                })
        
        return tools
    
    async def test_tool_execution(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """특정 도구 테스트 실행"""
        try:
            execution_result = await self.tool_executor.execute_tool(tool_name, parameters)
            
            if execution_result.result.is_success:
                return f"✅ {tool_name} 실행 성공:\n{execution_result.result.data}"
            else:
                return f"❌ {tool_name} 실행 실패:\n{execution_result.result.error_message}"
                
        except Exception as e:
            return f"❌ 테스트 중 오류: {str(e)}"


async def run_integration_test():
    """MCP 통합 시스템 테스트"""
    print("🚀 MCP 통합 시스템 테스트 시작")
    
    # 1. 시스템 초기화
    integration = MCPIntegration()
    await integration.initialize()
    
    # 2. 사용 가능한 도구 확인
    tools = await integration.get_available_tools()
    print(f"\n📋 사용 가능한 도구 ({len(tools)}개):")
    for tool in tools:
        print(f"  - {tool['name']}: {tool['description']}")
    
    # 3. 직접 도구 테스트
    if tools:
        print(f"\n🔧 첫 번째 도구 테스트: {tools[0]['name']}")
        
        # 계산기 도구 테스트
        if tools[0]['name'] == 'calculator':
            test_result = await integration.test_tool_execution(
                'calculator', 
                {'expression': '2 + 3 * 4'}
            )
            print(f"결과: {test_result}")
    
    # 4. 자연어 요청 테스트
    print(f"\n💬 자연어 요청 테스트")
    test_requests = [
        "2 더하기 3은 얼마야?",
        "현재 시간 알려줘",
        "안녕하세요"  # 모호한 요청
    ]
    
    for request in test_requests:
        print(f"\n사용자: {request}")
        response = await integration.process_user_request(request)
        print(f"AI 비서: {response}")
    
    print("\n✅ MCP 통합 시스템 테스트 완료")


if __name__ == "__main__":
    asyncio.run(run_integration_test())
