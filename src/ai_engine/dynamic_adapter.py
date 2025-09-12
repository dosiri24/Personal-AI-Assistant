"""
동적 계획 수정 시스템 (Dynamic Plan Adaptation)

실행 과정에서 예상치 못한 상황이 발생했을 때 기존 계획을 동적으로 수정하는 시스템입니다.
변화된 상황을 반영하여 새로운 접근 방식을 고안하거나 목표 자체를 조정합니다.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .llm_provider import LLMProvider, ChatMessage
from .smart_file_matcher import SmartFileMatcher
from .agent_state import AgentContext
from .planning_engine import ExecutionPlan, PlanStep, TaskStatus, TaskPriority
from .goal_manager import GoalHierarchy, Goal, GoalType
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AdaptationTrigger(Enum):
    """계획 수정 트리거"""
    STEP_FAILURE = "step_failure"
    TIMEOUT_RISK = "timeout_risk"
    RESOURCE_CONSTRAINT = "resource_constraint"
    UNEXPECTED_RESULT = "unexpected_result"
    GOAL_CHANGE = "goal_change"
    EXTERNAL_EVENT = "external_event"


class AdaptationStrategy(Enum):
    """적응 전략"""
    RETRY = "retry"              # 재시도
    ALTERNATIVE = "alternative"   # 대안 접근
    SKIP = "skip"                # 건너뛰기
    REPLAN = "replan"            # 전체 재계획
    ADJUST_GOAL = "adjust_goal"   # 목표 조정
    ABORT = "abort"              # 중단


@dataclass
class AdaptationEvent:
    """적응 이벤트"""
    event_id: str
    trigger: AdaptationTrigger
    description: str
    affected_steps: List[str]
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    severity: int = 1  # 1-5 (5가 가장 심각)


@dataclass
class AdaptationAction:
    """적응 행동"""
    action_id: str
    strategy: AdaptationStrategy
    description: str
    modifications: List[Dict[str, Any]]
    expected_impact: str
    confidence: float = 0.8  # 0.0-1.0
    estimated_time: float = 30.0  # 초
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "strategy": self.strategy.value,
            "description": self.description,
            "modifications": self.modifications,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "estimated_time": self.estimated_time
        }


@dataclass
class AdaptationHistory:
    """적응 이력"""
    events: List[AdaptationEvent] = field(default_factory=list)
    actions: List[AdaptationAction] = field(default_factory=list)
    success_rate: float = 0.0
    
    def add_event(self, event: AdaptationEvent):
        """이벤트 추가"""
        self.events.append(event)
    
    def add_action(self, action: AdaptationAction):
        """행동 추가"""
        self.actions.append(action)
    
    def get_recent_patterns(self, hours: int = 24) -> List[AdaptationEvent]:
        """최근 패턴 반환"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [event for event in self.events if event.timestamp > cutoff_time]


class DynamicPlanAdapter:
    """
    동적 계획 수정 시스템
    
    실행 중 발생하는 예상치 못한 상황에 대응하여
    계획을 동적으로 수정하고 최적화합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.smart_file_matcher = SmartFileMatcher(llm_provider)
        self.adaptation_history = AdaptationHistory()
        
        logger.info("동적 계획 수정 시스템 초기화 완료 (SmartFileMatcher 포함)")
    
    async def analyze_situation(
        self,
        plan: ExecutionPlan,
        current_step: PlanStep,
        execution_result: Dict[str, Any],
        context: AgentContext
    ) -> Optional[AdaptationEvent]:
        """
        현재 상황 분석하여 적응 필요성 판단
        
        Args:
            plan: 현재 실행 계획
            current_step: 현재 실행 단계
            execution_result: 실행 결과
            context: 에이전트 컨텍스트
            
        Returns:
            AdaptationEvent: 적응 이벤트 (필요한 경우)
        """
        logger.debug(f"상황 분석 시작: {current_step.step_id}")
        
        # 다양한 트리거 조건 확인
        triggers = []
        
        # 1. 단계 실패 확인
        if execution_result.get("status") == "failed":
            triggers.append({
                "trigger": AdaptationTrigger.STEP_FAILURE,
                "description": f"단계 실행 실패: {execution_result.get('error', '')}",
                "severity": 4
            })
        
        # 2. 타임아웃 위험 확인
        elapsed_time = execution_result.get("total_elapsed", 0)
        remaining_time = context.timeout_seconds - elapsed_time
        remaining_steps = len([s for s in plan.steps if s.status == TaskStatus.PENDING])
        
        if remaining_steps > 0:
            avg_time_per_step = remaining_time / remaining_steps
            if avg_time_per_step < 15:  # 단계당 15초 미만
                triggers.append({
                    "trigger": AdaptationTrigger.TIMEOUT_RISK,
                    "description": f"타임아웃 위험: 단계당 {avg_time_per_step:.1f}초 남음",
                    "severity": 3
                })
        
        # 3. 예상치 못한 결과 확인
        expected_duration = current_step.estimated_duration
        actual_duration = execution_result.get("execution_time", 0)
        
        if actual_duration > expected_duration * 3:  # 예상보다 3배 이상 오래 걸림
            triggers.append({
                "trigger": AdaptationTrigger.UNEXPECTED_RESULT,
                "description": f"예상 시간 초과: {actual_duration:.1f}초 (예상: {expected_duration:.1f}초)",
                "severity": 2
            })
        
        # 4. 리소스 제약 확인
        if execution_result.get("resource_exhausted"):
            triggers.append({
                "trigger": AdaptationTrigger.RESOURCE_CONSTRAINT,
                "description": "리소스 제한에 도달",
                "severity": 3
            })
        
        # 가장 심각한 트리거 선택
        if triggers:
            primary_trigger = max(triggers, key=lambda t: t["severity"])
            
            event = AdaptationEvent(
                event_id=f"event_{int(time.time())}",
                trigger=primary_trigger["trigger"],
                description=primary_trigger["description"],
                affected_steps=[current_step.step_id],
                context={
                    "execution_result": execution_result,
                    "plan_status": {
                        "total_steps": len(plan.steps),
                        "completed": len([s for s in plan.steps if s.status == TaskStatus.COMPLETED]),
                        "pending": len([s for s in plan.steps if s.status == TaskStatus.PENDING]),
                        "failed": len([s for s in plan.steps if s.status == TaskStatus.FAILED])
                    }
                },
                severity=primary_trigger["severity"]
            )
            
            self.adaptation_history.add_event(event)
            logger.info(f"적응 이벤트 감지: {event.description}")
            return event
        
        return None
    
    async def generate_adaptation_strategy(
        self,
        event: AdaptationEvent,
        plan: ExecutionPlan,
        goal_hierarchy: Optional[GoalHierarchy] = None,
        context: Optional[AgentContext] = None
    ) -> AdaptationAction:
        """
        적응 전략 생성
        
        Args:
            event: 적응 이벤트
            plan: 현재 실행 계획
            goal_hierarchy: 목표 계층 구조
            context: 에이전트 컨텍스트
            
        Returns:
            AdaptationAction: 적응 행동
        """
        logger.info(f"적응 전략 생성: {event.trigger.value}")
        
        # LLM을 통한 전략 생성
        strategy_prompt = self._create_strategy_prompt(event, plan, goal_hierarchy, context)
        
        try:
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=strategy_prompt)
            ])
            
            strategy_data = self._parse_strategy_response(response.content)
            
            action = AdaptationAction(
                action_id=f"action_{int(time.time())}",
                strategy=AdaptationStrategy(strategy_data["strategy"]),
                description=strategy_data["description"],
                modifications=strategy_data["modifications"],
                expected_impact=strategy_data["expected_impact"],
                confidence=strategy_data.get("confidence", 0.8),
                estimated_time=strategy_data.get("estimated_time", 30.0)
            )
            
            self.adaptation_history.add_action(action)
            logger.info(f"적응 전략 생성 완료: {action.strategy.value}")
            return action
            
        except Exception as e:
            logger.error(f"적응 전략 생성 실패: {e}")
            return self._create_fallback_strategy(event)
    
    async def apply_adaptation(
        self,
        action: AdaptationAction,
        plan: ExecutionPlan,
        goal_hierarchy: Optional[GoalHierarchy] = None
    ) -> ExecutionPlan:
        """
        적응 행동 적용
        
        Args:
            action: 적응 행동
            plan: 현재 실행 계획
            goal_hierarchy: 목표 계층 구조
            
        Returns:
            ExecutionPlan: 수정된 실행 계획
        """
        logger.info(f"적응 행동 적용: {action.strategy.value}")
        
        if action.strategy == AdaptationStrategy.RETRY:
            return self._apply_retry_strategy(action, plan)
        
        elif action.strategy == AdaptationStrategy.ALTERNATIVE:
            return self._apply_alternative_strategy(action, plan)
        
        elif action.strategy == AdaptationStrategy.SKIP:
            return self._apply_skip_strategy(action, plan)
        
        elif action.strategy == AdaptationStrategy.REPLAN:
            return await self._apply_replan_strategy(action, plan)
        
        elif action.strategy == AdaptationStrategy.ADJUST_GOAL:
            return self._apply_goal_adjustment_strategy(action, plan, goal_hierarchy)
        
        elif action.strategy == AdaptationStrategy.ABORT:
            return self._apply_abort_strategy(action, plan)
        
        else:
            logger.warning(f"알 수 없는 적응 전략: {action.strategy}")
            return plan
    
    def _create_strategy_prompt(
        self,
        event: AdaptationEvent,
        plan: ExecutionPlan,
        goal_hierarchy: Optional[GoalHierarchy],
        context: Optional[AgentContext]
    ) -> str:
        """전략 생성을 위한 프롬프트 생성"""
        
        plan_status = {
            "total_steps": len(plan.steps),
            "completed": len([s for s in plan.steps if s.status == TaskStatus.COMPLETED]),
            "pending": len([s for s in plan.steps if s.status == TaskStatus.PENDING]),
            "failed": len([s for s in plan.steps if s.status == TaskStatus.FAILED])
        }
        
        context_info = ""
        if context:
            remaining_time = context.timeout_seconds - event.context.get("execution_result", {}).get("total_elapsed", 0)
            context_info = f"""
**컨텍스트 정보**:
- 남은 시간: {remaining_time:.1f}초
- 최대 반복: {context.max_iterations}
- 제약 조건: {context.constraints}
"""
        
        prompt = f"""
현재 실행 중인 계획에서 문제가 발생했습니다. 최적의 적응 전략을 제안해주세요.

**목표**: {plan.goal}

**발생한 문제**:
- 트리거: {event.trigger.value}
- 설명: {event.description}
- 심각도: {event.severity}/5
- 영향받는 단계: {', '.join(event.affected_steps)}

**현재 계획 상태**:
- 전체 단계: {plan_status['total_steps']}
- 완료: {plan_status['completed']}
- 대기: {plan_status['pending']}
- 실패: {plan_status['failed']}
{context_info}

**사용 가능한 적응 전략**:
1. retry: 실패한 단계 재시도
2. alternative: 대안 접근 방식 사용
3. skip: 현재 단계 건너뛰기
4. replan: 전체 계획 재수립
5. adjust_goal: 목표 조정
6. abort: 실행 중단

**요구사항**:
현재 상황에 가장 적합한 전략을 선택하고, 구체적인 수정 사항을 제안해주세요.

응답은 다음 JSON 형식으로 해주세요:

```json
{{
    "strategy": "retry|alternative|skip|replan|adjust_goal|abort",
    "description": "전략에 대한 상세 설명",
    "modifications": [
        {{
            "type": "step_modification|goal_change|parameter_update",
            "target": "수정 대상 ID",
            "action": "수정 내용",
            "details": "상세 설명"
        }}
    ],
    "expected_impact": "예상 효과",
    "confidence": 0.8,
    "estimated_time": 45.0
}}
```
"""
        return prompt
    
    def _parse_strategy_response(self, response: str) -> Dict[str, Any]:
        """전략 응답 파싱"""
        try:
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response.strip()
            
            return json.loads(json_text)
            
        except Exception as e:
            logger.error(f"전략 응답 파싱 실패: {e}")
            return {
                "strategy": "retry",
                "description": "기본 재시도 전략",
                "modifications": [],
                "expected_impact": "재시도를 통한 문제 해결",
                "confidence": 0.5,
                "estimated_time": 30.0
            }
    
    def _create_fallback_strategy(self, event: AdaptationEvent) -> AdaptationAction:
        """기본 적응 전략 생성"""
        strategy = AdaptationStrategy.RETRY
        
        # 이벤트 타입에 따른 기본 전략 선택
        if event.trigger == AdaptationTrigger.TIMEOUT_RISK:
            strategy = AdaptationStrategy.SKIP
        elif event.trigger == AdaptationTrigger.RESOURCE_CONSTRAINT:
            strategy = AdaptationStrategy.ALTERNATIVE
        elif event.severity >= 4:
            strategy = AdaptationStrategy.REPLAN
        
        return AdaptationAction(
            action_id=f"fallback_{int(time.time())}",
            strategy=strategy,
            description=f"기본 {strategy.value} 전략",
            modifications=[],
            expected_impact="문제 상황 완화",
            confidence=0.5
        )
    
    def _apply_retry_strategy(self, action: AdaptationAction, plan: ExecutionPlan) -> ExecutionPlan:
        """재시도 전략 적용"""
        for modification in action.modifications:
            if modification.get("type") == "step_modification":
                step_id = modification.get("target")
                for step in plan.steps:
                    if step.step_id == step_id and step.status == TaskStatus.FAILED:
                        step.status = TaskStatus.PENDING
                        step.error = None
                        step.estimated_duration *= 1.2  # 시간 여유 추가
                        logger.debug(f"단계 재시도 설정: {step_id}")
        
        return plan
    
    def _apply_alternative_strategy(self, action: AdaptationAction, plan: ExecutionPlan) -> ExecutionPlan:
        """대안 전략 적용 - 2단계 접근법: 탐색 → 실행"""
        for modification in action.modifications:
            if modification.get("type") == "step_modification":
                step_id = modification.get("target")
                for step in plan.steps:
                    if step.step_id == step_id and step.status == TaskStatus.FAILED:
                        # 파일 관련 작업 실패 시 MCP Doctor 통한 해결
                        if step.tool_name == "filesystem" and step.tool_params:
                            original_action = step.tool_params.get("action")
                            original_path = step.tool_params.get("path")
                            
                            # 1단계: MCP Doctor에게 오류 진단 요청
                            doctor_step = PlanStep(
                                step_id=f"{step_id}_doctor",
                                description=f"MCP Doctor를 통한 오류 진단 및 해결책 조회",
                                action_type="tool_call",
                                tool_name="mcp_doctor",
                                tool_params={
                                    "query_type": "error_diagnosis",
                                    "tool_name": "filesystem",
                                    "error_message": step.error or "매개변수 오류"
                                }
                            )
                            plan.steps.append(doctor_step)
                            
                            # 2단계: 시스템 탐색으로 변경 (범용적 탐색)
                            step.tool_name = "system_explorer"
                            step.tool_params = {
                                "action": "get_structure",  # 범용적 구조 탐색
                                "path": original_path or "/Users/taesooa/Desktop",
                                "depth": 1  # 최상위 파일들만 탐색
                            }
                            step.description = f"1단계: 대상 디렉토리 파일 목록 탐색 (원래 작업: {original_action})"
                            step.dependencies = [f"{step_id}_doctor"]  # Doctor 조회 후 실행
                            
                            # 3단계: 정정된 매개변수로 실제 파일 작업
                            corrected_action = "delete" if original_action == "delete_file" else original_action
                            execute_step = PlanStep(
                                step_id=f"{step_id}_execute",
                                description=f"2단계: 파일 {corrected_action} 실행 (Doctor 조언 반영)",
                                action_type="tool_call",
                                tool_name="filesystem",
                                tool_params={
                                    "action": corrected_action,  # 정정된 정확한 action 값 사용
                                    "path": original_path or "탐색_결과_기반"
                                },
                                dependencies=[step_id] if step_id else []  # 탐색 완료 후 실행
                            )
                            plan.steps.append(execute_step)
                            
                        # 기타 대안 적용
                        elif "alternative_tool" in modification:
                            step.tool_name = modification["alternative_tool"]
                        if "alternative_params" in modification:
                            step.tool_params = modification["alternative_params"]
                        
                        step.status = TaskStatus.PENDING
                        step.error = None  # 에러 메시지 초기화
                        logger.debug(f"2단계 대안 전략 적용: {step_id} - 탐색 후 실행")
        
        return plan
    
    def _apply_skip_strategy(self, action: AdaptationAction, plan: ExecutionPlan) -> ExecutionPlan:
        """건너뛰기 전략 적용"""
        for modification in action.modifications:
            if modification.get("type") == "step_modification":
                step_id = modification.get("target")
                for step in plan.steps:
                    if step.step_id == step_id:
                        step.status = TaskStatus.SKIPPED
                        logger.debug(f"단계 건너뛰기: {step_id}")
        
        return plan
    
    async def _apply_replan_strategy(self, action: AdaptationAction, plan: ExecutionPlan) -> ExecutionPlan:
        """재계획 전략 적용"""
        # 새로운 계획 생성 (간단한 구현)
        remaining_steps = [s for s in plan.steps if s.status == TaskStatus.PENDING]
        
        # 실패한 단계들을 대안 방식으로 재구성
        for step in remaining_steps:
            step.estimated_duration *= 0.8  # 시간 단축
            step.priority = TaskPriority.HIGH  # 우선순위 상향
        
        logger.info("재계획 전략 적용 완료")
        return plan
    
    def _apply_goal_adjustment_strategy(
        self, 
        action: AdaptationAction, 
        plan: ExecutionPlan,
        goal_hierarchy: Optional[GoalHierarchy]
    ) -> ExecutionPlan:
        """목표 조정 전략 적용"""
        for modification in action.modifications:
            if modification.get("type") == "goal_change":
                # 목표 우선순위 조정 또는 일부 목표 제거
                new_goal = modification.get("new_goal", plan.goal)
                plan.goal = new_goal
                logger.info(f"목표 조정: {new_goal}")
        
        return plan
    
    def _apply_abort_strategy(self, action: AdaptationAction, plan: ExecutionPlan) -> ExecutionPlan:
        """중단 전략 적용"""
        for step in plan.steps:
            if step.status == TaskStatus.PENDING:
                step.status = TaskStatus.SKIPPED
        
        logger.warning("계획 실행 중단")
        return plan
