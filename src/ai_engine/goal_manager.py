"""
목표 관리 시스템 (Goal Manager)

복잡한 목표를 효과적으로 분해하고 우선순위를 관리하는 시스템입니다.
주요 목표와 부차적 목표를 구분하고 중요도와 긴급도를 평가합니다.
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from .llm_provider import LLMProvider, ChatMessage
from .agent_state import AgentContext
from .planning_engine import TaskPriority, TaskStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GoalType(Enum):
    """목표 유형"""
    PRIMARY = "primary"      # 주요 목표
    SECONDARY = "secondary"  # 부차적 목표
    PREREQUISITE = "prerequisite"  # 전제 조건
    OPTIONAL = "optional"    # 선택적 목표


class GoalUrgency(Enum):
    """목표 긴급도"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Goal:
    """목표 정의"""
    goal_id: str
    description: str
    goal_type: GoalType = GoalType.PRIMARY
    priority: TaskPriority = TaskPriority.MEDIUM
    urgency: GoalUrgency = GoalUrgency.MEDIUM
    dependencies: List[str] = field(default_factory=list)
    sub_goals: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get_combined_priority_score(self) -> float:
        """우선순위와 긴급도를 결합한 점수 계산"""
        priority_weight = 0.6
        urgency_weight = 0.4
        
        return (self.priority.value * priority_weight + 
                self.urgency.value * urgency_weight)
    
    def is_executable(self, completed_goals: Set[str]) -> bool:
        """실행 가능한 목표인지 확인 (의존성 체크)"""
        return all(dep_id in completed_goals for dep_id in self.dependencies)


@dataclass
class GoalHierarchy:
    """목표 계층 구조"""
    root_goal: Goal
    all_goals: Dict[str, Goal] = field(default_factory=dict)
    execution_order: List[str] = field(default_factory=list)
    
    def add_goal(self, goal: Goal, parent_id: Optional[str] = None):
        """목표 추가"""
        self.all_goals[goal.goal_id] = goal
        
        if parent_id and parent_id in self.all_goals:
            parent_goal = self.all_goals[parent_id]
            if goal.goal_id not in parent_goal.sub_goals:
                parent_goal.sub_goals.append(goal.goal_id)
            
            # 부모의 의존성 설정
            if parent_id not in goal.dependencies:
                goal.dependencies.append(parent_id)
    
    def get_next_executable_goals(self) -> List[Goal]:
        """다음에 실행 가능한 목표들 반환"""
        completed_goals = {
            goal_id for goal_id, goal in self.all_goals.items()
            if goal.status == TaskStatus.COMPLETED
        }
        
        executable_goals = [
            goal for goal in self.all_goals.values()
            if (goal.status == TaskStatus.PENDING and 
                goal.is_executable(completed_goals))
        ]
        
        # 우선순위 점수로 정렬
        return sorted(executable_goals, 
                     key=lambda g: g.get_combined_priority_score(), 
                     reverse=True)
    
    def update_execution_order(self):
        """실행 순서 업데이트 (토폴로지 정렬)"""
        # 간단한 토폴로지 정렬 구현
        in_degree = {goal_id: 0 for goal_id in self.all_goals}
        
        # 의존성 계산
        for goal in self.all_goals.values():
            for dep_id in goal.dependencies:
                if dep_id in in_degree:
                    in_degree[goal.goal_id] += 1
        
        # 큐 초기화 (의존성이 없는 목표들)
        queue = [goal_id for goal_id, degree in in_degree.items() if degree == 0]
        execution_order = []
        
        while queue:
            # 우선순위 고려하여 정렬
            queue.sort(key=lambda gid: self.all_goals[gid].get_combined_priority_score(), 
                      reverse=True)
            
            current_goal_id = queue.pop(0)
            execution_order.append(current_goal_id)
            
            # 현재 목표에 의존하는 목표들의 의존성 감소
            for goal in self.all_goals.values():
                if current_goal_id in goal.dependencies:
                    in_degree[goal.goal_id] -= 1
                    if in_degree[goal.goal_id] == 0:
                        queue.append(goal.goal_id)
        
        self.execution_order = execution_order


class GoalManager:
    """
    목표 관리 시스템
    
    복잡한 목표를 분해하고 우선순위를 관리하며,
    실행 가능한 목표 순서를 결정합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
        self.active_hierarchies: Dict[str, GoalHierarchy] = {}
        
        logger.info("목표 관리 시스템 초기화 완료")
    
    async def decompose_goal(
        self, 
        primary_goal: str, 
        context: AgentContext,
        available_tools: List[Dict[str, Any]]
    ) -> GoalHierarchy:
        """
        복잡한 목표를 하위 목표들로 분해
        
        Args:
            primary_goal: 주요 목표
            context: 에이전트 컨텍스트
            available_tools: 사용 가능한 도구 목록
            
        Returns:
            GoalHierarchy: 목표 계층 구조
        """
        logger.info(f"목표 분해 시작: {primary_goal}")
        
        # LLM을 통한 목표 분해
        decomposition_prompt = self._create_goal_decomposition_prompt(
            primary_goal, context, available_tools
        )
        
        try:
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=decomposition_prompt)
            ])
            
            goal_data = self._parse_goal_response(response.content, primary_goal)
            
            # GoalHierarchy 생성
            hierarchy = self._create_goal_hierarchy(goal_data, primary_goal)
            
            # 실행 순서 계산
            hierarchy.update_execution_order()
            
            # 계층 구조 등록
            hierarchy_id = f"hierarchy_{int(time.time())}"
            self.active_hierarchies[hierarchy_id] = hierarchy
            
            logger.info(f"목표 분해 완료: {len(hierarchy.all_goals)}개 목표 생성")
            return hierarchy
            
        except Exception as e:
            logger.error(f"목표 분해 실패: {e}")
            return self._create_fallback_hierarchy(primary_goal)
    
    async def reorder_goals(
        self,
        hierarchy: GoalHierarchy,
        execution_context: Dict[str, Any]
    ) -> GoalHierarchy:
        """
        실행 상황에 따라 목표 우선순위 재조정
        
        Args:
            hierarchy: 목표 계층 구조
            execution_context: 실행 컨텍스트 (시간, 리소스 등)
            
        Returns:
            GoalHierarchy: 재조정된 목표 계층 구조
        """
        logger.debug("목표 우선순위 재조정 시작")
        
        # 실행 상황 분석
        remaining_time = execution_context.get("remaining_time", 300)
        completed_goals = execution_context.get("completed_goals", [])
        failed_goals = execution_context.get("failed_goals", [])
        
        # 목표별 우선순위 재계산
        for goal in hierarchy.all_goals.values():
            if goal.status == TaskStatus.PENDING:
                # 시간 압박에 따른 긴급도 조정
                if remaining_time < 60:  # 1분 미만 남음
                    if goal.goal_type == GoalType.PRIMARY:
                        goal.urgency = GoalUrgency.CRITICAL
                    elif goal.goal_type == GoalType.SECONDARY:
                        goal.urgency = GoalUrgency.HIGH
                
                # 실패한 목표에 의존하는 목표의 우선순위 낮춤
                if any(failed_id in goal.dependencies for failed_id in failed_goals):
                    goal.priority = TaskPriority.LOW
        
        # 실행 순서 재계산
        hierarchy.update_execution_order()
        
        logger.debug("목표 우선순위 재조정 완료")
        return hierarchy
    
    def _create_goal_decomposition_prompt(
        self, 
        primary_goal: str, 
        context: AgentContext,
        available_tools: List[Dict[str, Any]]
    ) -> str:
        """목표 분해를 위한 프롬프트 생성"""
        
        tools_description = "\n".join([
            f"- {tool['name']}: {tool.get('description', '')}"
            for tool in available_tools
        ])
        
        prompt = f"""
주어진 목표를 달성하기 위해 체계적인 하위 목표들로 분해해주세요.

**주요 목표**: {primary_goal}

**사용 가능한 도구들**:
{tools_description}

**컨텍스트**:
- 사용자 ID: {context.user_id}
- 최대 반복 횟수: {context.max_iterations}
- 타임아웃: {context.timeout_seconds}초
- 사용자 선호도: {context.user_preferences}
- 제약 조건: {context.constraints}

**분해 요구사항**:
1. 주요 목표를 달성하기 위한 논리적 하위 목표들로 분해
2. 각 하위 목표의 유형, 우선순위, 긴급도 설정
3. 목표 간 의존성 관계 정의
4. 성공 기준 명시

**목표 유형**:
- primary: 핵심 목표
- secondary: 부차적 목표  
- prerequisite: 전제 조건
- optional: 선택적 목표

**우선순위**: 1(낮음) ~ 4(높음)
**긴급도**: 1(낮음) ~ 4(긴급)

응답은 다음 JSON 형식으로 해주세요:

```json
{{
    "goals": [
        {{
            "goal_id": "goal_1",
            "description": "목표 설명",
            "goal_type": "primary|secondary|prerequisite|optional",
            "priority": 3,
            "urgency": 2,
            "dependencies": ["prerequisite_goal_id"],
            "success_criteria": ["성공 기준 1", "성공 기준 2"],
            "constraints": {{"time_limit": 60}}
        }}
    ],
    "relationships": [
        {{
            "parent_id": "goal_1",
            "child_id": "goal_2"
        }}
    ]
}}
```
"""
        return prompt
    
    def _parse_goal_response(self, response: str, primary_goal: str) -> Dict[str, Any]:
        """LLM 응답을 파싱하여 목표 데이터 추출"""
        try:
            # JSON 응답 파싱
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                json_text = response[json_start:json_end].strip()
            else:
                json_text = response.strip()
            
            return json.loads(json_text)
            
        except Exception as e:
            logger.error(f"목표 응답 파싱 실패: {e}")
            return self._create_fallback_goal_data(primary_goal)
    
    def _create_fallback_goal_data(self, primary_goal: str) -> Dict[str, Any]:
        """파싱 실패 시 기본 목표 데이터 생성"""
        return {
            "goals": [
                {
                    "goal_id": "main_goal",
                    "description": primary_goal,
                    "goal_type": "primary",
                    "priority": 4,
                    "urgency": 3,
                    "dependencies": [],
                    "success_criteria": [f"{primary_goal} 달성"],
                    "constraints": {}
                }
            ],
            "relationships": []
        }
    
    def _create_goal_hierarchy(
        self, 
        goal_data: Dict[str, Any], 
        primary_goal: str
    ) -> GoalHierarchy:
        """목표 데이터에서 GoalHierarchy 생성"""
        
        goals = {}
        root_goal = None
        
        # Goal 객체들 생성
        for goal_info in goal_data.get("goals", []):
            goal = Goal(
                goal_id=goal_info["goal_id"],
                description=goal_info["description"],
                goal_type=GoalType(goal_info.get("goal_type", "primary")),
                priority=TaskPriority(goal_info.get("priority", 2)),
                urgency=GoalUrgency(goal_info.get("urgency", 2)),
                dependencies=goal_info.get("dependencies", []),
                success_criteria=goal_info.get("success_criteria", []),
                constraints=goal_info.get("constraints", {})
            )
            
            goals[goal.goal_id] = goal
            
            # 루트 목표 찾기 (primary 타입이면서 의존성이 없는 것)
            if (goal.goal_type == GoalType.PRIMARY and 
                not goal.dependencies and root_goal is None):
                root_goal = goal
        
        # 루트 목표가 없으면 첫 번째 목표를 루트로 설정
        if root_goal is None and goals:
            root_goal = list(goals.values())[0]
        
        # 관계 설정
        for relationship in goal_data.get("relationships", []):
            parent_id = relationship["parent_id"]
            child_id = relationship["child_id"]
            
            if parent_id in goals and child_id in goals:
                parent_goal = goals[parent_id]
                child_goal = goals[child_id]
                
                if child_id not in parent_goal.sub_goals:
                    parent_goal.sub_goals.append(child_id)
                
                if parent_id not in child_goal.dependencies:
                    child_goal.dependencies.append(parent_id)
        
        return GoalHierarchy(
            root_goal=root_goal or Goal("fallback", primary_goal),
            all_goals=goals
        )
    
    def _create_fallback_hierarchy(self, primary_goal: str) -> GoalHierarchy:
        """기본 목표 계층 구조 생성"""
        root_goal = Goal(
            goal_id="main_goal",
            description=primary_goal,
            goal_type=GoalType.PRIMARY,
            priority=TaskPriority.HIGH,
            urgency=GoalUrgency.HIGH,
            success_criteria=[f"{primary_goal} 달성"]
        )
        
        return GoalHierarchy(
            root_goal=root_goal,
            all_goals={"main_goal": root_goal}
        )
