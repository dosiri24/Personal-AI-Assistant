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


class TaskStatus(Enum):
    """작업 상태"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class SubTask:
    """세부 작업 단위"""
    name: str
    description: str
    status: TaskStatus = TaskStatus.NOT_STARTED
    required_tools: List[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    result_data: Optional[Dict[str, Any]] = None
    
    def mark_completed(self, result_data: Optional[Dict[str, Any]] = None):
        """작업 완료 처리"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.result_data = result_data
    
    def mark_failed(self):
        """작업 실패 처리"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
    
    def is_completed(self) -> bool:
        """작업 완료 여부"""
        return self.status == TaskStatus.COMPLETED


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
        
        # 🧠 새로운 기능: 누적 추론 이력 저장 (전체 보존)
        self.reasoning_history: List[str] = []  # 이전 모든 추론 과정 저장 (토큰 제한 없음)
        self.full_reasoning_preservation = True  # 전체 추론 이력 보존 플래그
        
        # 🔥 새로운 기능: 작업 상태 추적 시스템
        self.subtasks: List[SubTask] = []  # 세부 작업 목록
        self.completed_operations: set = set()  # 완료된 작업 추적 (중복 방지)
        self.current_phase: str = "planning"  # 현재 진행 단계
        
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
        """현재 스텝에 사고 기록 추가 + 추론 이력 누적 저장"""
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
        
        # 🧠 추론 이력에 추가 (사용자 제안 구현 - 전체 보존)
        self.reasoning_history.append(content)
        
        # 🔥 토큰 제한 제거 - 전체 추론 과정을 다음 추론에 넘겨줌
        # 사용자 요청: "토큰수 아끼지 말고 띵킹 과정 전체를 다음 띵킹에 넘겨주라"
        
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
    
    # 🔥 새로운 기능: 작업 상태 추적 메서드들
    def add_subtask(self, name: str, description: str, required_tools: Optional[List[str]] = None) -> SubTask:
        """세부 작업 추가"""
        subtask = SubTask(
            name=name,
            description=description,
            required_tools=required_tools or []
        )
        self.subtasks.append(subtask)
        return subtask
    
    def mark_subtask_completed(self, task_name: str, result_data: Optional[Dict[str, Any]] = None) -> bool:
        """세부 작업 완료 처리"""
        for task in self.subtasks:
            if task.name == task_name:
                task.mark_completed(result_data)
                self.completed_operations.add(task_name)
                return True
        return False
    
    def check_operation_completed(self, operation_key: str) -> bool:
        """특정 작업이 이미 완료되었는지 확인"""
        return operation_key in self.completed_operations
    
    def add_completed_operation(self, operation_key: str, tool_name: str, params: Dict[str, Any]):
        """완료된 작업 기록 추가 (중복 방지용)"""
        self.completed_operations.add(operation_key)
        # 🔥 세부 정보도 함께 저장
        if not hasattr(self, '_operation_details'):
            self._operation_details = {}
        
        self._operation_details[operation_key] = {
            'tool': tool_name,
            'params': params,
            'completed_at': datetime.now().isoformat()
        }
    
    def should_skip_duplicate_operation(self, tool_name: str, params: Dict[str, Any]) -> tuple[bool, str]:
        """중복 작업인지 확인하고 건너뛸지 결정"""
        # 🔥 작업 키 생성
        operation_key = self._generate_task_key(tool_name, params)
        
        # 🔥 이미 완료된 작업인지 확인
        if self.check_operation_completed(operation_key):
            return True, f"이미 완료된 작업입니다: {operation_key}"
        
        # 🔥 최근에 성공한 동일한 작업이 있는지 확인
        recent_success_count = 0
        for step in self.steps[-3:]:  # 최근 3개 스텝만 확인
            if (step.action and step.action.tool_name == tool_name and 
                step.observation and step.observation.success):
                
                if self._generate_task_key(tool_name, step.action.parameters) == operation_key:
                    recent_success_count += 1
        
        if recent_success_count > 0:
            return True, f"최근에 이미 성공한 작업입니다: {operation_key}"
        
        return False, ""
    
    def update_current_phase(self, phase: str):
        """현재 진행 단계 업데이트"""
        self.current_phase = phase
    
    def get_completion_status(self) -> Dict[str, Any]:
        """전체 작업 완료 상태 반환"""
        completed_tasks = [task for task in self.subtasks if task.is_completed()]
        total_tasks = len(self.subtasks)
        
        return {
            'completed_tasks': len(completed_tasks),
            'total_tasks': total_tasks,
            'completion_percentage': (len(completed_tasks) / total_tasks * 100) if total_tasks > 0 else 0,
            'current_phase': self.current_phase,
            'completed_operations': list(self.completed_operations),
            'pending_tasks': [task.name for task in self.subtasks if not task.is_completed()]
        }
    
    def auto_detect_and_track_tasks(self, goal: str):
        """목표를 분석하여 자동으로 세부 작업 생성"""
        # 🔥 간단한 패턴 매칭으로 작업 분해
        goal_lower = goal.lower()
        
        if "폴더" in goal and "만들" in goal:
            self.add_subtask("folder_creation", "폴더 생성", ["filesystem"])
        
        if "파일" in goal and "찾" in goal:
            self.add_subtask("file_search", "파일 검색", ["smart_file_finder"])
        
        if "이동" in goal or "넣어" in goal:
            self.add_subtask("file_move", "파일 이동", ["filesystem"])
        
        if "복사" in goal:
            self.add_subtask("file_copy", "파일 복사", ["filesystem"])
    
    def update_action_status(self, status: StepStatus, execution_time: Optional[float] = None, 
                           error_message: Optional[str] = None):
        """현재 스텝의 행동 상태 업데이트"""
        if self.steps and self.steps[-1].action:
            action = self.steps[-1].action
            action.status = status
            action.execution_time = execution_time
            action.error_message = error_message
    
    def get_formatted_history(self, include_metadata: bool = False) -> str:
        """LLM이 이해할 수 있는 포맷으로 히스토리 반환 - 도구 사용 이력 강화 + 추론 이력 포함"""
        if not self.steps:
            return f"목표: {self.goal}\n\n아직 수행된 단계가 없습니다."
        
        history = [f"목표: {self.goal}\n"]
        
        # 🧠 새로운 기능: 이전 추론 이력 포함 (사용자 제안 구현)
        reasoning_context = self._get_reasoning_context()
        if reasoning_context:
            history.append("\n🧠 **이전 추론 맥락:**")
            history.append(reasoning_context)
            history.append("")
        
        # 🔥 도구 사용 이력 요약 추가 (중복 방지를 위해)
        tool_usage_summary = self._generate_tool_usage_summary()
        if tool_usage_summary:
            history.append("\n🔍 **이전 도구 사용 이력 요약:**")
            history.append(tool_usage_summary)
            history.append("")
        
        for step in self.steps:
            history.append(f"\n--- 단계 {step.step_number} ---")
            
            if step.thought:
                history.append(f"🤔 사고: {step.thought.content}")
                if include_metadata:
                    history.append(f"   (신뢰도: {step.thought.confidence:.2f}, 깊이: {step.thought.reasoning_depth})")
            
            if step.action:
                if step.action.action_type == ActionType.TOOL_CALL:
                    # 🔧 도구 사용 정보를 더 상세히 표시
                    history.append(f"🔧 행동: {step.action.tool_name} 도구 사용")
                    if step.action.parameters:
                        params_str = json.dumps(step.action.parameters, ensure_ascii=False, indent=2)
                        history.append(f"   파라미터: {params_str}")
                        
                    # 실행 상태 표시
                    if step.action.status != StepStatus.PENDING:
                        status_emoji = {"completed": "✅", "failed": "❌", "executing": "⏳"}.get(step.action.status.value, "❓")
                        history.append(f"   상태: {status_emoji} {step.action.status.value}")
                        
                    if step.action.execution_time:
                        history.append(f"   실행 시간: {step.action.execution_time:.2f}초")
                        
                elif step.action.action_type == ActionType.FINAL_ANSWER:
                    history.append("✅ 최종 답변 준비")
                else:
                    history.append(f"⚡ 행동: {step.action.action_type.value}")
            
            if step.observation:
                status_emoji = "✅" if step.observation.success else "❌"
                # 🔍 결과를 더 명확하게 표시
                result_prefix = "성공" if step.observation.success else "실패"
                history.append(f"{status_emoji} 관찰: 도구 '{step.action.tool_name if step.action else '알 수 없음'}' 실행 결과: {step.observation.content}")
                
                # 실패한 경우 오류 메시지 강조
                if not step.observation.success and step.action and step.action.error_message:
                    history.append(f"   ⚠️ 오류 상세: {step.action.error_message}")
                
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
            history.append(f"- 추론 이력 수: {len(self.reasoning_history)}")
            
        return "\n".join(history)
    
    def _generate_tool_usage_summary(self) -> str:
        """도구 사용 이력 요약 생성 - 🔥 전체 이력을 중복 없이 표시"""
        if not self.steps:
            return ""

        # 🔥 중복 방지를 위한 성공한 태스크 추적
        successful_tasks = {}  # task_key -> task_info
        failed_attempts = []

        for step in self.steps:
            if (step.action and step.action.action_type == ActionType.TOOL_CALL and 
                step.observation is not None):
                
                tool_name = step.action.tool_name or "unknown"
                params = step.action.parameters
                success = step.observation.success
                
                # 🔥 태스크 식별을 위한 키 생성
                task_key = self._generate_task_key(tool_name, params)
                
                if success:
                    # 성공한 태스크는 최신 것으로 업데이트 (중복 제거)
                    summary = self._format_tool_summary(tool_name, params, step.observation)
                    successful_tasks[task_key] = {
                        'summary': summary,
                        'step': step.step_number,
                        'data': getattr(step.observation, 'data', None)
                    }
                else:
                    # 실패한 시도는 모두 기록
                    summary = self._format_tool_summary(tool_name, params, step.observation)
                    failed_attempts.append(f"• {summary} → ❌실패")
                    if step.action.error_message:
                        failed_attempts.append(f"  └─ 오류: {step.action.error_message}")

        # 🔥 결과를 단계 순서대로 정렬하여 표시
        result_lines = []
        
        if successful_tasks:
            sorted_tasks = sorted(successful_tasks.items(), 
                                key=lambda x: x[1]['step'])
            
            for task_key, task_info in sorted_tasks:
                result_lines.append(f"• {task_info['summary']} → ✅성공")
        
        # 실패한 시도들도 추가
        result_lines.extend(failed_attempts)

        if not result_lines:
            return ""

        summary = "\n".join(result_lines)
        
        # 🚨 패턴 감지 및 경고 추가
        warnings = []
        
        # 🔥 중복 작업 감지 개선
        task_counts = {}
        for step in self.steps:
            if step.action and step.action.action_type == ActionType.TOOL_CALL:
                tool_name = step.action.tool_name or "unknown"
                key = self._generate_task_key(tool_name, step.action.parameters)
                task_counts[key] = task_counts.get(key, 0) + 1
        
        repeated_tasks = [key for key, count in task_counts.items() if count > 1]
        if repeated_tasks:
            warnings.append(f"⚠️ 중복 작업 감지: 같은 작업을 {max(task_counts.values())}회 반복했습니다!")
        
        # 연속 실패 감지
        recent_failures = []
        for step in self.steps[-3:]:  # 최근 3개만 체크
            if (step.observation and not step.observation.success and 
                step.action and step.action.action_type == ActionType.TOOL_CALL):
                recent_failures.append(step.action.tool_name)
        
        if len(recent_failures) >= 2:
            warnings.append(f"🚨 연속 실패: {' → '.join(recent_failures)}")
        
        # 🎯 다음 단계 제안 로직 추가
        next_step_suggestions = self._suggest_next_step()
        if next_step_suggestions:
            warnings.append(f"💡 제안: {next_step_suggestions}")
        
        if warnings:
            summary += "\n\n" + "\n".join(warnings)
        
        return summary

    def _generate_task_key(self, tool_name: str, params: Dict[str, Any]) -> str:
        """태스크 식별을 위한 고유 키 생성"""
        if tool_name == 'filesystem':
            action = params.get('action', '')
            path = params.get('path', '')
            return f"filesystem_{action}_{path}"
        elif tool_name == 'smart_file_finder':
            action = params.get('action', '')
            description = params.get('description', '')
            directory = params.get('directory', '')
            return f"smart_file_finder_{action}_{description}_{directory}"
        else:
            # 다른 도구들의 경우 주요 파라미터들로 키 생성
            key_parts = [tool_name]
            for key, value in sorted(params.items()):
                if isinstance(value, (str, int, float, bool)):
                    key_parts.append(f"{key}={value}")
            return "_".join(key_parts)

    def _format_tool_summary(self, tool_name: str, params: Dict[str, Any], observation) -> str:
        """도구 사용 결과를 형식화된 요약으로 변환"""
        if tool_name == 'filesystem':
            action = params.get('action', '알 수 없음')
            path = params.get('path', '경로 없음')
            return f"filesystem({action}) → {path}"
        elif tool_name == 'smart_file_finder':
            action = params.get('action', '알 수 없음')
            description = params.get('description', '설명 없음')
            directory = params.get('directory', '디렉토리 없음')
            
            # 결과에서 중요한 정보 추출
            result_info = ""
            if observation.success and hasattr(observation, 'data') and observation.data:
                data = observation.data
                if 'selected_files' in data:
                    file_count = len(data['selected_files'])
                    result_info = f" → {file_count}개 파일 발견"
                elif 'found_directory' in data:
                    found_dir = data['found_directory']
                    result_info = f" → 디렉토리 발견: {found_dir}"
            
            return f"smart_file_finder({action}) → '{description}' in {directory}{result_info}"
        else:
            # 다른 도구들의 경우
            key_params = []
            for key, value in params.items():
                if isinstance(value, str) and len(value) < 50:
                    key_params.append(f"{key}={value}")
                elif isinstance(value, (int, float, bool)):
                    key_params.append(f"{key}={value}")
            
            params_str = ", ".join(key_params) if key_params else "매개변수 없음"
            return f"{tool_name}({params_str})"

    def _suggest_next_step(self) -> str:
        """현재 진행 상황을 기반으로 다음 단계 제안"""
        if not self.steps:
            return ""
        
        # 최근 성공한 도구 호출들 분석
        successful_actions = []
        found_files = []
        created_folders = []
        
        for step in self.steps:
            if (step.action and step.action.action_type == ActionType.TOOL_CALL and 
                step.observation and step.observation.success):
                
                tool_name = step.action.tool_name or "unknown"
                params = step.action.parameters
                
                if tool_name == 'filesystem' and params.get('action') == 'create_dir':
                    created_folders.append(params.get('path', '알 수 없는 경로'))
                
                elif tool_name == 'smart_file_finder' and hasattr(step.observation, 'data') and step.observation.data:
                    data = step.observation.data
                    if 'selected_files' in data and data['selected_files']:
                        found_files.extend(data['selected_files'])
        
        # 🔥 상황별 제안 개선
        if created_folders and found_files:
            # 폴더도 만들고 파일도 찾았다면 → 파일 이동 제안
            return (f"✅ 폴더 생성({len(created_folders)}개)과 파일 찾기({len(found_files)}개)가 완료되었습니다. "
                   f"🚀 이제 filesystem 도구로 파일 이동(move_file)을 실행하세요!")
        
        elif created_folders and not found_files:
            # 폴더만 만들었다면 → 파일 찾기 제안
            return "✅ 폴더 생성이 완료되었습니다. 🔍 이제 smart_file_finder로 대상 파일들을 찾으세요."
        
        elif found_files and not created_folders:
            # 파일만 찾았다면 → 폴더 생성 제안
            return f"✅ {len(found_files)}개 파일을 찾았습니다. 📁 이제 filesystem으로 목적지 폴더를 생성하세요."
        
        return ""
    
    def _get_reasoning_context(self) -> str:
        """🧠 이전 추론 맥락 반환 (전체 추론 과정 포함)"""
        if not self.reasoning_history:
            return ""
        
        # 🔥 사용자 요청: "토큰수 아끼지 말고 띵킹 과정 전체를 다음 띵킹에 넘겨주라"
        # 전체 추론 이력을 포함 (토큰 제한 없음)
        
        context_lines = []
        for i, reasoning in enumerate(self.reasoning_history, 1):
            # 🔥 요약하지 않고 전체 추론 내용 포함
            context_lines.append(f"{i}. {reasoning}")
        
        return "\n".join(context_lines)
    
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
@dataclass
class AgentContext:
    """에이전트 실행 컨텍스트"""
    user_id: str
    session_id: str
    goal: str
    available_tools: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Any] = field(default_factory=list)  # 대화 히스토리 추가
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
            "conversation_history": self.conversation_history,
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
    
    @classmethod
    def partial_success_result(cls, answer: str, scratchpad: AgentScratchpad,
                              metadata: Optional[Dict[str, Any]] = None) -> 'AgentResult':
        """부분 성공 결과 생성 (무한 루프 등으로 중단되었지만 유용한 정보가 있는 경우)"""
        return cls(
            success=False,  # 완전한 성공은 아니지만
            final_answer=answer,  # 유용한 정보는 반환
            scratchpad=scratchpad,
            error_message=None,
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
