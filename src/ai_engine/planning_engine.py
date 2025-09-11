"""
고급 계획 수립 시스템 (Planning Engine)

복잡한 목표를 여러 단계로 분해하고 각 단계를 순차적으로 실행하는
고급 계획 수립 시스템을 구현합니다.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .llm_provider import LLMProvider, ChatMessage
from .agent_state import AgentContext
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class PlanStep:
    """계획 단계"""
    step_id: str
    description: str
    action_type: str  # "tool_call", "reasoning", "final_answer"
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    dependencies: List[str] = field(default_factory=list)
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration: float = 30.0  # 초
    success_criteria: str = ""
    failure_recovery: str = ""
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None


@dataclass
class ExecutionPlan:
    """실행 계획"""
    plan_id: str
    goal: str
    steps: List[PlanStep]
    estimated_total_time: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    execution_strategy: str = "sequential"  # "sequential", "parallel", "adaptive"
    
    def __post_init__(self):
        self.estimated_total_time = sum(step.estimated_duration for step in self.steps)
    
    def get_next_steps(self) -> List[PlanStep]:
        """실행 가능한 다음 단계들 반환"""
        ready_steps = []
        
        for step in self.steps:
            if step.status == TaskStatus.PENDING:
                # 의존성 확인
                dependencies_met = all(
                    any(s.step_id == dep_id and s.status == TaskStatus.COMPLETED 
                        for s in self.steps)
                    for dep_id in step.dependencies
                )
                
                if dependencies_met:
                    ready_steps.append(step)
        
        # 우선순위 순으로 정렬
        return sorted(ready_steps, key=lambda x: x.priority.value, reverse=True)
    
    def is_completed(self) -> bool:
        """계획 완료 여부"""
        return all(step.status in [TaskStatus.COMPLETED, TaskStatus.SKIPPED] 
                  for step in self.steps)
    
    def has_failed(self) -> bool:
        """계획 실패 여부"""
        return any(step.status == TaskStatus.FAILED for step in self.steps)


class PlanningEngine:
    """
    고급 계획 수립 엔진
    
    복잡한 목표를 여러 단계로 분해하고 각 단계의 의존성과 실행 순서를 결정합니다.
    실행 과정에서 계획을 동적으로 수정하고 최적화합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.active_plans: Dict[str, ExecutionPlan] = {}
        
        logger.info("계획 수립 엔진 초기화 완료")
    
    async def create_execution_plan(
        self, 
        goal: str, 
        context: AgentContext,
        available_tools: List[Dict[str, Any]]
    ) -> ExecutionPlan:
        """
        목표에 대한 실행 계획 생성
        
        Args:
            goal: 달성할 목표
            context: 에이전트 컨텍스트
            available_tools: 사용 가능한 도구 목록
            
        Returns:
            ExecutionPlan: 생성된 실행 계획
        """
        logger.info(f"실행 계획 생성 시작: {goal}")
        
        # LLM을 통한 계획 생성
        plan_prompt = self._create_planning_prompt(goal, context, available_tools)
        
        try:
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=plan_prompt)
            ])
            
            plan_data = self._parse_plan_response(response.content, goal)
            
            # ExecutionPlan 객체 생성
            plan = ExecutionPlan(
                plan_id=f"plan_{int(time.time())}",
                goal=goal,
                steps=plan_data["steps"],
                execution_strategy=plan_data.get("strategy", "sequential")
            )
            
            # 계획 등록
            self.active_plans[plan.plan_id] = plan
            
            logger.info(f"실행 계획 생성 완료: {plan.plan_id} ({len(plan.steps)}단계)")
            return plan
            
        except Exception as e:
            logger.error(f"계획 생성 실패: {e}")
            # 기본 계획 생성
            return self._create_fallback_plan(goal)
    
    async def update_plan(
        self, 
        plan: ExecutionPlan, 
        execution_result: Dict[str, Any],
        context: AgentContext
    ) -> ExecutionPlan:
        """
        실행 결과를 바탕으로 계획 동적 수정
        
        Args:
            plan: 현재 실행 계획
            execution_result: 최근 실행 결과
            context: 에이전트 컨텍스트
            
        Returns:
            ExecutionPlan: 수정된 실행 계획
        """
        logger.debug(f"계획 수정 검토: {plan.plan_id}")
        
        # 실행 결과 분석
        needs_replanning = await self._analyze_execution_result(
            plan, execution_result, context
        )
        
        if needs_replanning:
            logger.info(f"계획 수정 필요: {plan.plan_id}")
            
            # 새로운 계획 생성
            updated_plan = await self._generate_updated_plan(
                plan, execution_result, context
            )
            
            # 기존 계획 교체
            self.active_plans[plan.plan_id] = updated_plan
            updated_plan.updated_at = datetime.now()
            
            logger.info(f"계획 수정 완료: {plan.plan_id}")
            return updated_plan
        
        return plan
    
    def _create_planning_prompt(
        self, 
        goal: str, 
        context: AgentContext,
        available_tools: List[Dict[str, Any]]
    ) -> str:
        """계획 생성을 위한 프롬프트 생성"""
        
        tools_description = "\n".join([
            f"- {tool['name']}: {tool.get('description', '')}"
            for tool in available_tools
        ])
        
        prompt = f"""
목표를 달성하기 위한 상세한 실행 계획을 수립해주세요.

**목표**: {goal}

**사용 가능한 도구들**:
{tools_description}

**현재 컨텍스트**:
- 최대 반복 횟수: {context.max_iterations}
- 타임아웃: {context.timeout_seconds}초
- 사용자 선호도: {context.user_preferences}
- 제약 조건: {context.constraints}

**🔍 파일 작업 필수 원칙**:
⚠️ 파일/폴더 작업을 수행하기 전에 반드시 다음을 확인하세요:
1. 첫 번째 단계는 항상 filesystem 도구로 대상 경로의 실제 상태를 list로 확인
2. 파일과 폴더를 구분하여 확인 (파일을 폴더로 착각하지 마세요!)
3. 존재하지 않는 파일/폴더를 가정하지 마세요
4. 실제 확인 결과를 바탕으로 후속 단계를 계획하세요

**요구사항**:
1. 목표를 달성하기 위한 구체적인 단계들을 나열해주세요
2. 각 단계에 대해 다음 정보를 포함해주세요:
   - 단계 설명
   - 사용할 도구 (해당하는 경우)
   - 예상 소요 시간 (초)
   - 성공 기준
   - 실패 시 복구 방안
   - 우선순위 (1-4, 4가 가장 높음)
3. 단계 간 의존성이 있다면 명시해주세요

응답은 반드시 다음 JSON 형식으로 해주세요 (정확한 필드명 사용 필수):

```json
{{
    "strategy": "sequential|parallel|adaptive",
    "steps": [
        {{
            "step_id": "step_1",
            "description": "첫 번째 단계 설명",
            "action_type": "tool_call|reasoning|final_answer",
            "tool_name": "도구명 (해당하는 경우)",
            "tool_params": {{"param1": "value1"}},
            "dependencies": [],
            "priority": 3,
            "estimated_duration": 30.0,
            "success_criteria": "성공 기준",
            "failure_recovery": "실패 시 복구 방안"
        }}
    ]
}}
```

⚠️ 주의: 반드시 "tool_name"과 "tool_params"를 사용하세요. "function_name"이나 "args" 같은 다른 필드명은 사용하지 마세요.
"""
        return prompt
    
    def _parse_plan_response(self, response: str, goal: str) -> Dict[str, Any]:
        """LLM 응답을 파싱하여 계획 데이터 추출"""
        try:
            # JSON 응답 파싱
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response.strip()
            
            plan_data = json.loads(json_text)
            
            # PlanStep 객체로 변환
            steps = []
            for i, step_data in enumerate(plan_data.get("steps", [])):
                # 매개변수 형식 정규화 (function_name -> tool_name, args -> tool_params)
                tool_name = step_data.get("tool_name") or step_data.get("function_name")
                tool_params = step_data.get("tool_params", {})
                
                # 잘못된 형식 사용 감지 및 정규화
                if "function_name" in step_data:
                    logger.warning(f"잘못된 필드명 감지 및 수정: function_name -> tool_name")
                
                if "args" in step_data:
                    logger.warning(f"잘못된 필드명 감지 및 수정: args -> tool_params")
                    # args가 있으면 tool_params로 변환
                    args_data = step_data.get("args", {})
                    if isinstance(args_data, dict):
                        tool_params.update(args_data)
                    elif isinstance(args_data, list) and len(args_data) > 0:
                        # 리스트 형태면 첫 번째 요소가 딕셔너리인지 확인
                        if isinstance(args_data[0], dict):
                            tool_params.update(args_data[0])
                
                step = PlanStep(
                    step_id=step_data.get("step_id", f"step_{i+1}"),
                    description=step_data.get("description", ""),
                    action_type=step_data.get("action_type", "tool_call"),
                    tool_name=tool_name,
                    tool_params=tool_params,
                    dependencies=step_data.get("dependencies", []),
                    priority=TaskPriority(step_data.get("priority", 2)),
                    estimated_duration=step_data.get("estimated_duration", 30.0),
                    success_criteria=step_data.get("success_criteria", ""),
                    failure_recovery=step_data.get("failure_recovery", "")
                )
                steps.append(step)
            
            return {
                "strategy": plan_data.get("strategy", "sequential"),
                "steps": steps
            }
            
        except Exception as e:
            logger.error(f"계획 응답 파싱 실패: {e}")
            return self._create_fallback_plan_data(goal)
    
    def _create_fallback_plan_data(self, goal: str) -> Dict[str, Any]:
        """파싱 실패 시 기본 계획 데이터 생성"""
        return {
            "strategy": "sequential",
            "steps": [
                PlanStep(
                    step_id="step_1",
                    description=f"목표 달성을 위한 단계: {goal}",
                    action_type="reasoning",
                    priority=TaskPriority.HIGH,
                    estimated_duration=60.0,
                    success_criteria="목표가 달성됨",
                    failure_recovery="다른 접근 방식 시도"
                )
            ]
        }
    
    def _create_fallback_plan(self, goal: str) -> ExecutionPlan:
        """기본 실행 계획 생성"""
        plan_data = self._create_fallback_plan_data(goal)
        
        return ExecutionPlan(
            plan_id=f"fallback_{int(time.time())}",
            goal=goal,
            steps=plan_data["steps"],
            execution_strategy="sequential"
        )
    
    async def _analyze_execution_result(
        self, 
        plan: ExecutionPlan,
        execution_result: Dict[str, Any],
        context: AgentContext
    ) -> bool:
        """실행 결과 분석하여 재계획 필요성 판단"""
        
        # 실패한 단계가 있는지 확인
        if execution_result.get("status") == "failed":
            return True
        
        # 예상 시간과 실제 시간 차이가 큰지 확인
        expected_time = execution_result.get("expected_duration", 0)
        actual_time = execution_result.get("actual_duration", 0)
        
        if actual_time > expected_time * 2:  # 예상보다 2배 이상 오래 걸림
            return True
        
        # 남은 시간 확인
        remaining_time = context.timeout_seconds - execution_result.get("total_elapsed", 0)
        remaining_steps = len([s for s in plan.steps if s.status == TaskStatus.PENDING])
        
        if remaining_steps > 0:
            avg_time_per_step = remaining_time / remaining_steps
            if avg_time_per_step < 10:  # 단계당 10초 미만 남음
                return True
        
        return False
    
    async def _generate_updated_plan(
        self,
        original_plan: ExecutionPlan,
        execution_result: Dict[str, Any],
        context: AgentContext
    ) -> ExecutionPlan:
        """수정된 계획 생성"""
        
        # 간단한 수정: 실패한 단계를 다른 방식으로 재시도
        updated_steps = []
        
        for step in original_plan.steps:
            if step.status == TaskStatus.FAILED:
                # 실패한 단계를 수정
                new_step = PlanStep(
                    step_id=f"{step.step_id}_retry",
                    description=f"재시도: {step.description}",
                    action_type=step.action_type,
                    tool_name=step.tool_name,
                    tool_params=step.tool_params,
                    dependencies=step.dependencies,
                    priority=TaskPriority.HIGH,
                    estimated_duration=step.estimated_duration * 1.5,
                    success_criteria=step.success_criteria,
                    failure_recovery="대안 접근 방식 사용"
                )
                updated_steps.append(new_step)
            elif step.status == TaskStatus.PENDING:
                updated_steps.append(step)
        
        return ExecutionPlan(
            plan_id=original_plan.plan_id,
            goal=original_plan.goal,
            steps=updated_steps,
            execution_strategy=original_plan.execution_strategy
        )
