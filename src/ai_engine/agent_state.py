"""
Agent 상태 관리 시스템

에이전틱 AI의 핵심인 Agent Scratchpad와 관련 상태 관리를 담당합니다.
사고-행동-관찰 루프의 중간 과정을 체계적으로 기록하고 관리합니다.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum


class ActionType(Enum):
    """행동 유형"""
    TOOL_CALL = "tool_call"
    THOUGHT = "thought"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"


class StepStatus(Enum):
    """단계 상태"""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ThoughtRecord:
    """사고 기록"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    reasoning_depth: int = 1  # 추론 깊이 (1-5)
    confidence: float = 0.8  # 신뢰도 (0.0-1.0)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "reasoning_depth": self.reasoning_depth,
            "confidence": self.confidence,
            "tags": self.tags
        }


@dataclass
class ActionRecord:
    """행동 기록"""
    action_type: ActionType
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None  # 행동에 대한 설명
    timestamp: datetime = field(default_factory=datetime.now)
    status: StepStatus = StepStatus.PENDING
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type.value,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "execution_time": self.execution_time,
            "error_message": self.error_message
        }


@dataclass
class ObservationRecord:
    """관찰 기록"""
    content: str
    success: bool = True
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    analysis: Optional[str] = None  # AI의 결과 분석
    lessons_learned: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "success": self.success,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "analysis": self.analysis,
            "lessons_learned": self.lessons_learned
        }


@dataclass
class ReActStep:
    """ReAct 루프의 한 스텝 (Thought -> Action -> Observation)"""
    step_number: int
    thought: Optional[ThoughtRecord] = None
    action: Optional[ActionRecord] = None
    observation: Optional[ObservationRecord] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    @property
    def is_complete(self) -> bool:
        """스텝이 완료되었는지 확인"""
        return (self.thought is not None and 
                self.action is not None and 
                self.observation is not None)
    
    @property
    def duration(self) -> Optional[timedelta]:
        """스텝 실행 시간"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "thought": self.thought.to_dict() if self.thought else None,
            "action": self.action.to_dict() if self.action else None,
            "observation": self.observation.to_dict() if self.observation else None,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration.total_seconds() if self.duration else None
        }


class AgentScratchpad:
    """
    에이전트 중간 과정 기록 및 관리
    
    ReAct 루프의 모든 사고-행동-관찰 과정을 체계적으로 기록하고,
    LLM이 다음 사고 과정에서 참조할 수 있는 구조화된 메모리를 제공합니다.
    """
    
    def __init__(self, goal: str, max_steps: int = 10):
        self.goal = goal
        self.max_steps = max_steps
        self.steps: List[ReActStep] = []
        self.current_step_number = 0
        self.start_time = datetime.now()
        self.end_time: Optional[datetime] = None
        self.final_result: Optional[str] = None
        self.success = False
        
        # 메타데이터
        self.total_tool_calls = 0
        self.successful_tool_calls = 0
        self.failed_tool_calls = 0
        self.unique_tools_used = set()
        
    def start_new_step(self) -> ReActStep:
        """새로운 ReAct 스텝 시작"""
        self.current_step_number += 1
        step = ReActStep(step_number=self.current_step_number)
        self.steps.append(step)
        return step
    
    def add_thought(self, content: str, reasoning_depth: int = 1, 
                   confidence: float = 0.8, tags: Optional[List[str]] = None) -> ThoughtRecord:
        """현재 스텝에 사고 기록 추가"""
        if not self.steps:
            self.start_new_step()
        
        current_step = self.steps[-1]
        thought = ThoughtRecord(
            content=content,
            reasoning_depth=reasoning_depth,
            confidence=confidence,
            tags=tags or []
        )
        current_step.thought = thought
        return thought
    
    def add_action(self, action_type: ActionType, tool_name: Optional[str] = None, 
                  parameters: Optional[Dict[str, Any]] = None) -> ActionRecord:
        """현재 스텝에 행동 기록 추가"""
        if not self.steps:
            self.start_new_step()
            
        current_step = self.steps[-1]
        action = ActionRecord(
            action_type=action_type,
            tool_name=tool_name,
            parameters=parameters or {}
        )
        current_step.action = action
        
        # 메타데이터 업데이트
        if action_type == ActionType.TOOL_CALL:
            self.total_tool_calls += 1
            if tool_name:
                self.unique_tools_used.add(tool_name)
                
        return action
    
    def add_observation(self, content: str, success: bool = True, 
                       data: Optional[Dict[str, Any]] = None, analysis: Optional[str] = None,
                       lessons_learned: Optional[List[str]] = None) -> ObservationRecord:
        """현재 스텝에 관찰 기록 추가"""
        if not self.steps:
            self.start_new_step()
            
        current_step = self.steps[-1]
        observation = ObservationRecord(
            content=content,
            success=success,
            data=data,
            analysis=analysis,
            lessons_learned=lessons_learned or []
        )
        current_step.observation = observation
        
        # 스텝 완료 처리
        if current_step.is_complete:
            current_step.end_time = datetime.now()
            
        # 메타데이터 업데이트
        if current_step.action and current_step.action.action_type == ActionType.TOOL_CALL:
            if success:
                self.successful_tool_calls += 1
            else:
                self.failed_tool_calls += 1
                
        return observation
    
    def update_action_status(self, status: StepStatus, execution_time: Optional[float] = None, 
                           error_message: Optional[str] = None):
        """현재 스텝의 행동 상태 업데이트"""
        if self.steps and self.steps[-1].action:
            action = self.steps[-1].action
            action.status = status
            action.execution_time = execution_time
            action.error_message = error_message
    
    def get_formatted_history(self, include_metadata: bool = False) -> str:
        """LLM이 이해할 수 있는 포맷으로 히스토리 반환"""
        if not self.steps:
            return f"목표: {self.goal}\n\n아직 수행된 단계가 없습니다."
        
        history = [f"목표: {self.goal}\n"]
        
        for step in self.steps:
            history.append(f"\n--- 단계 {step.step_number} ---")
            
            if step.thought:
                history.append(f"🤔 사고: {step.thought.content}")
                if include_metadata:
                    history.append(f"   (신뢰도: {step.thought.confidence:.2f}, 깊이: {step.thought.reasoning_depth})")
            
            if step.action:
                if step.action.action_type == ActionType.TOOL_CALL:
                    history.append(f"🔧 행동: {step.action.tool_name} 도구 사용")
                    if step.action.parameters:
                        history.append(f"   파라미터: {json.dumps(step.action.parameters, ensure_ascii=False, indent=2)}")
                elif step.action.action_type == ActionType.FINAL_ANSWER:
                    history.append("✅ 최종 답변 준비")
                else:
                    history.append(f"⚡ 행동: {step.action.action_type.value}")
            
            if step.observation:
                status_emoji = "✅" if step.observation.success else "❌"
                history.append(f"{status_emoji} 관찰: {step.observation.content}")
                
                if step.observation.analysis:
                    history.append(f"   분석: {step.observation.analysis}")
                    
                if step.observation.lessons_learned:
                    history.append("   교훈:")
                    for lesson in step.observation.lessons_learned:
                        history.append(f"   - {lesson}")
        
        if include_metadata:
            history.append(f"\n📊 통계:")
            history.append(f"- 총 단계: {len(self.steps)}")
            history.append(f"- 도구 호출: {self.total_tool_calls} (성공: {self.successful_tool_calls}, 실패: {self.failed_tool_calls})")
            history.append(f"- 사용된 도구: {', '.join(self.unique_tools_used)}")
            
        return "\n".join(history)
    
    def get_latest_context(self, steps_back: int = 3) -> str:
        """최근 N개 스텝의 컨텍스트 반환 (토큰 절약용)"""
        if not self.steps:
            return f"목표: {self.goal}\n\n진행 중..."
        
        recent_steps = self.steps[-steps_back:] if len(self.steps) > steps_back else self.steps
        
        context = [f"목표: {self.goal}\n"]
        
        if len(self.steps) > steps_back:
            context.append(f"... (이전 {len(self.steps) - steps_back}개 단계 생략) ...\n")
        
        for step in recent_steps:
            context.append(f"단계 {step.step_number}:")
            if step.thought:
                context.append(f"  사고: {step.thought.content}")
            if step.action and step.action.action_type == ActionType.TOOL_CALL:
                context.append(f"  행동: {step.action.tool_name} 사용")
            if step.observation:
                status = "성공" if step.observation.success else "실패"
                context.append(f"  결과: {step.observation.content} ({status})")
        
        return "\n".join(context)
    
    def finalize(self, final_result: str, success: bool = True):
        """ReAct 루프 완료 처리"""
        self.end_time = datetime.now()
        self.final_result = final_result
        self.success = success
    
    @property
    def total_duration(self) -> Optional[timedelta]:
        """전체 실행 시간"""
        if self.end_time:
            return self.end_time - self.start_time
        return datetime.now() - self.start_time
    
    @property
    def is_goal_achieved(self) -> bool:
        """목표 달성 여부 (간단한 휴리스틱)"""
        if not self.steps:
            return False
        
        # 최근 스텝에서 성공적인 최종 답변이 있는지 확인
        last_step = self.steps[-1]
        if (last_step.action and 
            last_step.action.action_type == ActionType.FINAL_ANSWER and
            last_step.observation and 
            last_step.observation.success):
            return True
        
        # 또는 성공적인 도구 호출이 연속으로 있는지 확인
        successful_calls = 0
        for step in reversed(self.steps[-3:]):  # 최근 3개 스텝 확인
            if (step.observation and step.observation.success and 
                step.action and step.action.action_type == ActionType.TOOL_CALL):
                successful_calls += 1
            else:
                break
        
        return successful_calls >= 2  # 연속 2개 성공 시 목표 달성으로 간주
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (저장/로드용)"""
        return {
            "goal": self.goal,
            "max_steps": self.max_steps,
            "steps": [step.to_dict() for step in self.steps],
            "current_step_number": self.current_step_number,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "final_result": self.final_result,
            "success": self.success,
            "total_tool_calls": self.total_tool_calls,
            "successful_tool_calls": self.successful_tool_calls,
            "failed_tool_calls": self.failed_tool_calls,
            "unique_tools_used": list(self.unique_tools_used)
        }


@dataclass
class AgentContext:
    """에이전트 실행 컨텍스트"""
    user_id: str
    session_id: str
    goal: str
    available_tools: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    max_iterations: int = 10
    timeout_seconds: int = 300
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "goal": self.goal,
            "available_tools": self.available_tools,
            "user_preferences": self.user_preferences,
            "constraints": self.constraints,
            "max_iterations": self.max_iterations,
            "timeout_seconds": self.timeout_seconds
        }


@dataclass
class AgentResult:
    """에이전트 실행 결과"""
    success: bool
    final_answer: str
    scratchpad: AgentScratchpad
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def success_result(cls, answer: str, scratchpad: AgentScratchpad, 
                      metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """성공 결과 생성"""
        return cls(
            success=True,
            final_answer=answer,
            scratchpad=scratchpad,
            metadata=metadata or {}
        )
    
    @classmethod
    def failure_result(cls, error: str, scratchpad: AgentScratchpad,
                      metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """실패 결과 생성"""
        return cls(
            success=False,
            final_answer="",
            scratchpad=scratchpad,
            error_message=error,
            metadata=metadata or {}
        )
    
    @classmethod
    def max_iterations_result(cls, scratchpad: AgentScratchpad,
                             metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """최대 반복 도달 결과 생성"""
        return cls(
            success=False,
            final_answer="최대 반복 횟수에 도달했습니다. 부분적인 진행 상황을 확인해주세요.",
            scratchpad=scratchpad,
            error_message="MAX_ITERATIONS_REACHED",
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_answer": self.final_answer,
            "error_message": self.error_message,
            "scratchpad": self.scratchpad.to_dict(),
            "metadata": self.metadata
        }
