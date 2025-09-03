"""프롬프트 템플릿 시스템

AI 에이전트의 다양한 작업에 대한 프롬프트 템플릿 관리
"""

import json
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from string import Template

from loguru import logger


class PromptType(Enum):
    """프롬프트 템플릿 타입"""
    COMMAND_ANALYSIS = "command_analysis"
    TASK_PLANNING = "task_planning"
    TOOL_SELECTION = "tool_selection"
    MEMORY_SEARCH = "memory_search"
    RESULT_SUMMARY = "result_summary"
    ERROR_HANDLING = "error_handling"
    CLARIFICATION = "clarification"
    SYSTEM_NOTIFICATION = "system_notification"
    
    # 작업별 특화 템플릿
    SCHEDULE_MANAGEMENT = "schedule_management"
    FILE_OPERATIONS = "file_operations"
    WEB_SEARCH = "web_search"
    EMAIL_MANAGEMENT = "email_management"
    NOTE_TAKING = "note_taking"
    AUTOMATION_SETUP = "automation_setup"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_WRITING = "creative_writing"
    
    # 컨텍스트 인식 템플릿
    PERSONALIZED_RESPONSE = "personalized_response"
    CONTEXT_AWARE_PLANNING = "context_aware_planning"
    FEEDBACK_ANALYSIS = "feedback_analysis"
    PREFERENCE_LEARNING = "preference_learning"


@dataclass
class PromptTemplate:
    """프롬프트 템플릿 데이터 클래스"""
    name: str
    type: PromptType
    template: str
    description: str
    required_variables: List[str] = field(default_factory=list)
    optional_variables: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def render(self, variables: Dict[str, Any]) -> str:
        """변수를 사용하여 템플릿 렌더링"""
        try:
            # 필수 변수 확인
            missing_vars = [var for var in self.required_variables if var not in variables]
            if missing_vars:
                raise ValueError(f"필수 변수가 누락되었습니다: {missing_vars}")
                
            # 템플릿 렌더링
            template = Template(self.template)
            return template.safe_substitute(variables)
            
        except Exception as e:
            logger.error(f"템플릿 렌더링 중 오류 ({self.name}): {e}")
            raise


class PromptManager:
    """프롬프트 템플릿 관리자"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates: Dict[str, PromptTemplate] = {}
        self.templates_dir = templates_dir
        self._initialize_default_templates()
        
    def _initialize_default_templates(self):
        """기본 프롬프트 템플릿 초기화"""
        
        # 명령 분석 템플릿
        self.add_template(PromptTemplate(
            name="command_analysis",
            type=PromptType.COMMAND_ANALYSIS,
            template="""당신은 개인 AI 비서입니다. 사용자의 자연어 명령을 분석하여 구체적인 작업 계획을 수립해야 합니다.

[사용자 명령]
$user_command

[과거 유사 작업 기록]
$memory_context

[현재 시스템 상태]
- 시간: $current_time
- 사용자: $user_id
- 플랫폼: $platform

[분석 요청]
1. 명령의 의도와 목표를 파악하세요
2. 필요한 정보나 도구를 식별하세요
3. 단계별 작업 계획을 수립하세요
4. 예상 소요시간과 난이도를 평가하세요

응답 형식:
```json
{
    "intent": "명령의 주요 의도",
    "goal": "달성하고자 하는 목표",
    "required_tools": ["필요한 도구 목록"],
    "action_plan": [
        {"step": 1, "action": "구체적 행동", "tool": "사용할 도구", "expected_time": "예상 시간"}
    ],
    "difficulty": "easy|medium|hard",
    "confidence": 0.95,
    "clarification_needed": ["추가로 필요한 정보"]
}
```""",
            description="사용자 명령을 분석하여 작업 계획을 수립하는 템플릿",
            required_variables=["user_command", "current_time", "user_id", "platform"],
            optional_variables=["memory_context"],
            examples=[
                {
                    "input": "내일 오후 3시에 회의 일정 추가해줘",
                    "output": "회의 일정 추가 작업 계획"
                }
            ]
        ))
        
        # 도구 선택 템플릿
        self.add_template(PromptTemplate(
            name="tool_selection", 
            type=PromptType.TOOL_SELECTION,
            template="""작업 실행을 위한 최적의 도구를 선택해야 합니다.

[작업 목표]
$task_goal

[사용 가능한 도구]
$available_tools

[현재 컨텍스트]
$context

[도구 선택 기준]
1. 작업 목표와의 적합성
2. 도구의 신뢰성과 성공률
3. 실행 속도와 효율성
4. 사용자 경험과 편의성

가장 적합한 도구를 선택하고 사용법을 설명해주세요.

응답 형식:
```json
{
    "selected_tool": "선택된 도구명",
    "reason": "선택 이유",
    "usage_plan": "구체적 사용 계획",
    "parameters": {"매개변수": "값"},
    "fallback_tools": ["대안 도구들"],
    "expected_result": "예상 결과"
}
```""",
            description="작업에 최적화된 도구를 선택하는 템플릿",
            required_variables=["task_goal", "available_tools"],
            optional_variables=["context"]
        ))
        
        # 기억 검색 템플릿
        self.add_template(PromptTemplate(
            name="memory_search",
            type=PromptType.MEMORY_SEARCH,
            template="""과거 행동 패턴을 검색하여 현재 작업에 활용할 정보를 찾아야 합니다.

[현재 작업]
$current_task

[검색 컨텍스트]
$search_context

[기억 검색 전략]
1. 유사한 작업 패턴 검색
2. 성공/실패 사례 분석
3. 사용자 선호도 패턴
4. 시간대/상황별 행동 패턴

관련된 과거 기억을 검색하고 현재 작업에 어떻게 활용할지 설명해주세요.

응답 형식:
```json
{
    "search_keywords": ["검색할 키워드들"],
    "search_filters": {
        "time_range": "시간 범위",
        "task_type": "작업 유형",
        "success_only": true
    },
    "expected_insights": ["얻을 수 있는 인사이트들"],
    "application_plan": "현재 작업에 적용할 방법"
}
```""",
            description="과거 기억을 검색하여 현재 작업에 활용하는 템플릿",
            required_variables=["current_task"],
            optional_variables=["search_context"]
        ))
        
        # 결과 요약 템플릿
        self.add_template(PromptTemplate(
            name="result_summary",
            type=PromptType.RESULT_SUMMARY,
            template="""작업 실행 결과를 사용자가 이해하기 쉽게 요약해야 합니다.

[실행된 작업]
$executed_task

[작업 결과]
$task_result

[실행 과정]
$execution_process

[발생한 문제]
$issues

[사용자 보고 형식]
1. 작업 완료 상태를 명확히 표시
2. 주요 결과를 간결하게 요약
3. 문제가 있었다면 해결 과정 설명
4. 다음 단계 제안 (필요시)

사용자에게 보고할 최종 메시지를 작성해주세요.

응답 형식:
```json
{
    "status": "completed|partial|failed",
    "summary": "작업 결과 요약",
    "details": {
        "what_was_done": "수행된 작업",
        "key_results": ["주요 결과들"],
        "issues_resolved": ["해결된 문제들"]
    },
    "next_steps": ["다음 단계 제안"],
    "user_message": "사용자에게 보낼 최종 메시지"
}
```""",
            description="작업 결과를 사용자에게 보고하는 템플릿",
            required_variables=["executed_task", "task_result"],
            optional_variables=["execution_process", "issues"]
        ))
        
        # 오류 처리 템플릿
        self.add_template(PromptTemplate(
            name="error_handling",
            type=PromptType.ERROR_HANDLING,
            template="""작업 실행 중 오류가 발생했습니다. 문제를 분석하고 해결 방안을 제시해야 합니다.

[발생한 오류]
$error_message

[오류 발생 컨텍스트]
$error_context

[시도했던 작업]
$attempted_task

[시스템 상태]
$system_state

[오류 분석 및 해결 과정]
1. 오류의 근본 원인 분석
2. 가능한 해결 방법들 검토
3. 최적의 해결책 선택
4. 재시도 또는 대안 제시

오류를 분석하고 해결 방안을 제시해주세요.

응답 형식:
```json
{
    "error_type": "오류 유형",
    "root_cause": "근본 원인",
    "severity": "low|medium|high|critical",
    "solution_options": [
        {
            "method": "해결 방법",
            "description": "설명",
            "success_probability": 0.8,
            "side_effects": ["부작용들"]
        }
    ],
    "recommended_action": "권장 조치",
    "prevention_tips": ["재발 방지 방법들"]
}
```""",
            description="오류 발생시 분석하고 해결책을 제시하는 템플릿",
            required_variables=["error_message", "attempted_task"],
            optional_variables=["error_context", "system_state"]
        ))
        
        # 명확화 요청 템플릿
        self.add_template(PromptTemplate(
            name="clarification",
            type=PromptType.CLARIFICATION,
            template="""사용자의 명령이 불분명하거나 추가 정보가 필요합니다. 적절한 질문을 통해 명확화해야 합니다.

[불분명한 명령]
$unclear_command

[누락된 정보]
$missing_information

[컨텍스트]
$context

[명확화 전략]
1. 핵심 의도 파악을 위한 질문
2. 구체적 세부사항 확인
3. 선택지 제시 (가능한 경우)
4. 사용자 친화적 표현 사용

사용자에게 명확화를 요청하는 메시지를 작성해주세요.

응답 형식:
```json
{
    "clarification_type": "intent|details|options|confirmation",
    "questions": [
        {
            "question": "질문 내용",
            "type": "open|choice|yes_no",
            "options": ["선택지들"],
            "priority": "high|medium|low"
        }
    ],
    "user_message": "사용자에게 보낼 친근한 질문",
    "suggested_examples": ["예시들"]
}
```""",
            description="불분명한 명령에 대해 명확화를 요청하는 템플릿",
            required_variables=["unclear_command"],
            optional_variables=["missing_information", "context"]
        ))
        
        # 시스템 알림 처리 템플릿
        self.add_template(PromptTemplate(
            name="system_notification",
            type=PromptType.SYSTEM_NOTIFICATION,
            template="""시스템에서 새로운 알림이 감지되었습니다. 알림의 중요도를 판단하고 적절한 액션을 결정해야 합니다.

[알림 정보]
- 유형: $notification_type
- 내용: $notification_content
- 발신자: $sender
- 시간: $timestamp

[사용자 컨텍스트]
$user_context

[과거 행동 패턴]
$behavior_patterns

[중요도 판단 기준]
1. 긴급성 (시간 민감성)
2. 중요성 (업무/개인 관련도)
3. 발신자 우선순위
4. 사용자 설정 및 선호도

알림을 분석하고 적절한 액션을 제안해주세요.

응답 형식:
```json
{
    "urgency": "immediate|high|medium|low",
    "importance": "critical|high|medium|low",
    "priority_score": 85,
    "recommended_actions": [
        {
            "action": "액션 유형",
            "description": "설명",
            "automated": true,
            "parameters": {}
        }
    ],
    "user_notification": {
        "should_notify": true,
        "message": "사용자에게 보낼 메시지",
        "channel": "discord|email|push"
    },
    "learning_data": {
        "pattern": "행동 패턴",
        "reason": "판단 근거"
    }
}
```""",
            description="시스템 알림을 분석하고 적절한 액션을 결정하는 템플릿",
            required_variables=["notification_type", "notification_content", "timestamp"],
            optional_variables=["sender", "user_context", "behavior_patterns"]
        ))
        
        logger.info(f"기본 프롬프트 템플릿 {len(self.templates)}개 초기화 완료")
        
    def add_template(self, template: PromptTemplate):
        """템플릿 추가"""
        self.templates[template.name] = template
        logger.debug(f"템플릿 추가됨: {template.name}")
        
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """템플릿 가져오기"""
        return self.templates.get(name)
        
    def list_templates(self, template_type: Optional[PromptType] = None) -> List[str]:
        """템플릿 목록 반환"""
        if template_type:
            return [
                name for name, template in self.templates.items()
                if template.type == template_type
            ]
        return list(self.templates.keys())
        
    def render_template(self, name: str, variables: Dict[str, Any]) -> str:
        """템플릿 렌더링"""
        template = self.get_template(name)
        if not template:
            raise ValueError(f"템플릿을 찾을 수 없습니다: {name}")
            
        return template.render(variables)
        
    def save_templates(self, file_path: Path):
        """템플릿을 파일로 저장"""
        try:
            templates_data = {}
            for name, template in self.templates.items():
                templates_data[name] = {
                    "name": template.name,
                    "type": template.type.value,
                    "template": template.template,
                    "description": template.description,
                    "required_variables": template.required_variables,
                    "optional_variables": template.optional_variables,
                    "examples": template.examples,
                    "metadata": template.metadata
                }
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"템플릿 저장 완료: {file_path}")
            
        except Exception as e:
            logger.error(f"템플릿 저장 중 오류: {e}")
            raise
            
    def load_templates(self, file_path: Path):
        """파일에서 템플릿 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                templates_data = json.load(f)
                
            for name, data in templates_data.items():
                template = PromptTemplate(
                    name=data["name"],
                    type=PromptType(data["type"]),
                    template=data["template"],
                    description=data["description"],
                    required_variables=data.get("required_variables", []),
                    optional_variables=data.get("optional_variables", []),
                    examples=data.get("examples", []),
                    metadata=data.get("metadata", {})
                )
                self.templates[name] = template
                
            logger.info(f"템플릿 로드 완료: {len(templates_data)}개")
            
        except Exception as e:
            logger.error(f"템플릿 로드 중 오류: {e}")
            raise


@dataclass
class UserContext:
    """사용자 컨텍스트 정보"""
    user_id: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    recent_tasks: List[str] = field(default_factory=list)
    current_mood: Optional[str] = None
    time_patterns: Dict[str, Any] = field(default_factory=dict)
    feedback_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TaskContext:
    """작업 컨텍스트 정보"""
    task_type: str
    priority: str = "medium"
    deadline: Optional[str] = None
    related_tasks: List[str] = field(default_factory=list)
    required_resources: List[str] = field(default_factory=list)
    complexity_level: str = "medium"
    previous_attempts: List[Dict[str, Any]] = field(default_factory=list)


class ContextAwarePromptManager(PromptManager):
    """컨텍스트 인식 프롬프트 관리자"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        super().__init__(templates_dir)
        self.user_contexts: Dict[str, UserContext] = {}
        self.task_contexts: Dict[str, TaskContext] = {}
        self._initialize_specialized_templates()
        
    def _initialize_specialized_templates(self):
        """특화된 템플릿 초기화"""
        
        # 일정 관리 특화 템플릿
        self.add_template(PromptTemplate(
            name="schedule_management",
            type=PromptType.SCHEDULE_MANAGEMENT,
            template="""당신은 개인 일정 관리 전문 AI입니다. 사용자의 일정 관련 요청을 효율적으로 처리합니다.

[사용자 요청]
$user_request

[현재 일정 컨텍스트]
$schedule_context

[사용자 선호도]
- 선호 시간대: $preferred_time_slots
- 회의 길이 선호: $preferred_meeting_duration
- 알림 선호: $notification_preferences

[일정 분석]
1. 요청된 일정의 우선순위 평가
2. 기존 일정과의 충돌 확인
3. 최적의 시간 슬롯 제안
4. 준비 시간 고려

응답 형식:
```json
{
    "action": "create|update|delete|reschedule",
    "event_details": {
        "title": "일정 제목",
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "duration": "분 단위",
        "location": "장소",
        "participants": ["참석자"],
        "priority": "high|medium|low"
    },
    "conflicts": ["충돌하는 일정들"],
    "alternatives": ["대안 시간들"],
    "preparation_needed": ["필요한 준비사항"],
    "notifications": ["알림 설정"]
}
```""",
            description="일정 관리 작업에 특화된 템플릿",
            required_variables=["user_request"],
            optional_variables=["schedule_context", "preferred_time_slots", "preferred_meeting_duration", "notification_preferences"]
        ))
        
        # 파일 조작 특화 템플릿
        self.add_template(PromptTemplate(
            name="file_operations",
            type=PromptType.FILE_OPERATIONS,
            template="""당신은 파일 관리 전문 AI입니다. 안전하고 효율적인 파일 작업을 수행합니다.

[파일 작업 요청]
$file_request

[현재 파일 시스템 상태]
$filesystem_context

[보안 설정]
- 허용된 디렉토리: $allowed_directories
- 백업 정책: $backup_policy
- 접근 권한: $access_permissions

[작업 계획]
1. 요청 유효성 검증
2. 보안 위험 평가
3. 백업 필요성 판단
4. 단계별 실행 계획

응답 형식:
```json
{
    "operation": "create|read|update|delete|move|copy|search",
    "target_files": ["대상 파일들"],
    "safety_checks": ["안전성 검증 항목"],
    "backup_plan": "백업 계획",
    "execution_steps": [
        {"step": 1, "action": "구체적 행동", "command": "실행 명령어"}
    ],
    "rollback_plan": "실패시 롤백 계획",
    "risk_level": "low|medium|high"
}
```""",
            description="파일 조작 작업에 특화된 템플릿",
            required_variables=["file_request"],
            optional_variables=["filesystem_context", "allowed_directories", "backup_policy", "access_permissions"]
        ))
        
        # 개인화된 응답 템플릿
        self.add_template(PromptTemplate(
            name="personalized_response",
            type=PromptType.PERSONALIZED_RESPONSE,
            template="""사용자의 개인적 특성과 선호도를 반영한 맞춤형 응답을 생성합니다.

[사용자 프로필]
$user_profile

[대화 히스토리]
$conversation_history

[현재 요청]
$current_request

[개인화 요소]
- 의사소통 스타일: $communication_style
- 세부사항 선호도: $detail_preference
- 응답 톤: $response_tone
- 전문성 수준: $expertise_level

[개인화 전략]
1. 사용자의 과거 반응 패턴 분석
2. 선호하는 정보 제공 방식 적용
3. 적절한 전문성 수준으로 설명
4. 개인적 맥락 고려

응답을 $response_tone 톤으로, $detail_preference 수준의 세부사항으로 작성해주세요.""",
            description="사용자 개인화에 특화된 응답 생성 템플릿",
            required_variables=["user_profile", "current_request"],
            optional_variables=["conversation_history", "communication_style", "detail_preference", "response_tone", "expertise_level"]
        ))
        
        # 피드백 분석 템플릿
        self.add_template(PromptTemplate(
            name="feedback_analysis",
            type=PromptType.FEEDBACK_ANALYSIS,
            template="""사용자 피드백을 분석하여 시스템 개선점을 도출합니다.

[수집된 피드백]
$user_feedback

[관련 작업 컨텍스트]
$task_context

[이전 피드백 패턴]
$feedback_history

[분석 관점]
1. 만족도 지표 (1-10 스케일)
2. 개선이 필요한 영역
3. 사용자 기대치와 실제 결과 비교
4. 반복되는 문제점 패턴

응답 형식:
```json
{
    "satisfaction_score": 8.5,
    "positive_aspects": ["잘된 점들"],
    "improvement_areas": ["개선 필요 영역"],
    "specific_issues": ["구체적 문제점"],
    "suggested_improvements": [
        {
            "area": "개선 영역",
            "current_behavior": "현재 동작",
            "suggested_change": "제안 변경사항",
            "priority": "high|medium|low"
        }
    ],
    "user_preferences_learned": ["새로 학습한 선호도"],
    "action_items": ["즉시 적용할 액션 아이템"]
}
```""",
            description="사용자 피드백 분석 및 시스템 개선을 위한 템플릿",
            required_variables=["user_feedback"],
            optional_variables=["task_context", "feedback_history"]
        ))
        
    def get_context_aware_prompt(self, template_name: str, user_id: str, variables: Dict[str, Any]) -> str:
        """컨텍스트를 고려한 프롬프트 생성"""
        try:
            template = self.get_template(template_name)
            if not template:
                raise ValueError(f"템플릿을 찾을 수 없습니다: {template_name}")
                
            # 사용자 컨텍스트 추가
            enhanced_variables = variables.copy()
            if user_id in self.user_contexts:
                user_context = self.user_contexts[user_id]
                enhanced_variables.update({
                    "user_preferences": user_context.preferences,
                    "conversation_history": user_context.conversation_history[-5:],  # 최근 5개
                    "recent_tasks": user_context.recent_tasks[-3:],  # 최근 3개
                    "current_mood": user_context.current_mood or "neutral"
                })
                
            return template.render(enhanced_variables)
            
        except Exception as e:
            logger.error(f"컨텍스트 인식 프롬프트 생성 중 오류: {e}")
            raise
            
    def update_user_context(self, user_id: str, context_update: Dict[str, Any]):
        """사용자 컨텍스트 업데이트"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = UserContext(user_id=user_id)
            
        user_context = self.user_contexts[user_id]
        
        # 선호도 업데이트
        if "preferences" in context_update:
            user_context.preferences.update(context_update["preferences"])
            
        # 대화 히스토리 추가
        if "conversation_turn" in context_update:
            user_context.conversation_history.append(context_update["conversation_turn"])
            # 최대 100개 유지
            if len(user_context.conversation_history) > 100:
                user_context.conversation_history = user_context.conversation_history[-100:]
                
        # 최근 작업 추가
        if "completed_task" in context_update:
            user_context.recent_tasks.append(context_update["completed_task"])
            # 최대 20개 유지
            if len(user_context.recent_tasks) > 20:
                user_context.recent_tasks = user_context.recent_tasks[-20:]
                
        # 피드백 히스토리 추가
        if "feedback" in context_update:
            user_context.feedback_history.append(context_update["feedback"])
            # 최대 50개 유지
            if len(user_context.feedback_history) > 50:
                user_context.feedback_history = user_context.feedback_history[-50:]
                
        logger.debug(f"사용자 컨텍스트 업데이트 완료: {user_id}")
        
    def analyze_feedback_and_improve(self, user_id: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """피드백 분석 및 개선사항 도출"""
        try:
            # 피드백 분석 프롬프트 생성
            variables = {
                "user_feedback": feedback,
                "task_context": feedback.get("task_context", {}),
                "feedback_history": self.user_contexts.get(user_id, UserContext(user_id)).feedback_history
            }
            
            analysis_prompt = self.get_context_aware_prompt("feedback_analysis", user_id, variables)
            
            # 피드백 컨텍스트 업데이트
            self.update_user_context(user_id, {"feedback": feedback})
            
            logger.info(f"피드백 분석 완료: {user_id}")
            return {"analysis_prompt": analysis_prompt, "status": "success"}
            
        except Exception as e:
            logger.error(f"피드백 분석 중 오류: {e}")
            return {"error": str(e), "status": "error"}
            
    def validate_template(self, template: PromptTemplate) -> bool:
        """템플릿 유효성 검사"""
        try:
            # 필수 필드 확인
            if not template.name or not template.template:
                return False
                
            # 템플릿 구문 확인
            Template(template.template)
            
            return True
            
        except Exception as e:
            logger.error(f"템플릿 유효성 검사 실패 ({template.name}): {e}")
            return False
