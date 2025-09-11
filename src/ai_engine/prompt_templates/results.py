"""
결과 처리 및 오류 관리 프롬프트 템플릿
작업 결과 요약, 오류 처리, 사용자 알림을 담당
"""

from .base import BasePromptManager, PromptTemplate, PromptType


class ResultsPromptManager(BasePromptManager):
    """결과 처리 및 오류 관리 프롬프트 템플릿 매니저"""
    
    def __init__(self):
        super().__init__()
        self._initialize_templates()
    
    def _initialize_templates(self):
        """결과 처리 및 오류 관리 템플릿 초기화"""
        
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
        
        # 품질 검증 템플릿
        self.add_template(PromptTemplate(
            name="quality_verification",
            type=PromptType.QUALITY_VERIFICATION,
            template="""실행된 작업의 품질을 검증하고 개선점을 제안합니다.

[작업 결과]
$task_result

[품질 기준]
$quality_criteria

[검증 컨텍스트]
$verification_context

[품질 검증 영역]
1. 정확성 (요구사항 충족도)
2. 완전성 (누락된 요소)
3. 효율성 (성능 및 리소스 사용)
4. 사용자 만족도

품질 검증 결과를 제시하세요:
```json
{
    "overall_quality": "excellent|good|acceptable|poor",
    "quality_score": 0.85,
    "verification_results": {
        "accuracy": {
            "score": 0.9,
            "issues": ["발견된 문제들"],
            "suggestions": ["개선 제안들"]
        },
        "completeness": {
            "score": 0.8,
            "missing_elements": ["누락된 요소들"],
            "optional_additions": ["추가 가능한 요소들"]
        },
        "efficiency": {
            "score": 0.85,
            "performance_metrics": {"key": "value"},
            "optimization_opportunities": ["최적화 기회들"]
        },
        "user_satisfaction": {
            "score": 0.9,
            "feedback_points": ["피드백 포인트들"]
        }
    },
    "improvement_plan": {
        "immediate_fixes": ["즉시 수정 사항들"],
        "enhancement_opportunities": ["개선 기회들"],
        "learning_points": ["학습 포인트들"]
    }
}
```""",
            description="작업 결과의 품질을 검증하고 개선점을 제안하는 템플릿",
            required_variables=["task_result", "quality_criteria"],
            optional_variables=["verification_context"]
        ))
        
        # 성과 보고 템플릿
        self.add_template(PromptTemplate(
            name="performance_report",
            type=PromptType.PERFORMANCE_REPORT,
            template="""일정 기간의 성과를 종합적으로 분석하고 보고합니다.

[보고 기간]
$reporting_period

[수행된 작업들]
$completed_tasks

[성과 메트릭]
$performance_metrics

[사용자 피드백]
$user_feedback

[성과 분석 영역]
1. 작업 완료율 및 품질
2. 응답 시간 및 효율성
3. 사용자 만족도
4. 학습 및 개선 효과

종합 성과 보고서를 작성하세요:
```json
{
    "executive_summary": "성과 요약",
    "period_overview": {
        "start_date": "시작일",
        "end_date": "종료일",
        "total_tasks": 100,
        "completed_tasks": 95,
        "success_rate": 0.95
    },
    "performance_highlights": [
        {
            "metric": "메트릭명",
            "value": "값",
            "trend": "improving|stable|declining",
            "benchmark": "기준값"
        }
    ],
    "achievements": ["주요 성과들"],
    "challenges": ["직면한 도전들"],
    "user_satisfaction": {
        "score": 4.2,
        "feedback_summary": "피드백 요약",
        "improvement_areas": ["개선 영역들"]
    },
    "learning_outcomes": ["학습 성과들"],
    "recommendations": ["향후 권장사항들"]
}
```""",
            description="일정 기간의 성과를 종합 분석하여 보고하는 템플릿",
            required_variables=["reporting_period", "completed_tasks", "performance_metrics"],
            optional_variables=["user_feedback"]
        ))
