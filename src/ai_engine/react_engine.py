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
                # 매개변수 검증 및 보정
                validated_params = self._validate_and_fix_tool_params(step.tool_name, step.tool_params or {})
                
                if validated_params is None:
                    step.status = PlanTaskStatus.FAILED
                    error_msg = f"매개변수 검증 실패: {step.tool_name} 도구의 필수 매개변수가 누락되었습니다"
                    step.error = error_msg
                    logger.error(f"계획 단계 실행 실패: {error_msg}")
                    
                    return {
                        "status": "failed",
                        "error": error_msg,
                        "expected_duration": step.estimated_duration
                    }
                
                # 도구 실행
                result = await self.tool_executor.execute_tool(
                    step.tool_name, 
                    validated_params
                )
                
                if result.result.is_success:
                    step.status = PlanTaskStatus.COMPLETED
                    step.result = result.result
                    
                    # Scratchpad에 기록
                    action_record = ActionRecord(
                        action_type=ActionType.TOOL_CALL,
                        tool_name=step.tool_name,
                        parameters=validated_params
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
                    
                    # 타임아웃 시 부분 성공 여부 확인 후 적절한 응답 생성
                    timeout_response = await self._handle_timeout(scratchpad, context)
                    scratchpad.finalize(timeout_response, success=False)
                    
                    return AgentResult.failure_result(
                        "TIMEOUT_EXCEEDED",
                        scratchpad,
                        {"timeout_seconds": context.timeout_seconds, "response": timeout_response}
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
                temperature=0.4,  # 빠른 결정을 위해 온도 감소
                max_tokens=1024  # 사고 과정 토큰 수 대폭 감소 (4096->1024)
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
                max_tokens=4096,  # 행동 결정 토큰 수 축소
                response_mime_type='application/json'
            )
            
            # JSON 파싱
            action_data = self._parse_action_response(response.content)

            # LLM이 'final_answer'를 선택한 경우 1회 재시도(도구 강제)를 시도
            if action_data.get("action_type") == "final_answer":
                strict_system_prompt = (
                    system_prompt
                    + "\n\n[중요 정책] 이 턴에서는 final_answer 사용이 금지됩니다.\n"
                    + "반드시 tool_call을 출력하세요. 사용할 도구를 목록에서 선택하고, 필요한 파라미터를 메타데이터에 맞게 채우세요.\n"
                    + "모호한 경우에도 합리적 기본값을 사용하세요. JSON 이외 형식은 허용되지 않습니다."
                )
                strict_messages = [
                    ChatMessage(role="system", content=strict_system_prompt),
                    ChatMessage(role="user", content=user_prompt),
                ]
                try:
                    strict_response = await self.llm_provider.generate_response(
                        messages=strict_messages,
                        temperature=0.2,
                        max_tokens=4096,
                        response_mime_type='application/json'
                    )
                    strict_data = self._parse_action_response(strict_response.content)
                    if strict_data.get("action_type") == "tool_call":
                        tool_name = strict_data.get("tool_name")
                        action = scratchpad.add_action(
                            ActionType.TOOL_CALL,
                            tool_name=tool_name,
                            parameters=strict_data.get("parameters") or {}
                        )
                        logger.info(f"도구 호출 행동 결정(재시도): '{tool_name}'")
                        return action
                except Exception as re:
                    logger.warning(f"행동 결정 재시도 실패: {re}")

                # 재시도 후에도 여전히 final_answer면 그대로 존중
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
    
    async def _handle_timeout(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """타임아웃 시 적절한 응답 생성"""
        try:
            # 성공한 액션이 있는지 확인
            successful_actions = []
            for step in scratchpad.steps:
                if step.observation and step.observation.success and step.action:
                    if step.action.tool_name == 'notion_todo':
                        successful_actions.append("할일 생성/수정")
                    elif step.action.tool_name == 'apple_calendar':
                        successful_actions.append("일정 등록")
                    elif step.action.tool_name:
                        successful_actions.append(f"{step.action.tool_name} 실행")
            
            if successful_actions:
                actions_text = ", ".join(set(successful_actions))
                return f"시간이 초과되었지만 {actions_text}은 완료했어요! 😊"
            else:
                return "시간이 초과되어 작업을 완료하지 못했어요. 다시 시도해주세요."
                
        except Exception as e:
            logger.error(f"타임아웃 응답 생성 실패: {e}")
            return "시간이 초과되었어요. 다시 시도해주세요."
    
    def _detect_repetitive_actions(self, scratchpad: AgentScratchpad) -> bool:
        """반복 행동 감지"""
        if len(scratchpad.steps) < 3:
            return False
            
        # 최근 3개 단계의 액션 확인
        recent_actions = []
        for step in scratchpad.steps[-3:]:
            if step.action and step.action.tool_name:
                recent_actions.append(step.action.tool_name)
        
        # 같은 도구를 연속으로 3번 이상 사용했는지 확인
        if len(set(recent_actions)) == 1 and len(recent_actions) >= 3:
            # notion_todo 같은 도구를 계속 반복하는 경우
            if recent_actions[0] in ['notion_todo', 'apple_calendar']:
                # 성공적인 실행이 있었는지 확인
                for step in scratchpad.steps[-3:]:
                    if (step.observation and step.observation.success and 
                        step.action and step.action.tool_name == recent_actions[0]):
                        logger.warning(f"반복 행동 감지: {recent_actions[0]} 도구를 3회 연속 사용, 성공한 실행 있음")
                        return True
        
        return False
    
    async def _is_goal_achieved(self, scratchpad: AgentScratchpad, context: AgentContext) -> bool:
        """목표 달성 여부를 판단 (휴리스틱 + LLM)"""
        logger.debug(f"목표 달성 여부 확인: 현재단계={len(scratchpad.steps)}")
        
        # 1. 빠른 휴리스틱 판단
        if self._quick_goal_check(scratchpad, context):
            logger.info("휴리스틱으로 목표 달성 확인됨")
            return True
            
        # 2. 반복 행동 감지 및 조기 종료
        if self._detect_repetitive_actions(scratchpad):
            logger.warning("반복 행동 감지됨 - 목표 달성으로 간주")
            return True

        try:
            # 목표 달성 판단 프롬프트 (typo 보정 포함)
            system_prompt = """당신은 에이전트의 목표 달성 여부를 판단하는 전문가입니다.

주어진 목표와 지금까지의 실행 과정을 분석하여 목표가 달성되었는지 판단하세요.

판단 기준:
1. 목표가 명확히 완료되었는가?
2. 사용자가 요청한 모든 작업이 성공적으로 수행되었는가?
3. 추가로 수행해야 할 중요한 단계가 남아있지 않은가?

**중요**: 다음과 같은 typo나 오타는 관대하게 해석하세요:
- "odo" → "todo" (할일)
- "otino" → "notion"
- "clanedar" → "calendar"

사용자의 의도가 명확하고 해당 작업이 성공적으로 완료되었다면 달성으로 판단하세요.

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
        
        system_prompt = """당신은 매우 간결한 개인비서입니다. 작업 완료 후 사용자에게 초간단 보고를 하세요.

필수 규칙:
1. 최대 2줄 이내로만 답변
2. "완료했어요" + 핵심 결과 1가지만
3. � 친근한 어조로 마무리
4. ❌ 긴 설명, 단계별 설명, 세부사항 절대 금지
5. ❌ 마크다운 헤더(###) 사용 금지

좋은 예시:
"GPS 개론 복습하기를 오늘 8시까지 Notion에 추가했어요!"
"계산 완료: 123 + 456 = 579입니다!"

나쁜 예시:
"### 작업 완료 보고\n상세한 설명..."
"단계별로 설명드리면..."
"""
        
        user_prompt = f"""작업: {context.goal}

실행 결과:
{scratchpad.get_formatted_history()}

위 작업을 완료했습니다. 사용자에게 간결하고 친절한 결과 보고를 해주세요."""
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt)
        ]
        
        logger.debug("LLM에게 최종 답변 생성 요청 중...")
        response = await self.llm_provider.generate_response(
            messages=messages,
            temperature=0.3  # 더 일관된 간결한 응답을 위해 낮춤
            # max_tokens 제거 - 자동으로 적절한 길이 생성
        )
        
        final_answer = response.content.strip()
        logger.info(f"최종 답변 생성 완료: 길이={len(final_answer)}자")
        
        return final_answer

    async def _generate_partial_result(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """부분 결과 생성 (최대 반복 도달 시)"""
        logger.debug(f"부분 결과 생성: 단계={len(scratchpad.steps)}")
        
        system_prompt = """당신은 친절한 개인비서입니다. 작업이 완전히 끝나지 않았지만 지금까지의 진행 상황을 간결하게 보고하세요.

답변 요구사항:
1. 작업이 진행 중임을 알려주기
2. 완료된 부분이 있다면 간단히 언급
3. 간단한 다음 단계 제안 (1가지만)
4. 격려하는 어조로 마무리
5. 최대 2-3줄로 간결하게

피할 것: 기술적 용어, 긴 설명, 복잡한 지시사항"""
        
        user_prompt = f"""작업: {context.goal}

진행 상황:
{scratchpad.get_formatted_history()}

작업이 아직 완료되지 않았습니다. 사용자에게 간결한 중간 보고를 해주세요."""
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt)
        ]
        
        logger.debug("LLM에게 부분 결과 생성 요청 중...")
        response = await self.llm_provider.generate_response(
            messages=messages,
            temperature=0.3
            # max_tokens 제거 - 자동으로 적절한 길이 생성
        )
        
        partial_result = response.content.strip()
        logger.info(f"부분 결과 생성 완료: 길이={len(partial_result)}자")
        
        return partial_result
            

    
    # 헬퍼 메서드들
    
    def _create_thinking_system_prompt(self, context: AgentContext) -> str:
        """사고 과정을 위한 시스템 프롬프트"""
        return f"""당신은 목표 달성을 위해 체계적으로 사고하는 에이전트입니다.

현재 목표: {context.goal}

간결하고 핵심적인 사고 과정만 작성하세요:
1. 현재 상황 요약 (1-2문장)
2. 다음 필요한 행동 (1-2문장)
3. 선택 이유 (1-2문장)

불필요한 상세 분석이나 긴 설명은 피하고, 처리에 필요한 핵심 내용만 포함하세요.
형식을 갖출 필요 없이 실용적이고 간단명료하게 작성하세요."""
    
    def _create_thinking_user_prompt(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """사고 과정을 위한 사용자 프롬프트"""
        # 최근 대화 컨텍스트(있으면) 주입
        history_txt = ""
        try:
            conv = (context.constraints or {}).get("conversation_history") or []
            if isinstance(conv, list) and conv:
                # 최근 10개로 확장하고 더 자세히 표시
                tail = conv[-10:]
                lines = []
                for item in tail:
                    if isinstance(item, dict):
                        role = item.get("role") or "context"
                        content = (item.get("content") or "").strip()
                        if content:
                            # TODO 관련 내용은 특별히 강조
                            if any(keyword in content.lower() for keyword in ['todo', '할일', '투두', '작업', '기행문', 'notion']):
                                lines.append(f"- {role}: 📝 {content}")
                            else:
                                lines.append(f"- {role}: {content}")
                if lines:
                    history_txt = "최근 대화 컨텍스트 (참고용):\n" + "\n".join(lines) + "\n\n"
        except Exception:
            pass

        if not scratchpad.steps:
            return (
                history_txt
                + f"목표 '{context.goal}'를 달성하기 위한 첫 번째 단계를 간단히 계획하세요. (3-4문장 이내)\n"
                + "이전 대화에서 언급된 관련 정보가 있다면 참고하세요."
            )
        
        return (
            history_txt
            + f"""현재까지의 진행 상황:
{scratchpad.get_latest_context()}

위 상황을 바탕으로 다음 단계를 간단히 계획하세요. (3-4문장 이내)
이전 결과를 어떻게 활용할지, 다음에 무엇을 할지만 핵심적으로 작성하세요.
이전 대화 맥락도 고려하세요."""
        )
    
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
            
            # 파라미터 정보를 더 명확하게 표시
            param_details = []
            for p in t.get("parameters", []):
                param_name = p.get('name', '')
                required_mark = "*" if p.get("required") else ""
                choices = p.get('choices', [])
                
                if choices:
                    # choices가 있는 경우 더 명확하게 표시
                    choices_str = f" [선택값: {' | '.join(choices)}]"
                else:
                    choices_str = ""
                
                param_details.append(f"{param_name}{required_mark}{choices_str}")
            
            params_str = ", ".join(param_details)
            tool_lines.append(f"- {t['name']}: {t['description']} | 파라미터: {params_str}")

        tools_desc = "\n".join(tool_lines)

        # 실제 사용자 경로 정보 추가
        import os
        from pathlib import Path
        home_path = str(Path.home())
        desktop_path = str(Path.home() / "Desktop")
        documents_path = str(Path.home() / "Documents")
        downloads_path = str(Path.home() / "Downloads")

        return f"""당신은 사용 가능한 MCP 도구들을 활용해 사용자의 목표를 실행하는 에이전트입니다.

목표: {context.goal}

🔍 실제 시스템 경로 정보:
- 홈 디렉토리: {home_path}
- 바탕화면: {desktop_path}
- 문서 폴더: {documents_path}
- 다운로드 폴더: {downloads_path}

사용 가능한 도구(메타데이터):
{tools_desc}

🚨 CRITICAL: 도구 사용 우선 규칙 🚨
1) TODO 추가, 일정 추가, 계산, 파일 작업 등은 무조건 해당 도구를 사용해야 합니다
2) 절대로 "사용자가 직접 하세요"라고 답하지 마세요 - 당신이 도구로 해결하세요
3) 현재 날짜/시간이 필요하면 먼저 'system_time' 도구를 반드시 사용하세요
4) final_answer는 정말 도구로 해결할 수 없는 경우에만 사용하세요
5) 🔍 이전 대화에서 언급된 할일/작업들을 먼저 검색해서 찾아보세요 (키워드 포함 검색 활용)

🔍 파일 작업 필수 원칙:
⚠️ 파일/폴더 작업을 수행하기 전에 반드시 다음을 확인하세요:
1. 파일 작업 전 항상 filesystem 도구로 대상 경로의 실제 상태를 list로 먼저 확인
2. 파일과 폴더를 구분하여 확인 (파일을 폴더로 착각하지 마세요!)
3. 존재하지 않는 파일/폴더를 가정하지 마세요
4. 실제 확인 결과를 바탕으로 작업을 수행하세요

💡 대화 맥락 활용 가이드:
- 사용자가 특정 키워드를 이야기 하면 그 단어와 관련 모든 항목을 검색하세요
- 제목이 정확히 일치하지 않아도 그 안의 주요 키워드로 검색하세요
- list action으로 먼저 관련 항목들을 확인한 후 적절한 것을 선택하세요

행동 결정 규칙:
1) 파라미터는 메타데이터에 맞게 정확히 채웁니다
2) [선택값: A | B | C] 형태로 표시된 파라미터는 반드시 그 중 하나를 정확히 선택하세요
3) 날짜/시간은 ISO 형식(예: 2025-09-10T20:00:00+09:00)으로 변환
4) 정보가 모호하면 합리적인 기본값 사용
5) 반드시 JSON 형식만 출력

⚠️ 중요: 파라미터 구분을 정확히 하세요!
- 작업명/제목 변경: title 파라미터 사용
- 진행상황 변경: status 파라미터 사용 ("Not Started", "In Progress", "Completed", "Cancelled")
- 우선순위 변경: priority 파라미터 사용 ("높음", "중간", "낮음")
- 마감일 변경: due_date 파라미터 사용

예시 구분:
- "GPS개론 완료로 바꿔줘" → status를 "Completed"로 설정 (진행상황 완료)
- "제목을 GPS개론 완료로 바꿔줘" → title을 "GPS개론 완료"로 설정 (작업명 변경)
- "우선순위를 높음으로 바꿔줘" → priority를 "높음"으로 설정

⚠️ 중요: 선택값이 정해진 파라미터는 반드시 정확한 값을 사용하세요. 예를 들어:
- notion_todo의 action: 반드시 "create", "update", "delete", "get", "list", "complete" 중 하나
- priority: 반드시 "높음", "중간", "낮음" 중 하나
- status: 반드시 "Not Started", "In Progress", "Completed", "Cancelled" 중 하나

도구별 필수 규칙:
- notion_todo: 
  * action 필수값: create(새 할일), update(수정), delete(삭제), get(단일 조회), list(목록 조회), complete(완료 처리)
  * update/delete/complete/get에는 반드시 'todo_id'가 필요합니다. ID가 없으면 먼저 list로 후보를 조회하여 ID를 찾은 뒤 다음 스텝에서 해당 action을 수행하세요.
  * ⭐ list에서 query 파라미터 활용: 제목에 포함된 키워드로 검색 가능 (예: query="기행문"으로 기행문 관련 모든 할일 검색)
  * priority 선택값: "높음", "중간", "낮음"
  * status 선택값: "Not Started", "In Progress", "Completed", "Cancelled"
- notion_calendar:
  * action 필수값: create(새 일정), update(수정), delete(삭제), get(단일 조회), list(목록 조회)
- calculator:
  * action 필수값: calculate(계산 수행)
- filesystem:
  * action 필수값: list(목록 조회), stat(파일 정보), move(이동), copy(복사), mkdir(디렉토리 생성), trash_delete(휴지통), delete(영구 삭제)
  * ⚠️ 중요: 반드시 위의 실제 경로를 사용하세요! "/Users/your_username/" 같은 플레이스홀더 절대 금지!
  * ⚠️ 매개변수명 주의: "src", "dst" 사용 (source, destination 아님!)
  * mkdir 사용법: {{"action": "mkdir", "path": "{desktop_path}/새폴더", "parents": true}}
  * move 사용법: {{"action": "move", "src": "{desktop_path}/원본파일", "dst": "{desktop_path}/새폴더/원본파일"}}
  * copy 사용법: {{"action": "copy", "src": "{desktop_path}/원본", "dst": "{desktop_path}/복사본", "recursive": true}}
  * list 사용법: {{"action": "list", "path": "{desktop_path}", "include_hidden": false}}
  * 🔍 파일 작업 전 반드시 list로 실제 구조 확인!
- apple_notes:
  * action 필수값: create(새 메모), update(수정), search(검색), list(목록 조회)
- system_time:
  * 파라미터 없음 (현재 시간 반환)

응답 스키마 (정확한 필드명 사용 필수):
도구 사용 (우선):
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "create",
    "title": "GPS 개론 복습하기",
    "due_date": "2025-09-10T20:00:00+09:00",
    "priority": "중간"
  }},
  "reasoning": "사용자가 todo 추가를 요청했으므로 notion_todo 도구 사용"
}}

진행상황 변경 예시:
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "update",
    "todo_id": "existing_todo_id",
    "status": "Completed"
  }},
  "reasoning": "사용자가 진행상황을 완료로 변경하라고 요청했으므로 status를 Completed로 설정"
}}

우선순위 변경 예시:
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "update",
    "todo_id": "existing_todo_id",
    "priority": "높음"
  }},
  "reasoning": "사용자가 우선순위를 높음으로 변경하라고 요청했으므로 priority 설정"
}}

제목 변경 예시:
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "update",
    "todo_id": "existing_todo_id",
    "title": "새로운 작업명"
  }},
  "reasoning": "사용자가 작업명/제목을 변경하라고 요청했으므로 title 설정"
}}

할일 검색 예시:
{{
  "action_type": "tool_call",
  "tool_name": "notion_todo",
  "parameters": {{
    "action": "list",
    "query": "기행문",
    "filter": "pending"
  }},
  "reasoning": "기행문 관련 할일을 찾기 위해 query로 키워드 검색 수행"
}}

시스템 시간 조회 예시:
{{
  "action_type": "tool_call",
  "tool_name": "system_time",
  "parameters": {{}},
  "reasoning": "현재 시간 정보가 필요하므로 system_time 도구 사용"
}}

디렉토리 생성 예시:
{{
  "action_type": "tool_call",
  "tool_name": "filesystem",
  "parameters": {{
    "action": "mkdir",
    "path": "{desktop_path}/새폴더",
    "parents": true
  }},
  "reasoning": "새 폴더를 생성하기 위해 filesystem 도구의 mkdir 액션 사용"
}}

파일 이동 예시:
{{
  "action_type": "tool_call",
  "tool_name": "filesystem",
  "parameters": {{
    "action": "move",
    "src": "{desktop_path}/원본파일.pdf",
    "dst": "{desktop_path}/새폴더/원본파일.pdf"
  }},
  "reasoning": "파일을 새 위치로 이동하기 위해 filesystem 도구의 move 액션 사용"
}}

최종 답변 (마지막 수단):
{{
  "action_type": "final_answer",
  "answer": "직접 제공할 최종 답변",
  "reasoning": "도구 사용이 불필요하거나 목표 완료"
}}

⚠️ 중요: 반드시 "tool_name"과 "parameters"를 사용하세요. "function_name", "args" 등은 사용하지 마세요.

🚨 도구 이름 규칙:
- 절대로 "filesystem.mkdir", "notion_todo.create" 같은 방식으로 쓰지 마세요
- 올바른 형태: "tool_name": "filesystem", "parameters": {"action": "mkdir", ...}
- 올바른 형태: "tool_name": "notion_todo", "parameters": {"action": "create", ...}

🚨 경로 사용 규칙:
- 반드시 위에 제공된 실제 경로를 사용하세요!
- 절대로 "/Users/your_username/", "/Users/username/" 같은 플레이스홀더 사용 금지!
- 올바른 예: "{desktop_path}/새폴더"
- 잘못된 예: "/Users/your_username/Desktop/새폴더"
"""
    
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
            
            action_data = json.loads(content)
            # parameters가 null이거나 비-딕셔너리인 경우 빈 객체로 보정
            if isinstance(action_data, dict) and action_data.get("action_type") == "tool_call":
                if not isinstance(action_data.get("parameters"), dict):
                    action_data["parameters"] = {}
            
            # 매개변수 형식 정규화 (function_name -> tool_name, args -> parameters)
            if "function_name" in action_data and "tool_name" not in action_data:
                logger.warning(f"잘못된 필드명 감지 및 수정: function_name -> tool_name")
                action_data["tool_name"] = action_data.pop("function_name")
            
            if "args" in action_data and "parameters" not in action_data:
                logger.warning(f"잘못된 필드명 감지 및 수정: args -> parameters")
                args_data = action_data.pop("args")
                if isinstance(args_data, dict):
                    action_data["parameters"] = args_data
                elif isinstance(args_data, list) and len(args_data) > 0:
                    if isinstance(args_data[0], dict):
                        action_data["parameters"] = args_data[0]
                    else:
                        action_data["parameters"] = {}
                else:
                    action_data["parameters"] = {}
            
            return action_data
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
    
    def _has_date_in_context(self, context: AgentContext, thought: ThoughtRecord) -> bool:
        """컨텍스트에 날짜 정보가 있는지 확인"""
        # 목표에 날짜 관련 키워드가 있는지 확인
        date_keywords = ['오늘', '내일', '모레', '이번주', '다음주', '월요일', '화요일', '수요일', 
                        '목요일', '금요일', '토요일', '일요일', '시까지', '시간', '날짜']
        
        goal_lower = context.goal.lower()
        
        # 구체적인 날짜나 시간이 명시된 경우
        if any(keyword in goal_lower for keyword in date_keywords):
            # 사고 과정에서 이미 시간을 파악했다고 언급했는지 확인
            thought_lower = thought.content.lower()
            if '오늘' in thought_lower or '현재' in thought_lower or '2025' in thought_lower:
                return True
        
        return False
    
    def _quick_goal_check(self, scratchpad: AgentScratchpad, context: AgentContext) -> bool:
        """빠른 휴리스틱 목표 달성 판단"""
        if not scratchpad.steps:
            return False
            
        last_step = scratchpad.steps[-1]
        if not last_step.observation or not last_step.observation.success:
            return False
            
        goal_lower = context.goal.lower()
        
        # TODO 관련 작업 휴리스틱
        if 'todo' in goal_lower and ('추가' in goal_lower or '만들' in goal_lower):
            # notion_todo 도구가 성공했으면 달성
            if (last_step.action and 
                last_step.action.tool_name == 'notion_todo' and 
                last_step.observation.success):
                return True
        
        # 캘린더 관련 작업 휴리스틱  
        if ('캘린더' in goal_lower or '일정' in goal_lower) and '추가' in goal_lower:
            if (last_step.action and 
                last_step.action.tool_name == 'apple_calendar' and 
                last_step.observation.success):
                return True
        
        # 연락처 관련 작업 휴리스틱
        if '연락처' in goal_lower and '추가' in goal_lower:
            if (last_step.action and 
                last_step.action.tool_name == 'apple_contacts' and 
                last_step.observation.success):
                return True
                
        return False
    
    def _validate_and_fix_tool_params(self, tool_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """도구 매개변수 검증 및 자동 보정"""
        if not tool_name:
            return None
        
        # 파라미터 복사본 생성
        validated_params = params.copy()
        
        # 도구별 필수 매개변수 검증 및 보정
        if tool_name == "filesystem":
            if "action" not in validated_params:
                logger.warning(f"filesystem 도구의 필수 매개변수 'action'이 누락됨. 기본값 'list' 적용")
                validated_params["action"] = "list"
            
            # 잘못된 매개변수명 자동 변환
            if "source" in validated_params:
                validated_params["src"] = validated_params.pop("source")
                logger.warning(f"filesystem 도구의 매개변수 'source'를 'src'로 변환")
            if "destination" in validated_params:
                validated_params["dst"] = validated_params.pop("destination")
                logger.warning(f"filesystem 도구의 매개변수 'destination'을 'dst'로 변환")
        
        elif tool_name == "notion_todo":
            if "action" not in validated_params:
                logger.warning(f"notion_todo 도구의 필수 매개변수 'action'이 누락됨. 기본값 'list' 적용")
                validated_params["action"] = "list"
        
        elif tool_name == "notion_calendar":
            if "action" not in validated_params:
                logger.warning(f"notion_calendar 도구의 필수 매개변수 'action'이 누락됨. 기본값 'list' 적용")
                validated_params["action"] = "list"
        
        elif tool_name == "calculator":
            if "action" not in validated_params:
                logger.warning(f"calculator 도구의 필수 매개변수 'action'이 누락됨. 기본값 'calculate' 적용")
                validated_params["action"] = "calculate"
        
        # 도구 메타데이터를 통한 추가 검증
        tool_metadata = self.tool_registry.get_tool_metadata(tool_name)
        if tool_metadata:
            for param in tool_metadata.parameters:
                if param.required and param.name not in validated_params:
                    # 필수 매개변수가 누락된 경우 기본값 적용 시도
                    if param.default is not None:
                        validated_params[param.name] = param.default
                        logger.warning(f"{tool_name} 도구의 필수 매개변수 '{param.name}'에 기본값 적용: {param.default}")
                    else:
                        logger.error(f"{tool_name} 도구의 필수 매개변수 '{param.name}'이 누락되었고 기본값이 없음")
                        return None
        
        return validated_params
