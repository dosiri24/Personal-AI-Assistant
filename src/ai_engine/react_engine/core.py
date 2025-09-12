from __future__ import annotations

"""
ReactEngine 핵심 모듈

모든 하위 모듈들을 조합하여 완전한 ReAct 엔진 기능을 제공
"""

import asyncio
import time
import json
from typing import Optional, List, Dict, Any
from ..agent_state import AgentContext, AgentResult, AgentScratchpad
from ..llm_provider import LLMProvider
from ..prompt_templates import PromptManager
from ..planning_engine import PlanningEngine, ExecutionPlan
from ..goal_manager import GoalManager, GoalHierarchy
from ..dynamic_adapter import DynamicPlanAdapter
from typing import TYPE_CHECKING
from ...utils.logger import get_logger

if TYPE_CHECKING:
    # 타입 체크 전용 임포트로 순환 의존성 회피
    from ...mcp.registry import ToolRegistry
    from ...mcp.executor import ToolExecutor

from .thought import ThoughtGenerator
from .observation import ObservationManager
from .execution import ActionExecutor
from .planning import PlanningExecutor
from .adaptation import AdaptationManager

logger = get_logger(__name__)


class ReactEngine:
    """
    ReAct (Reasoning and Acting) 엔진
    
    진정한 에이전틱 AI의 핵심인 사고-행동-관찰 루프를 구현합니다.
    목표 달성까지 자율적으로 반복 수행하며, 중간 과정을 체계적으로 기록합니다.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        prompt_manager: PromptManager,
        max_iterations: int = 15,
        timeout_seconds: int = 600  # 10분으로 증가
    ):
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.prompt_manager = prompt_manager
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        
        # Phase 2: 고급 계획 수립 시스템 통합
        self.planning_engine = PlanningEngine(llm_provider)
        self.goal_manager = GoalManager(llm_provider)
        self.dynamic_adapter = DynamicPlanAdapter(llm_provider)
        
        # 모듈화된 컴포넌트들
        self.thought_generator = ThoughtGenerator(llm_provider)
        self.observation_manager = ObservationManager()
        self.action_executor = ActionExecutor(tool_registry, tool_executor)
        self.planning_executor = PlanningExecutor(tool_executor, self.dynamic_adapter, llm_provider)
        self.adaptation_manager = AdaptationManager(self.dynamic_adapter)
        
        # 현재 활성 계획 및 목표
        self.current_plan: Optional[ExecutionPlan] = None
        self.current_hierarchy: Optional[GoalHierarchy] = None
        
        logger.info(f"ReAct 엔진 초기화 완료 (최대 반복: {max_iterations}, 타임아웃: {timeout_seconds}초)")
    
    async def execute_goal_with_planning(self, context: AgentContext) -> AgentResult:
        """
        고급 계획 수립을 통한 목표 실행 (Phase 2)
        
        Args:
            context: 에이전트 실행 컨텍스트
            
        Returns:
            AgentResult: 실행 결과
        """
        logger.info(f"고급 계획 기반 실행 시작: {context.goal}")
        
        start_time = time.time()
        
        try:
            # 1. 목표 분해
            available_tools = self._get_available_tools_info()
            self.current_hierarchy = await self.goal_manager.decompose_goal(
                context.goal, context, available_tools
            )
            
            # 2. 실행 계획 생성
            self.current_plan = await self.planning_engine.create_execution_plan(
                context.goal, context, available_tools
            )
            
            # 3. 계획 기반 실행
            return await self.planning_executor.execute_plan_with_adaptation(
                self.current_plan, self.current_hierarchy, context, start_time
            )
            
        except Exception as e:
            logger.error(f"고급 계획 실행 실패: {e}")
            # 기본 ReAct 루프로 폴백
            return await self.execute_goal(context)
    
    async def execute_goal(self, context: AgentContext) -> AgentResult:
        """
        기본 ReAct 루프 실행
        
        Args:
            context: 에이전트 실행 컨텍스트
            
        Returns:
            AgentResult: 실행 결과
        """
        logger.info(f"ReAct 실행 시작: {context.goal}")
        
        start_time = time.time()
        scratchpad = AgentScratchpad(
            goal=context.goal,
            max_steps=context.max_iterations or self.max_iterations
        )
        
        timeout_seconds = context.timeout_seconds or self.timeout_seconds
        
        for iteration in range(context.max_iterations or self.max_iterations):
            logger.debug(f"ReAct 반복 {iteration + 1}/{context.max_iterations or self.max_iterations}")
            
            # 타임아웃 체크
            if time.time() - start_time > timeout_seconds:
                logger.warning("ReAct 실행 타임아웃")
                timeout_result = await self.observation_manager.handle_timeout(scratchpad, context)
                scratchpad.finalize(timeout_result, success=False)
                return AgentResult.failure_result("TIMEOUT_EXCEEDED", scratchpad, {"timeout_seconds": timeout_seconds})
            
            # 1. 사고 (Thought)
            thought = await self.thought_generator.generate_thought(scratchpad, context)
            if not thought:
                logger.error("사고 생성 실패")
                break
            
            # 2. 행동 결정 (Action Decision)
            action = await self._decide_action(thought, scratchpad, context)
            if not action:
                logger.error("행동 결정 실패")
                break
            
            # 3. 행동 실행 및 관찰 (Action & Observation)
            observation = await self.action_executor.execute_and_observe(action, scratchpad, context)
            
            # 4. 목표 달성 확인
            if await self._is_goal_achieved(scratchpad, context):
                final_result = await self._generate_final_answer(scratchpad, context)
                scratchpad.finalize(final_result, success=True)
                
                logger.info(f"목표 달성 완료 (반복 {iteration + 1}회)")
                return AgentResult.success_result(
                    final_result,
                    scratchpad,
                    {
                        "iterations": iteration + 1,
                        "execution_time": time.time() - start_time
                    }
                )
            
            # 5. 반복 행동 감지
            if self.observation_manager.detect_repetitive_actions(scratchpad):
                logger.warning("반복 행동 감지됨 - 실행 중단")
                break
        
        # 최대 반복 도달 또는 기타 종료
        partial_result = await self._generate_partial_result(scratchpad, context)
        scratchpad.finalize(partial_result, success=False)
        
        return AgentResult.max_iterations_result(
            scratchpad,
            {
                "iterations": context.max_iterations or self.max_iterations,
                "execution_time": time.time() - start_time,
                "partial_result": partial_result
            }
        )
    
    def _get_available_tools_info(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 정보 생성"""
        try:
            tools_info = []
            
            for tool_name, tool_meta in self.tool_registry.get_all_tools().items():
                if isinstance(tool_meta, type):
                    # 클래스인 경우 인스턴스 생성해서 메타데이터 가져오기
                    tool_instance = tool_meta()
                    if hasattr(tool_instance, 'metadata'):
                        tool_meta = tool_instance.metadata
                    else:
                        continue
                
                tools_info.append({
                    "name": tool_name,
                    "description": tool_meta.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "type": p.type.value,
                            "description": p.description,
                            "required": p.required,
                            "default": p.default,
                            "choices": getattr(p, 'choices', None)  # choices 정보 추가
                        }
                        for p in tool_meta.parameters
                    ]
                })
            
            return tools_info
            
        except Exception as e:
            logger.error(f"도구 정보 생성 실패: {e}")
            return []
    
    # 기존 메서드들은 하위 모듈로 위임하거나 간소화
    async def _decide_action(self, thought, scratchpad, context):
        """행동 결정 - 기존 로직 유지"""
        from ..agent_state import ActionRecord, ActionType
        from ..llm_provider import ChatMessage
        
        logger.debug(f"행동 결정 시작: 사고신뢰도={thought.confidence:.2f}")
        
        try:
            # 컨텍스트에 날짜가 있고 system_time 호출이 불필요한지 확인
            has_date_context = self._has_date_in_context(context, thought)
            
            # 사용 가능한 도구 정보 수집 (자세한 메타데이터 포함)
            tools_info = self._get_available_tools_info()
            
            # 날짜 컨텍스트가 있으면 system_time 도구 제외
            if has_date_context:
                tools_info = [tool for tool in tools_info if tool['name'] != 'system_time']
                logger.debug("컨텍스트에 날짜 정보가 있어 system_time 도구 제외")
            
            logger.debug(f"사용가능 도구: {len(tools_info)}개 ({[t['name'] for t in tools_info[:3]]}...)")
            
            # 행동 결정 프롬프트 생성
            system_prompt = self._create_action_system_prompt(context, tools_info)
            user_prompt = self._create_action_user_prompt(thought, scratchpad)
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            # LLM에게 행동 결정 요청
            logger.debug("LLM에게 행동 결정 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.3,  # 정확한 행동 결정을 위해 낮은 온도
                max_tokens=8192,  # 행동 결정 토큰 수 증가 (4096→8192)
                response_mime_type='application/json'
            )
            
            # JSON 파싱
            action_data = self._parse_action_response(response.content)

            # LLM이 'final_answer'를 선택한 경우 처리
            if action_data.get("action_type") == "final_answer":
                action = scratchpad.add_action(ActionType.FINAL_ANSWER)
                action.parameters = {"answer": action_data.get("answer", "")}
                logger.info("최종 답변 행동 결정됨")
                return action
            else:
                tool_name = action_data.get("tool_name")
                action = scratchpad.add_action(
                    ActionType.TOOL_CALL,
                    tool_name=tool_name,
                    parameters=action_data.get("parameters") or {}
                )
                logger.info(f"도구 호출 행동 결정: '{tool_name}'")
                return action
                
        except Exception as e:
            logger.error(f"행동 결정 실패: {e}")
            return None
    
    def _has_date_in_context(self, context, thought):
        """컨텍스트에 날짜 정보가 있는지 확인"""
        # 간단한 구현
        date_keywords = ["오늘", "내일", "어제", "2024", "2025", "월", "일"]
        text_to_check = f"{context.goal} {thought.content}"
        return any(keyword in text_to_check for keyword in date_keywords)
    
    def _parse_action_response(self, response_content):
        """행동 응답 파싱"""
        try:
            return json.loads(response_content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}")
            return {"action_type": "final_answer", "answer": "응답 파싱에 실패했습니다."}
    
    def _create_action_system_prompt(self, context, tools_info):
        """행동 시스템 프롬프트 생성"""
        tools_description = "\n".join([
            f"- {tool['name']}: {tool['description']}\n  파라미터: {self._format_parameters_description(tool['parameters'])}"
            for tool in tools_info
        ])
        
        return f"""당신은 목표 달성을 위해 도구를 사용하는 AI 에이전트입니다.

목표: {context.goal}

사용 가능한 도구:
{tools_description}

다음 중 하나를 선택하여 JSON으로 응답하세요:

1. 도구 호출:
{{"action_type": "tool_call", "tool_name": "도구명", "parameters": {{"param1": "value1"}}}}

2. 최종 답변:
{{"action_type": "final_answer", "answer": "최종 답변 내용"}}

⚠️ 중요: 각 파라미터의 허용값(choices)을 정확히 확인하고 사용하세요.

예시: notion_todo로 할일 목록 조회하려면:
{{"action_type": "tool_call", "tool_name": "notion_todo", "parameters": {{"action": "list"}}}}

목표 달성을 위해 가장 적절한 행동을 선택하세요."""
    
    def _format_parameters_description(self, parameters):
        """파라미터 설명을 포맷팅 (choices 정보 포함)"""
        descriptions = []
        for p in parameters:
            desc = f"{p['name']}({'필수' if p['required'] else '선택'}): {p['description']}"
            if p.get('choices'):
                desc += f" [가능한 값: {', '.join(p['choices'])}]"
            descriptions.append(desc)
        return ", ".join(descriptions)
    
    def _create_action_user_prompt(self, thought, scratchpad):
        """행동 사용자 프롬프트 생성"""
        return f"""현재 사고: {thought.content}

이전 진행 상황:
{self._format_scratchpad_history(scratchpad)}

위 사고를 바탕으로 다음 행동을 결정하세요."""
    
    def _format_scratchpad_history(self, scratchpad):
        """스크래치패드 히스토리 포맷"""
        if not scratchpad.steps:
            return "없음"
        
        history = []
        for i, step in enumerate(scratchpad.steps[-3:], 1):  # 최근 3개만
            if step.action:
                history.append(f"{i}. 행동: {step.action.action_type.value}")
            if step.observation:
                result = "성공" if step.observation.success else "실패"
                history.append(f"   결과: {result}")
        
        return "\n".join(history) if history else "없음"
    
    async def _is_goal_achieved(self, scratchpad, context):
        """목표 달성 확인 - 기존 로직 유지 (간소화)"""
        # 기존의 목표 달성 확인 로직
        if scratchpad.steps:
            last_step = scratchpad.steps[-1]
            if last_step.observation and last_step.observation.success:
                return True
        return False
    
    async def _generate_final_answer(self, scratchpad, context):
        """최종 답변 생성"""
        return await self.planning_executor._generate_final_answer(scratchpad, context)
    
    async def _generate_partial_result(self, scratchpad, context):
        """부분 결과 생성"""
        return await self.planning_executor._generate_partial_result(scratchpad, context)
