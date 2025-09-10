"""
ReAct 엔진 - 진정한 에이전틱 AI의 핵심

Reasoning and Acting (ReAct) 패러다임을 구현하여 에이전트가 목표 달성까지
지속적으로 사고-행동-관찰 루프를 반복하도록 합니다.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta

from .agent_state import (
    AgentScratchpad, AgentContext, AgentResult, ActionType, 
    StepStatus, ThoughtRecord, ActionRecord, ObservationRecord
)
from .llm_provider import LLMProvider, ChatMessage
from .prompt_templates import PromptManager
from .planning_engine import PlanningEngine, ExecutionPlan, TaskStatus as PlanTaskStatus
from .goal_manager import GoalManager, GoalHierarchy
from .dynamic_adapter import DynamicPlanAdapter, AdaptationEvent
from ..mcp.registry import ToolRegistry
from ..mcp.base_tool import ToolMetadata
from ..mcp.executor import ToolExecutor
from ..utils.logger import get_logger

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
            return await self._execute_plan_with_adaptation(context, start_time)
            
        except Exception as e:
            logger.error(f"고급 계획 실행 실패: {e}")
            # 기본 ReAct 루프로 폴백
            return await self.execute_goal(context)
    
    async def _execute_plan_with_adaptation(
        self, 
        context: AgentContext, 
        start_time: float
    ) -> AgentResult:
        """적응형 계획 실행"""
        
        scratchpad = AgentScratchpad(
            goal=context.goal,
            max_steps=context.max_iterations
        )
        
        plan = self.current_plan
        if not plan:
            raise ValueError("실행할 계획이 없습니다")
        
        for iteration in range(context.max_iterations):
            logger.debug(f"계획 실행 반복 {iteration + 1}/{context.max_iterations}")
            
            # 타임아웃 체크
            if time.time() - start_time > context.timeout_seconds:
                logger.warning("계획 실행 타임아웃")
                scratchpad.finalize("실행 시간이 초과되었습니다.", success=False)
                return AgentResult.failure_result(
                    "TIMEOUT_EXCEEDED",
                    scratchpad,
                    {"timeout_seconds": context.timeout_seconds}
                )
            
            # 다음 실행 가능한 단계 선택
            next_steps = plan.get_next_steps()
            if not next_steps:
                # 모든 단계 완료 확인
                if plan.is_completed():
                    final_result = await self._generate_final_answer(scratchpad, context)
                    scratchpad.finalize(final_result, success=True)
                    
                    logger.info(f"계획 실행 완료 (반복 {iteration + 1}회)")
                    return AgentResult.success_result(
                        final_result,
                        scratchpad,
                        {
                            "iterations": iteration + 1,
                            "execution_time": time.time() - start_time,
                            "plan_id": plan.plan_id
                        }
                    )
                else:
                    # 실행할 단계가 없지만 완료되지 않은 상태
                    logger.warning("실행 가능한 단계가 없음 - 계획 재검토 필요")
                    break
            
            # 첫 번째 단계 실행
            current_step = next_steps[0]
            current_step.status = PlanTaskStatus.IN_PROGRESS
            
            step_start_time = time.time()
            
            # 단계 실행
            execution_result = await self._execute_plan_step(
                current_step, scratchpad, context
            )
            
            execution_result["execution_time"] = time.time() - step_start_time
            execution_result["total_elapsed"] = time.time() - start_time
            
            # 적응 필요성 분석
            adaptation_event = await self.dynamic_adapter.analyze_situation(
                plan, current_step, execution_result, context
            )
            
            if adaptation_event:
                # 적응 전략 생성 및 적용
                adaptation_action = await self.dynamic_adapter.generate_adaptation_strategy(
                    adaptation_event, plan, self.current_hierarchy, context
                )
                
                plan = await self.dynamic_adapter.apply_adaptation(
                    adaptation_action, plan, self.current_hierarchy
                )
                
                self.current_plan = plan  # 업데이트된 계획 저장
                
                logger.info(f"계획 적응 완료: {adaptation_action.strategy.value}")
        
        # 최대 반복 도달
        logger.warning(f"최대 반복 횟수 도달: {context.max_iterations}")
        partial_result = await self._generate_partial_result(scratchpad, context)
        scratchpad.finalize(partial_result, success=False)
        
        return AgentResult.max_iterations_result(
            scratchpad,
            {
                "iterations": context.max_iterations,
                "execution_time": time.time() - start_time,
                "partial_result": partial_result,
                "plan_id": plan.plan_id if plan else None
            }
        )
    
    async def _execute_plan_step(
        self, 
        step: Any, 
        scratchpad: AgentScratchpad, 
        context: AgentContext
    ) -> Dict[str, Any]:
        """계획 단계 실행"""
        
        try:
            if step.action_type == "tool_call" and step.tool_name:
                # 도구 실행
                result = await self.tool_executor.execute_tool(
                    step.tool_name, 
                    step.tool_params or {}
                )
                
                if result.result.is_success:
                    step.status = PlanTaskStatus.COMPLETED
                    step.result = result.result
                    
                    # Scratchpad에 기록
                    action_record = ActionRecord(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=step.tool_name,
                        parameters=step.tool_params or {}
                    )
                    
                    observation_record = ObservationRecord(
                        content=str(step.result)
                    )
                    
                    step_record = scratchpad.start_new_step()
                    step_record.action = action_record
                    step_record.observation = observation_record
                    step_record.end_time = datetime.now()
                    
                    return {
                        "status": "success",
                        "result": step.result,
                        "expected_duration": step.estimated_duration
                    }
                else:
                    step.status = PlanTaskStatus.FAILED
                    step.error = result.result.error_message if result.result.error_message else "도구 실행 실패"
                    
                    return {
                        "status": "failed",
                        "error": step.error,
                        "expected_duration": step.estimated_duration
                    }
            
            elif step.action_type == "reasoning":
                # 추론 단계
                thought = ThoughtRecord(
                    content=f"추론 단계: {step.description}"
                )
                
                step_record = scratchpad.start_new_step()
                step_record.thought = thought
                step_record.end_time = datetime.now()
                
                step.status = PlanTaskStatus.COMPLETED
                step.result = "추론 완료"
                
                return {
                    "status": "success",
                    "result": "추론 완료",
                    "expected_duration": step.estimated_duration
                }
            
            else:
                step.status = PlanTaskStatus.SKIPPED
                return {
                    "status": "skipped",
                    "reason": f"지원하지 않는 액션 타입: {step.action_type}",
                    "expected_duration": step.estimated_duration
                }
                
        except Exception as e:
            step.status = PlanTaskStatus.FAILED
            step.error = str(e)
            
            return {
                "status": "failed",
                "error": str(e),
                "expected_duration": step.estimated_duration
            }
    
    def _get_available_tools_info(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구의 상세 메타데이터를 반환"""
        tools: List[Dict[str, Any]] = []
        for tool_name in self.tool_registry.list_tools():
            md: Optional[ToolMetadata] = self.tool_registry.get_tool_metadata(tool_name)
            if not md:
                continue
            params: List[Dict[str, Any]] = []
            for p in md.parameters:
                try:
                    params.append({
                        "name": p.name,
                        "type": getattr(p.type, "value", str(getattr(p.type, "name", "string")).lower()),
                        "description": p.description,
                        "required": p.required,
                        "choices": p.choices or [],
                        "default": p.default
                    })
                except Exception:
                    params.append({"name": getattr(p, "name", "param"), "required": getattr(p, "required", False)})
            tools.append({
                "name": md.name,
                "description": md.description,
                "parameters": params,
                "category": md.category.value,
                "tags": md.tags
            })
        return tools
    
    async def execute_goal(self, context: AgentContext) -> AgentResult:
        """
        목표 달성을 위한 ReAct 루프 실행
        
        Args:
            context: 에이전트 실행 컨텍스트
            
        Returns:
            AgentResult: 실행 결과 (성공/실패, 최종 답변, 실행 과정)
        """
        logger.info(f"ReAct 실행 시작: 목표='{context.goal[:100]}...', 최대반복={context.max_iterations}")
        
        # Scratchpad 초기화
        scratchpad = AgentScratchpad(
            goal=context.goal,
            max_steps=context.max_iterations
        )
        
        start_time = time.time()
        
        try:
            # 메인 ReAct 루프
            for iteration in range(context.max_iterations):
                logger.debug(f"ReAct 반복 {iteration + 1}/{context.max_iterations} 시작")
                
                # 타임아웃 체크
                if time.time() - start_time > context.timeout_seconds:
                    logger.warning(f"ReAct 실행 타임아웃: {context.timeout_seconds}초 초과")
                    scratchpad.finalize("실행 시간이 초과되었습니다.", success=False)
                    return AgentResult.failure_result(
                        "TIMEOUT_EXCEEDED",
                        scratchpad,
                        {"timeout_seconds": context.timeout_seconds}
                    )
                
                # 새 스텝 시작
                step = scratchpad.start_new_step()
                logger.debug(f"새 스텝 시작: 단계 {len(scratchpad.steps)}")
                
                # 1. Reasoning (사고)
                thought = await self._generate_thought(scratchpad, context)
                if not thought:
                    logger.error("사고 생성 실패")
                    break
                logger.debug(f"사고 생성 완료: {thought.content[:50]}...")
                
                # 2. Acting (행동)
                action = await self._decide_action(thought, scratchpad, context)
                if not action:
                    logger.error("행동 결정 실패")
                    break
                logger.debug(f"행동 결정: {action.action_type.value}")
                
                # 최종 답변인지 확인
                if action.action_type == ActionType.FINAL_ANSWER:
                    observation = await self._observe_final_answer(action, scratchpad)
                    final_result = observation.content
                    scratchpad.finalize(final_result, success=True)
                    
                    execution_time = time.time() - start_time
                    logger.info(f"ReAct 완료: 최종 답변 생성 (반복={iteration + 1}회, "
                               f"실행시간={execution_time:.2f}초)")
                    return AgentResult.success_result(
                        final_result,
                        scratchpad,
                        {
                            "iterations": iteration + 1,
                            "execution_time": execution_time
                        }
                    )
                
                # 3. Observation (관찰) - 도구 실행
                observation = await self._execute_and_observe(action, scratchpad, context)
                logger.debug(f"관찰 완료: {observation.content[:50]}...")
                
                # 진행 상황 주기적 로깅
                if (iteration + 1) % 3 == 0:
                    elapsed = time.time() - start_time
                    logger.info(f"진행 상황 ({iteration + 1}회): "
                               f"단계={len(scratchpad.steps)}, "
                               f"경과시간={elapsed:.1f}초")
                
                # 목표 달성 여부 확인
                if await self._is_goal_achieved(scratchpad, context):
                    final_result = await self._generate_final_answer(scratchpad, context)
                    scratchpad.finalize(final_result, success=True)
                    
                    execution_time = time.time() - start_time
                    logger.info(f"ReAct 완료: 목표 달성 (반복={iteration + 1}회, "
                               f"실행시간={execution_time:.2f}초)")
                    return AgentResult.success_result(
                        final_result,
                        scratchpad,
                        {
                            "iterations": iteration + 1,
                            "execution_time": execution_time
                        }
                    )
            
            # 최대 반복 도달
            execution_time = time.time() - start_time
            logger.warning(f"최대 반복 횟수 도달: {context.max_iterations}회, "
                          f"실행시간={execution_time:.2f}초")
            partial_result = await self._generate_partial_result(scratchpad, context)
            scratchpad.finalize(partial_result, success=False)
            
            return AgentResult.max_iterations_result(
                scratchpad,
                {
                    "iterations": context.max_iterations,
                    "execution_time": execution_time,
                    "partial_result": partial_result
                }
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"ReAct 실행 중 오류: {e}, 실행시간={execution_time:.2f}초")
            scratchpad.finalize(f"실행 중 오류가 발생했습니다: {str(e)}", success=False)
            return AgentResult.failure_result(
                str(e),
                scratchpad,
                {
                    "execution_time": execution_time,
                    "error_type": type(e).__name__
                }
            )
    
    async def _generate_thought(self, scratchpad: AgentScratchpad, context: AgentContext) -> Optional[ThoughtRecord]:
        """현재 상황을 분석하고 다음 행동에 대해 사고"""
        logger.debug(f"사고 과정 생성 시작: 현재단계={len(scratchpad.steps)}")
        
        try:
            # 시스템 프롬프트 생성
            system_prompt = self._create_thinking_system_prompt(context)
            
            # 현재 상황과 히스토리를 포함한 사용자 프롬프트
            user_prompt = self._create_thinking_user_prompt(scratchpad, context)
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            # LLM에게 사고 요청
            logger.debug("LLM에게 사고 분석 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.7,  # 창의적 사고를 위해 적당한 온도
                max_tokens=32768
            )
            
            thought_content = response.content.strip()
            
            # 사고 품질 평가 (간단한 휴리스틱)
            confidence = self._evaluate_thought_quality(thought_content)
            reasoning_depth = self._assess_reasoning_depth(thought_content)
            tags = self._extract_thought_tags(thought_content)
            
            thought = scratchpad.add_thought(
                content=thought_content,
                reasoning_depth=reasoning_depth,
                confidence=confidence,
                tags=tags
            )
            
            logger.debug(f"사고 생성 완료: 길이={len(thought_content)}자, "
                        f"신뢰도={confidence:.2f}, 깊이={reasoning_depth}")
            return thought
            
        except Exception as e:
            logger.error(f"사고 생성 실패: {e}")
            # 기본 사고로 폴백
            thought = scratchpad.add_thought(
                content=f"현재 상황을 분석하고 다음 단계를 계획해야 합니다. (오류: {str(e)})",
                reasoning_depth=1,
                confidence=0.3,
                tags=["fallback", "error"]
            )
            logger.warning("기본 사고로 폴백 처리됨")
            return thought
    
    async def _decide_action(self, thought: ThoughtRecord, scratchpad: AgentScratchpad, 
                           context: AgentContext) -> Optional[ActionRecord]:
        """사고를 바탕으로 구체적인 행동 결정"""
        logger.debug(f"행동 결정 시작: 사고신뢰도={thought.confidence:.2f}")
        
        try:
            # 사용 가능한 도구 정보 수집 (자세한 메타데이터 포함)
            tools_info = self._get_available_tools_info()
            
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
                max_tokens=32768,
                response_mime_type='application/json'
            )
            
            # JSON 파싱
            action_data = self._parse_action_response(response.content)

            # LLM의 최종 결정이 'final_answer'면 그대로 사용
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
                    parameters=action_data.get("parameters", {})
                )
                logger.info(f"도구 호출 행동 결정: '{tool_name}'")
            
            return action
            
        except Exception as e:
            logger.error(f"행동 결정 실패: {e}")
            # 안전한 종료를 위해 FINAL_ANSWER 액션으로 폴백
            action = scratchpad.add_action(
                ActionType.FINAL_ANSWER,
                tool_name="",
                parameters={"answer": f"행동 결정 오류로 인해 처리를 완료할 수 없습니다: {str(e)}"}
            )
            logger.warning("FINAL_ANSWER로 안전 폴백 처리됨")
            return action
    
    async def _execute_and_observe(self, action: ActionRecord, scratchpad: AgentScratchpad,
                                 context: AgentContext) -> ObservationRecord:
        """행동을 실행하고 결과를 관찰"""
        logger.debug(f"행동 실행 중: 도구='{action.tool_name}', 파라미터={list(action.parameters.keys()) if action.parameters else 'None'}")
        
        start_time = time.time()
        
        try:
            scratchpad.update_action_status(StepStatus.EXECUTING)
            
            # 도구 실행
            if action.tool_name:
                logger.debug(f"도구 '{action.tool_name}' 실행 시작")
                execution_result = await self.tool_executor.execute_tool(
                    tool_name=action.tool_name,
                    parameters=action.parameters
                )
            else:
                # tool_name이 None인 경우 처리
                logger.error("도구 이름이 지정되지 않음")
                scratchpad.update_action_status(
                    StepStatus.FAILED,
                    execution_time=0.0,
                    error_message="도구 이름이 지정되지 않았습니다."
                )
                observation = scratchpad.add_observation(
                    content="도구 이름이 지정되지 않아 실행할 수 없습니다.",
                    success=False,
                    analysis="행동 결정 과정에서 도구 이름이 누락됨"
                )
                return observation
            
            execution_time = time.time() - start_time
            
            if execution_result.result.is_success:
                scratchpad.update_action_status(
                    StepStatus.COMPLETED,
                    execution_time=execution_time
                )
                
                # 성공적인 관찰
                observation = scratchpad.add_observation(
                    content=f"도구 '{action.tool_name}' 실행 성공: {execution_result.result.data}",
                    success=True,
                    data=execution_result.result.data,
                    analysis=await self._analyze_execution_result(execution_result, context)
                )
                
                logger.info(f"도구 실행 성공: '{action.tool_name}' (실행시간={execution_time:.2f}초)")
                
            else:
                scratchpad.update_action_status(
                    StepStatus.FAILED,
                    execution_time=execution_time,
                    error_message=execution_result.result.error_message
                )
                
                # 실패 관찰 및 교훈 도출
                error_msg = execution_result.result.error_message or "알 수 없는 오류"
                lessons = await self._extract_lessons_from_failure(
                    action, error_msg, context
                )
                
                observation = scratchpad.add_observation(
                    content=f"도구 '{action.tool_name}' 실행 실패: {execution_result.result.error_message}",
                    success=False,
                    analysis=f"실패 원인 분석: {execution_result.result.error_message}",
                    lessons_learned=lessons
                )
                
                logger.warning(f"도구 실행 실패: '{action.tool_name}' - {execution_result.result.error_message} (실행시간={execution_time:.2f}초)")
            
            return observation
            
        except Exception as e:
            execution_time = time.time() - start_time
            scratchpad.update_action_status(
                StepStatus.FAILED,
                execution_time=execution_time,
                error_message=str(e)
            )
            
            observation = scratchpad.add_observation(
                content=f"도구 실행 중 예외 발생: {str(e)}",
                success=False,
                analysis=f"예외 분석: {type(e).__name__}",
                lessons_learned=[f"도구 '{action.tool_name}' 실행 시 {type(e).__name__} 예외 주의"]
            )
            
            logger.error(f"도구 실행 예외: '{action.tool_name}' - {e} (실행시간={execution_time:.2f}초)")
            return observation
    
    async def _observe_final_answer(self, action: ActionRecord, scratchpad: AgentScratchpad) -> ObservationRecord:
        """최종 답변 관찰"""
        final_answer = action.parameters.get("answer", "")
        
        observation = scratchpad.add_observation(
            content=f"최종 답변 생성: {final_answer}",
            success=True,
            analysis="목표 달성을 위한 최종 답변이 준비되었습니다."
        )
        
        return observation
    
    async def _is_goal_achieved(self, scratchpad: AgentScratchpad, context: AgentContext) -> bool:
        """목표 달성 여부를 LLM이 판단"""
        logger.debug(f"목표 달성 여부 확인: 현재단계={len(scratchpad.steps)}")
        
        try:
            # 목표 달성 판단 프롬프트
            system_prompt = """당신은 에이전트의 목표 달성 여부를 판단하는 전문가입니다.

주어진 목표와 지금까지의 실행 과정을 분석하여 목표가 달성되었는지 판단하세요.

판단 기준:
1. 목표가 명확히 완료되었는가?
2. 사용자가 요청한 모든 작업이 성공적으로 수행되었는가?
3. 추가로 수행해야 할 중요한 단계가 남아있지 않은가?

응답은 반드시 JSON 형식으로 하되, 다음 형태를 따르세요:
{
    "goal_achieved": true/false,
    "reason": "판단 이유 설명",
    "confidence": 0.0-1.0
}"""
            
            user_prompt = f"""목표: {context.goal}

현재까지의 실행 과정:
{scratchpad.get_formatted_history()}

목표가 달성되었는지 판단해주세요."""
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            logger.debug("LLM에게 목표 달성 여부 판단 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.2,
                max_tokens=32768,
                response_mime_type='application/json'
            )
            
            result = json.loads(response.content)
            achieved = result.get("goal_achieved", False)
            reason = result.get("reason", "")
            confidence = result.get("confidence", 0.5)
            
            logger.info(f"목표 달성 판단 결과: {achieved} (신뢰도={confidence:.2f}) - {reason[:50]}...")
            
            return achieved and confidence > 0.7
            
        except Exception as e:
            logger.error(f"목표 달성 판단 실패: {e}")
            # 폴백: Scratchpad의 휴리스틱 판단 사용
            fallback_result = scratchpad.is_goal_achieved
            logger.warning(f"휴리스틱 판단으로 폴백: {fallback_result}")
            return fallback_result
    
    async def _generate_final_answer(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """최종 답변 생성"""
        logger.debug(f"최종 답변 생성 시작: 단계={len(scratchpad.steps)}")
        
        try:
            system_prompt = """당신은 에이전트의 실행 결과를 종합하여 사용자에게 최종 답변을 제공하는 전문가입니다.

지금까지의 실행 과정을 분석하여 사용자의 목표가 어떻게 달성되었는지 명확하고 유용한 답변을 생성하세요.

답변 요구사항:
1. 수행된 주요 작업들을 요약
2. 달성된 결과를 구체적으로 설명
3. 사용자가 알아야 할 중요한 정보나 후속 조치 제안
4. 친근하고 도움이 되는 어조 유지

응답은 일반 텍스트로 하되, 마크다운 형식을 활용해도 좋습니다."""
            
            user_prompt = f"""목표: {context.goal}

실행 과정:
{scratchpad.get_formatted_history()}

위 과정을 종합하여 사용자에게 최종 답변을 제공해주세요."""
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            logger.debug("LLM에게 최종 답변 생성 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.5,
                max_tokens=32768
            )
            
            final_answer = response.content.strip()
            logger.info(f"최종 답변 생성 완료: 길이={len(final_answer)}자")
            
            return final_answer
            
        except Exception as e:
            logger.error(f"최종 답변 생성 실패: {e}")
            # 기본 답변으로 폴백
            fallback_answer = f"목표 '{context.goal}'에 대한 작업을 수행했지만 최종 답변 생성 중 오류가 발생했습니다: {str(e)}"
            logger.warning("기본 답변으로 폴백 처리됨")
            return fallback_answer

    async def _generate_partial_result(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """부분 결과 생성 (최대 반복 도달 시)"""
        logger.debug(f"부분 결과 생성: 단계={len(scratchpad.steps)}")
        
        try:
            system_prompt = """에이전트가 최대 반복 횟수에 도달하여 목표를 완전히 달성하지 못했습니다.

지금까지의 진행 상황을 분석하여 사용자에게 부분 결과와 후속 조치를 안내하는 답변을 생성하세요.

포함할 내용:
1. 지금까지 성공적으로 완료된 작업들
2. 달성하지 못한 부분과 이유
3. 사용자가 직접 수행할 수 있는 후속 조치
4. 재시도를 위한 제안 사항

친근하고 도움이 되는 어조로 답변해주세요."""
            
            user_prompt = f"""목표: {context.goal}

실행 과정:
{scratchpad.get_formatted_history()}

부분 결과와 후속 조치를 포함한 답변을 생성해주세요."""
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            logger.debug("LLM에게 부분 결과 생성 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.5,
                max_tokens=32768
            )
            
            partial_result = response.content.strip()
            logger.info(f"부분 결과 생성 완료: 길이={len(partial_result)}자")
            
            return partial_result
            
        except Exception as e:
            logger.error(f"부분 결과 생성 실패: {e}")
            # 기본 부분 결과로 폴백
            fallback_result = f"목표 '{context.goal}' 달성을 위해 {len(scratchpad.steps)}개의 단계를 수행했지만 최대 반복 횟수에 도달했습니다. 추가 작업이 필요할 수 있습니다."
            logger.warning("기본 부분 결과로 폴백 처리됨")
            return fallback_result
    
    # 헬퍼 메서드들
    
    def _create_thinking_system_prompt(self, context: AgentContext) -> str:
        """사고 과정을 위한 시스템 프롬프트"""
        return f"""당신은 목표 달성을 위해 체계적으로 사고하는 에이전트입니다.

현재 목표: {context.goal}

사고 과정에서 고려해야 할 사항:
1. 현재 상황과 지금까지의 진행상황 분석
2. 목표 달성을 위해 다음에 수행해야 할 가장 중요한 단계 식별
3. 가능한 접근 방법들과 각각의 장단점 평가
4. 예상되는 결과와 잠재적 문제점 고려
5. 이전 실패 경험이 있다면 그로부터 얻은 교훈 반영

깊이 있고 논리적인 사고 과정을 자연어로 설명하세요.
구체적이고 실행 가능한 계획을 포함해야 합니다."""
    
    def _create_thinking_user_prompt(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """사고 과정을 위한 사용자 프롬프트"""
        if not scratchpad.steps:
            return f"목표 '{context.goal}'를 달성하기 위한 첫 번째 단계를 계획해주세요. 현재 상황을 분석하고 어떤 접근 방식이 가장 효과적일지 생각해보세요."
        
        return f"""현재까지의 진행 상황:
{scratchpad.get_latest_context()}

위 상황을 바탕으로 다음 단계를 계획해주세요. 
이전 단계의 결과를 어떻게 활용할 것인지, 아직 해결되지 않은 문제는 무엇인지 분석하고,
목표 달성을 위한 최적의 다음 행동을 결정하세요."""
    
    def _create_action_system_prompt(self, context: AgentContext, tools_info: List[Dict]) -> str:
        """행동 결정을 위한 시스템 프롬프트(도구 메타데이터/별칭/예시 포함)"""
        # 도구 상세 설명 문자열 구성
        tool_lines: List[str] = []
        for t in tools_info:
            actions = []
            for p in t.get("parameters", []):
                if p.get("name") == "action" and p.get("choices"):
                    actions = p["choices"]
                    break
            params_str = ", ".join([
                f"{p.get('name')}" + ("*" if p.get("required") else "") + (f"(choices: {', '.join(p.get('choices', []))})" if p.get('choices') else "")
                for p in t.get("parameters", [])
            ])
            tool_lines.append(f"- {t['name']}: {t['description']} | params: {params_str}" + (f" | actions: {', '.join(actions)}" if actions else ""))

        tools_desc = "\n".join(tool_lines)

        # 한국어 별칭 매핑(도구 선택 가이드)
        alias_map = {
            "notion_todo": ["할일", "todo", "태스크", "작업", "체크리스트"],
            "notion_calendar": ["일정", "캘린더", "회의", "미팅", "약속", "스케줄"],
            "apple_notes": ["메모", "노트", "Apple Notes", "애플메모"],
            "calculator": ["계산", "더하기", "빼기", "곱하기", "나누기", "+", "-", "*", "/"],
            "filesystem": ["파일", "폴더", "이동", "복사", "삭제", "목록"]
        }
        alias_lines = [f"- {k}: {', '.join(v)}" for k, v in alias_map.items()]

        return f"""당신은 사용 가능한 MCP 도구들을 활용해 사용자의 목표를 실행하는 에이전트입니다.

목표: {context.goal}

사용 가능한 도구(메타데이터):
{tools_desc}

도구 선택 별칭(한국어 표현 → 도구명):
{chr(10).join(alias_lines)}

행동 결정 규칙(중요):
1) 사용자의 의도가 도구로 실행 가능한 경우, 'final_answer' 대신 반드시 'tool_call'을 선택합니다.
2) 파라미터는 메타데이터에 맞게 정확히 채웁니다. 날짜/시간은 ISO 형식(예: 2025-09-10T20:00:00+09:00)으로 변환하고, 시간대가 없으면 Asia/Seoul(+09:00)을 사용합니다.
3) 정보가 모호하더라도 합리적인 기본값(예: 오늘 23:59 등)을 채우고, 필요한 경우 보충 질문은 다음 턴에서 요청한다고 가정합니다.
4) 반드시 JSON 형식만 출력합니다.

응답 스키마 예시:
도구 사용:
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "create",
    "title": "GPS 개론 복습하기",
    "due_date": "2025-09-10T20:00:00+09:00",
    "priority": "중간"
  }},
  "reasoning": "사용자 요청이 '할일 추가'이므로 notion_todo로 생성"
}}

최종 답변(도구 불필요/완료 시에만):
{{
  "action_type": "final_answer",
  "answer": "직접 제공할 최종 답변",
  "reasoning": "도구 사용이 불필요하거나 목표 완료"
}}"""
    
    def _create_action_user_prompt(self, thought: ThoughtRecord, scratchpad: AgentScratchpad) -> str:
        """행동 결정을 위한 사용자 프롬프트"""
        return f"""방금 전 사고 내용:
{thought.content}

현재까지의 진행 상황:
{scratchpad.get_latest_context()}

이 사고를 바탕으로 다음에 수행할 구체적인 행동을 결정해주세요."""
    
    def _parse_action_response(self, response_content: str) -> Dict[str, Any]:
        """LLM 응답에서 행동 정보 파싱"""
        try:
            # JSON 블록 추출
            content = response_content.strip()
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"행동 응답 JSON 파싱 실패: {response_content}")
            # 폴백 금지: 상위에서 오류 처리하도록 예외 전파
            raise
    
    def _evaluate_thought_quality(self, thought_content: str) -> float:
        """사고 품질 평가 (간단한 휴리스틱)"""
        # 길이, 구체성, 키워드 포함 여부 등을 종합적으로 평가
        length_score = min(len(thought_content) / 200, 1.0)  # 200자 기준
        
        quality_keywords = ["분석", "계획", "고려", "예상", "방법", "단계", "이유", "결과"]
        keyword_score = sum(1 for keyword in quality_keywords if keyword in thought_content) / len(quality_keywords)
        
        # 질문이나 의도가 포함되어 있는지
        intent_score = 1.0 if any(word in thought_content for word in ["해야", "필요", "중요", "다음"]) else 0.5
        
        return (length_score * 0.3 + keyword_score * 0.5 + intent_score * 0.2)
    
    def _assess_reasoning_depth(self, thought_content: str) -> int:
        """추론 깊이 평가 (1-5 단계)"""
        depth_indicators = [
            ["왜냐하면", "이유는", "때문에"],  # 1차 추론
            ["따라서", "그러므로", "결과적으로"],  # 2차 추론
            ["만약", "가정하면", "경우"],  # 3차 추론 (가정)
            ["반면", "하지만", "그러나"],  # 4차 추론 (대안 고려)
            ["종합하면", "결론적으로", "최종적으로"]  # 5차 추론 (종합)
        ]
        
        depth = 1
        for level, indicators in enumerate(depth_indicators, 1):
            if any(indicator in thought_content for indicator in indicators):
                depth = level + 1
        
        return min(depth, 5)
    
    def _extract_thought_tags(self, thought_content: str) -> List[str]:
        """사고 내용에서 태그 추출"""
        tags = []
        
        tag_patterns = {
            "planning": ["계획", "단계", "순서"],
            "analysis": ["분석", "파악", "이해"],
            "problem_solving": ["문제", "해결", "방법"],
            "decision_making": ["결정", "선택", "판단"],
            "exploration": ["탐색", "조사", "확인"],
            "evaluation": ["평가", "검토", "고려"]
        }
        
        for tag, patterns in tag_patterns.items():
            if any(pattern in thought_content for pattern in patterns):
                tags.append(tag)
        
        return tags
    
    async def _analyze_execution_result(self, execution_result, context: AgentContext) -> str:
        """실행 결과 분석"""
        if execution_result.result.is_success:
            return f"성공적으로 실행되었습니다. 결과 데이터: {execution_result.result.data}"
        else:
            return f"실행 실패: {execution_result.result.error_message}"
    
    async def _extract_lessons_from_failure(self, action: ActionRecord, error_message: str, 
                                          context: AgentContext) -> List[str]:
        """실패로부터 교훈 추출"""
        lessons = []
        
        # 일반적인 실패 패턴 분석
        if "parameter" in error_message.lower():
            lessons.append(f"도구 '{action.tool_name}'의 파라미터 설정을 더 신중히 검토해야 함")
        
        if "permission" in error_message.lower() or "access" in error_message.lower():
            lessons.append("권한 관련 문제 - 사전 권한 확인 필요")
        
        if "timeout" in error_message.lower():
            lessons.append("실행 시간 초과 - 더 간단한 접근 방식 고려")
        
        if "not found" in error_message.lower():
            lessons.append("리소스를 찾을 수 없음 - 사전 존재 여부 확인 필요")
        
        return lessons
