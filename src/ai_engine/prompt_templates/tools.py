"""
도구 및 전문 기능 프롬프트 템플릿
일정 관리, 파일 조작, 개인화, 피드백 분석 등 특화된 기능을 담당
"""

from .base import BasePromptManager, PromptTemplate, PromptType


class ToolsPromptManager(BasePromptManager):
    """도구 및 전문 기능 프롬프트 템플릿 매니저"""
    
    def __init__(self):
        super().__init__()
        self._initialize_templates()
    
    def _initialize_templates(self):
        """도구 및 전문 기능 템플릿 초기화"""
        
        # 컨텍스트 인식 작업 계획 템플릿
        self.add_template(PromptTemplate(
            name="context_aware_planning",
            type=PromptType.CONTEXT_AWARE_PLANNING,
            template="""당신은 개인 AI 비서입니다. 사용자 요청과 최근 대화/선호도를 반영하여 최적의 작업 계획을 수립하세요.

[사용자 명령]
$user_command

[사용자 컨텍스트]
$user_context

[시스템 가능 기능]
$system_capabilities

[최근 대화 히스토리]
$conversation_history

[계획 수립 지침]
1. 목표를 한 문장으로 명확히 정의
2. 필요한 도구와 데이터 의존성을 식별
3. 실행 가능한 단계로 분해(각 단계에 도구/예상시간/성공조건 포함)
4. 리스크/불확실성 및 명확화 필요 정보를 표기
5. 전체 난이도와 신뢰도를 추정

응답 형식:
```json
{
  "goal": "달성 목표",
  "steps": [
    {
      "step": 1,
      "action": "구체적 행동",
      "tool": "사용할 도구 또는 manual",
      "expected_time": "예상 시간(분)",
      "success_criteria": "완료 판단 기준"
    }
  ],
  "required_tools": ["필요 도구 목록"],
  "dependencies": ["의존 관계 또는 선행 작업"],
  "estimated_duration": "총 예상 소요 시간",
  "difficulty": "easy|medium|hard",
  "confidence": 0.8,
  "clarification_needed": ["추가로 필요한 정보"]
}
```""",
            description="사용자/대화 컨텍스트를 반영한 작업 계획 수립 템플릿",
            required_variables=["user_command"],
            optional_variables=["user_context", "system_capabilities", "conversation_history"]
        ))

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

⚠️ [중요: 도구 매개변수 정확성] ⚠️
filesystem 도구 사용 시 반드시 정확한 action 값을 사용하세요:
✅ 올바른 값들:
- 파일/폴더 목록 보기: "list"
- 새 폴더 생성: "create_dir"  
- 파일 복사: "copy"
- 파일 이동/이름변경: "move"
- 파일 삭제: "delete"

❌ 잘못된 값들:
- "delete_file" (X) → "delete" (O)
- "remove" (X) → "delete" (O)
- "list_files" (X) → "list" (O)

🏥 [MCP Doctor - 오류 해결 전문가] 🏥
도구 사용 중 오류가 발생하면 mcp_doctor를 호출하세요:
- query_type="error_diagnosis": 오류 진단 및 해결책 제안
- query_type="usage_guide": 도구 사용법 안내
- query_type="parameter_help": 매개변수 도움말
- query_type="tool_recommendation": 작업에 적합한 도구 추천

🚨 오류 발생 시 권장 절차:
1. mcp_doctor로 오류 진단 → 2. 해결책 적용 → 3. 작업 재시도

[작업 계획]
1. system_explorer로 먼저 대상 파일/폴더 위치 정확히 확인
2. 요청 유효성 검증
3. 보안 위험 평가
4. 백업 필요성 판단
5. filesystem 도구에 정확한 action 값으로 실행

응답 형식:
```json
{
    "operation": "create|read|update|delete|move|copy|search",
    "target_files": ["대상 파일들"],
    "safety_checks": ["안전성 검증 항목"],
    "backup_plan": "백업 계획",
    "execution_steps": [
        {
            "step": 1, 
            "action": "구체적 행동", 
            "tool": "사용할 도구명",
            "parameters": {
                "action": "정확한_action_값", 
                "path": "절대경로"
            },
            "validation": "매개변수 유효성 확인"
        }
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
2. 구체적 개선 요청사항
3. 반복되는 문제 패턴
4. 긍정적 피드백 요인

피드백 분석 결과를 제시하세요:
```json
{
    "satisfaction_score": 8.5,
    "feedback_category": "performance|usability|feature_request|bug_report",
    "key_insights": ["주요 인사이트들"],
    "improvement_areas": [
        {
            "area": "개선 영역",
            "priority": "high|medium|low",
            "specific_actions": ["구체적 개선 행동들"],
            "expected_impact": "예상 효과"
        }
    ],
    "positive_aspects": ["긍정적 요소들"],
    "recurring_issues": ["반복되는 문제들"],
    "action_plan": {
        "immediate": ["즉시 실행 항목들"],
        "short_term": ["단기 계획들"],
        "long_term": ["장기 계획들"]
    }
}
```""",
            description="사용자 피드백을 분석하여 개선점을 도출하는 템플릿",
            required_variables=["user_feedback"],
            optional_variables=["task_context", "feedback_history"]
        ))
        
        # 웹 스크래핑 템플릿
        self.add_template(PromptTemplate(
            name="web_scraping",
            type=PromptType.WEB_SCRAPING,
            template="""웹 스크래핑 작업을 계획하고 실행합니다.

[스크래핑 요청]
$scraping_request

[대상 웹사이트 정보]
$website_info

[추출 요구사항]
$extraction_requirements

[제약 조건]
$constraints

[스크래핑 전략]
1. 웹사이트 구조 분석
2. 적절한 추출 방법 선택
3. 반복 작업 최적화
4. 에러 처리 계획

스크래핑 실행 계획을 제시하세요:
```json
{
    "target_urls": ["대상 URL들"],
    "extraction_strategy": "정적|동적|API",
    "data_points": ["추출할 데이터 포인트들"],
    "selectors": {
        "css": ["CSS 선택자들"],
        "xpath": ["XPath 표현식들"]
    },
    "pagination_handling": "페이지네이션 처리 방법",
    "rate_limiting": "요청 제한 설정",
    "error_handling": ["오류 처리 방안들"],
    "output_format": "JSON|CSV|HTML",
    "quality_checks": ["품질 검증 항목들"]
}
```""",
            description="웹 스크래핑 작업을 계획하고 실행하는 템플릿",
            required_variables=["scraping_request", "extraction_requirements"],
            optional_variables=["website_info", "constraints"]
        ))
        
        # 자동화 워크플로우 템플릿
        self.add_template(PromptTemplate(
            name="automation_workflow",
            type=PromptType.AUTOMATION_WORKFLOW,
            template="""반복적인 작업을 자동화하는 워크플로우를 설계합니다.

[자동화 대상 작업]
$target_tasks

[트리거 조건]
$trigger_conditions

[가용 도구 및 API]
$available_tools

[제약 조건]
$constraints

[워크플로우 설계 원칙]
1. 단순성과 신뢰성 우선
2. 오류 복구 메커니즘 포함
3. 모니터링 및 알림 설정
4. 단계별 검증 포인트

자동화 워크플로우를 설계하세요:
```json
{
    "workflow_name": "워크플로우명",
    "trigger_type": "schedule|event|manual",
    "trigger_details": "트리거 상세 설정",
    "workflow_steps": [
        {
            "step": 1,
            "name": "단계명",
            "action": "실행할 작업",
            "tool": "사용할 도구",
            "parameters": {"key": "value"},
            "success_condition": "성공 조건",
            "failure_action": "실패시 대응"
        }
    ],
    "dependencies": ["의존성 관계들"],
    "monitoring": {
        "health_checks": ["상태 점검 항목들"],
        "alerts": ["알림 조건들"],
        "logging": "로깅 설정"
    },
    "rollback_strategy": "롤백 전략",
    "estimated_execution_time": "예상 실행 시간"
}
```""",
            description="반복적인 작업을 자동화하는 워크플로우를 설계하는 템플릿",
            required_variables=["target_tasks", "trigger_conditions"],
            optional_variables=["available_tools", "constraints"]
        ))
