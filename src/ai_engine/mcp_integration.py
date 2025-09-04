"""
MCP와 AI 엔진 통합 모듈

AI 의사결정 엔진이 MCP 도구들을 사용할 수 있도록 연결하는 통합 레이어입니다.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from ..utils.logger import get_logger
from ..mcp import get_registry, get_executor, ToolMetadata, ExecutionResult, ExecutionMode
from .decision_engine import AgenticDecisionEngine, Decision, DecisionContext, Tool
from .llm_provider import LLMProvider

logger = get_logger(__name__)


@dataclass
class IntegratedExecutionResult:
    """통합 실행 결과"""
    decision: Decision
    execution_results: List[ExecutionResult] = field(default_factory=list)
    overall_success: bool = False
    total_execution_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "decision": self.decision.to_dict(),
            "execution_results": [result.to_dict() for result in self.execution_results],
            "overall_success": self.overall_success,
            "total_execution_time": self.total_execution_time,
            "errors": self.errors,
            "warnings": self.warnings,
            "executed_at": datetime.now().isoformat()
        }


class MCPIntegratedAI:
    """
    MCP와 통합된 AI 엔진
    
    AI 의사결정 엔진과 MCP 도구 시스템을 통합하여
    자연어 명령을 받아 실제 도구 실행까지 완료합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.decision_engine = AgenticDecisionEngine(llm_provider)
        self.registry = get_registry()
        self.executor = get_executor()
        
        # MCP 도구를 AI 엔진의 도구 목록으로 동기화
        self._sync_tools()
    
    def _sync_tools(self) -> None:
        """MCP 레지스트리의 도구들을 AI 엔진과 동기화"""
        logger.info("MCP 도구와 AI 엔진 동기화 시작...")
        
        # 기존 도구 목록 클리어
        self.decision_engine.available_tools.clear()
        
        # MCP 레지스트리에서 도구 정보 가져오기
        tool_names = self.registry.list_tools(enabled_only=True)
        
        for tool_name in tool_names:
            metadata = self.registry.get_tool_metadata(tool_name)
            if metadata:
                # MCP 도구를 AI 엔진 도구 형식으로 변환
                ai_tool = Tool(
                    name=metadata.name,
                    description=metadata.description,
                    capabilities=self._extract_capabilities(metadata),
                    required_params=[p.name for p in metadata.parameters if p.required],
                    optional_params=[p.name for p in metadata.parameters if not p.required],
                    confidence_threshold=0.7,
                    execution_time_estimate=metadata.timeout
                )
                
                self.decision_engine.available_tools[tool_name] = ai_tool
                logger.debug(f"도구 동기화 완료: {tool_name}")
        
        logger.info(f"총 {len(self.decision_engine.available_tools)}개 도구 동기화 완료")
    
    def _extract_capabilities(self, metadata: ToolMetadata) -> List[str]:
        """메타데이터에서 기능 목록 추출"""
        capabilities = []
        
        # 설명에서 키워드 추출
        description_lower = metadata.description.lower()
        
        # 카테고리 기반 기능 추가
        category_capabilities = {
            "productivity": ["일정 관리", "할일 관리", "노트 작성"],
            "communication": ["이메일 발송", "메시지 전송", "알림"],
            "file_management": ["파일 생성", "파일 수정", "파일 삭제", "파일 검색"],
            "web_scraping": ["웹 검색", "정보 수집", "데이터 추출"],
            "automation": ["자동화", "스케줄링", "배치 처리"],
            "system": ["시스템 정보", "프로세스 관리", "모니터링"],
            "data_analysis": ["데이터 분석", "통계", "시각화"],
            "creative": ["텍스트 생성", "창작", "편집"]
        }
        
        if metadata.category.value in category_capabilities:
            capabilities.extend(category_capabilities[metadata.category.value])
        
        # 태그 추가
        capabilities.extend(metadata.tags)
        
        return list(set(capabilities))  # 중복 제거
    
    async def process_command(self, user_input: str, user_context: Optional[Dict[str, Any]] = None) -> IntegratedExecutionResult:
        """
        사용자 명령 처리 (의사결정 + 도구 실행)
        
        Args:
            user_input: 사용자의 자연어 명령
            user_context: 사용자 컨텍스트 정보
            
        Returns:
            통합 실행 결과
        """
        logger.info(f"명령 처리 시작: {user_input}")
        start_time = datetime.now()
        
        try:
            # 1. 도구 동기화 (최신 상태 보장)
            self._sync_tools()
            
            # 2. AI 의사결정
            context = DecisionContext(
                user_input=user_input,
                user_context=user_context or {},
                available_tools=list(self.decision_engine.available_tools.keys())
            )
            
            decision = await self.decision_engine.make_decision(context)
            logger.info(f"AI 의사결정 완료: {decision.selected_tool} (신뢰도: {decision.confidence})")
            
            # 3. 의사결정 검증
            if not decision.selected_tool:
                return IntegratedExecutionResult(
                    decision=decision,
                    errors=["AI가 적절한 도구를 선택하지 못했습니다"]
                )
            
            if decision.needs_user_input:
                return IntegratedExecutionResult(
                    decision=decision,
                    warnings=["사용자 추가 입력이 필요합니다"],
                    errors=[f"필요한 정보: {', '.join(decision.missing_info)}"]
                )
            
            # 4. 도구 실행
            execution_results = []
            overall_success = True
            
            # 단일 도구 실행
            if isinstance(decision.execution_plan, dict) and "tool" in decision.execution_plan:
                result = await self._execute_single_tool(
                    decision.execution_plan["tool"],
                    decision.execution_plan.get("parameters", {})
                )
                execution_results.append(result)
                
                if not result.result.is_success:
                    overall_success = False
            
            # 다중 도구 실행 (실행 계획이 리스트인 경우)
            elif isinstance(decision.execution_plan, list):
                for step in decision.execution_plan:
                    if isinstance(step, dict) and "tool" in step:
                        result = await self._execute_single_tool(
                            step["tool"],
                            step.get("parameters", {})
                        )
                        execution_results.append(result)
                        
                        if not result.result.is_success:
                            overall_success = False
                            # 실패 시 중단할지 결정 (추후 AI가 판단하도록 개선 가능)
                            break
            
            # 5. 결과 통합
            total_time = (datetime.now() - start_time).total_seconds()
            
            result = IntegratedExecutionResult(
                decision=decision,
                execution_results=execution_results,
                overall_success=overall_success,
                total_execution_time=total_time
            )
            
            # 에러 및 경고 수집
            for exec_result in execution_results:
                if exec_result.result.error_message:
                    result.errors.append(exec_result.result.error_message)
                
                result.warnings.extend(exec_result.warnings)
            
            logger.info(f"명령 처리 완료: {overall_success} ({total_time:.2f}초)")
            return result
        
        except Exception as e:
            logger.error(f"명령 처리 중 예외: {e}", exc_info=True)
            
            total_time = (datetime.now() - start_time).total_seconds()
            return IntegratedExecutionResult(
                decision=Decision(
                    selected_tool=None,
                    confidence=0.0,
                    reasoning="명령 처리 중 예외 발생",
                    execution_plan={},
                    needs_user_input=False
                ),
                overall_success=False,
                total_execution_time=total_time,
                errors=[f"시스템 오류: {str(e)}"]
            )
    
    async def _execute_single_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ExecutionResult:
        """단일 도구 실행"""
        logger.debug(f"도구 실행: {tool_name} with {parameters}")
        
        try:
            result = await self.executor.execute_tool(
                tool_name=tool_name,
                parameters=parameters,
                mode=ExecutionMode.ASYNC
            )
            
            logger.debug(f"도구 실행 완료: {tool_name} - {result.result.status.value}")
            return result
        
        except Exception as e:
            logger.error(f"도구 실행 중 예외: {tool_name} - {e}")
            
            # 더미 결과 생성
            from ..mcp.base_tool import ToolResult, ExecutionStatus
            from ..mcp.executor import ExecutionContext
            
            dummy_context = ExecutionContext(
                tool_name=tool_name,
                parameters=parameters,
                execution_id=f"error_{tool_name}_{int(datetime.now().timestamp())}"
            )
            
            dummy_result = ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"도구 실행 예외: {str(e)}"
            )
            
            return ExecutionResult(context=dummy_context, result=dummy_result)
    
    async def get_available_tools(self) -> Dict[str, Dict[str, Any]]:
        """사용 가능한 도구 목록 반환"""
        self._sync_tools()
        
        tools_info = {}
        for tool_name, tool in self.decision_engine.available_tools.items():
            metadata = self.registry.get_tool_metadata(tool_name)
            stats = self.registry.get_tool_stats(tool_name)
            
            tools_info[tool_name] = {
                "description": tool.description,
                "capabilities": tool.capabilities,
                "required_params": tool.required_params,
                "optional_params": tool.optional_params,
                "category": metadata.category.value if metadata else "unknown",
                "enabled": stats["enabled"] if stats else False,
                "usage_count": stats["usage_count"] if stats else 0
            }
        
        return tools_info
    
    async def reload_tools(self) -> int:
        """도구 재로드"""
        logger.info("도구 재로드 시작...")
        
        # 레지스트리에서 자동 발견
        try:
            discovered = await self.registry.discover_tools("src.tools")
            logger.info(f"자동 발견된 도구: {discovered}개")
        except Exception as e:
            logger.warning(f"도구 자동 발견 실패: {e}")
            discovered = 0
        
        # AI 엔진과 동기화
        self._sync_tools()
        
        return len(self.decision_engine.available_tools)
    
    async def test_integration(self) -> Dict[str, Any]:
        """통합 테스트"""
        logger.info("MCP-AI 통합 테스트 시작...")
        
        try:
            # 1. 도구 동기화 테스트
            self._sync_tools()
            tools_count = len(self.decision_engine.available_tools)
            
            # 2. 간단한 의사결정 테스트
            test_context = DecisionContext(
                user_input="안녕하세요, 테스트입니다",
                available_tools=list(self.decision_engine.available_tools.keys())
            )
            
            decision = await self.decision_engine.make_decision(test_context)
            
            # 3. 레지스트리 상태 확인
            registry_stats = self.registry.get_registry_stats()
            
            # 4. 실행 엔진 상태 확인
            executor_stats = self.executor.get_execution_stats()
            
            test_result = {
                "integration_status": "success",
                "tools_synchronized": tools_count,
                "decision_engine_working": decision is not None,
                "registry_stats": registry_stats,
                "executor_stats": executor_stats,
                "test_decision": {
                    "confidence": decision.confidence if decision else 0,
                    "reasoning_length": len(decision.reasoning) if decision else 0
                }
            }
            
            logger.info("MCP-AI 통합 테스트 완료")
            return test_result
        
        except Exception as e:
            logger.error(f"통합 테스트 실패: {e}", exc_info=True)
            return {
                "integration_status": "error",
                "error": str(e)
            }


# 전역 통합 AI 인스턴스
_global_integrated_ai: Optional[MCPIntegratedAI] = None


def get_integrated_ai(llm_provider: Optional[LLMProvider] = None) -> MCPIntegratedAI:
    """전역 통합 AI 인스턴스 반환"""
    global _global_integrated_ai
    
    if _global_integrated_ai is None:
        if llm_provider is None:
            from .llm_provider import GeminiProvider, MockLLMProvider, GENAI_AVAILABLE
            
            if GENAI_AVAILABLE:
                try:
                    llm_provider = GeminiProvider()
                except Exception as e:
                    logger.warning(f"GeminiProvider 초기화 실패, Mock 사용: {e}")
                    llm_provider = MockLLMProvider()
            else:
                llm_provider = MockLLMProvider()
        
        _global_integrated_ai = MCPIntegratedAI(llm_provider)
    
    return _global_integrated_ai
