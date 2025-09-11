"""
명령 분석 및 처리 관련 프롬프트 템플릿
사용자 명령의 의도 파악, 도구 선택, 실행 계획 수립을 담당
"""

from .base import BasePromptManager, PromptTemplate, PromptType


class CommandPromptManager(BasePromptManager):
    """명령 분석 관련 프롬프트 템플릿 매니저"""
    
    def __init__(self):
        super().__init__()
        self._initialize_templates()
    
    def _initialize_templates(self):
        """명령 분석 관련 템플릿 초기화"""
        
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
5. intent_category를 아래 중 하나로 분류하세요:
   ["task_management","information_search","web_scraping","system_control","communication","file_management","automation","query","unclear"]
6. 긴급도(urgency)를 아래 중 하나로 지정하세요: ["immediate","high","medium","low"]

응답 형식:
```json
{
    "intent": "명령의 주요 의도",
    "intent_category": "위 분류 중 하나",
    "goal": "달성하고자 하는 목표",
    "required_tools": ["필요한 도구 목록"],
    "action_plan": [
        {"step": 1, "action": "구체적 행동", "tool": "사용할 도구", "expected_time": "예상 시간"}
    ],
    "difficulty": "easy|medium|hard",
    "confidence": 0.95,
    "urgency": "immediate|high|medium|low",
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

가장 적합한 도구를 선택하고, 필요한 경우 action과 기본 parameters를 제시하세요.

응답 형식(JSON만 출력):
```json
{
  "tool_needed": true,
  "selected_tool": "도구명",
  "action": "액션명(예: create/update/search)",
  "reasoning": "선택 이유",
  "confidence": 0.9,
  "parameters": {"key": "value"}
}
```

도구가 불필요하면 아래 형식을 사용하세요:
```json
{
  "tool_needed": false,
  "reasoning": "이유"
}
```""",
            description="작업에 최적화된 도구를 선택하는 템플릿",
            required_variables=["task_goal", "available_tools"],
            optional_variables=["context"]
        ))
        
        # 실행 계획 템플릿
        self.add_template(PromptTemplate(
            name="execution_planning",
            type=PromptType.TASK_PLANNING,
            template="""선택된 도구와 매개변수를 기반으로 구체적인 실행 계획을 수립합니다.

[작업 목표]
$task_goal

[선택된 도구]
$selected_tool

[매개변수]
$parameters

[컨텍스트]
$context

[실행 계획 요소]
1. 실행 순서와 의존성
2. 예상 실행 시간
3. 오류 처리 방안
4. 결과 검증 방법
5. 롤백 계획

실행 계획을 JSON 형식으로 제시하세요:
```json
{
    "execution_steps": [
        {
            "step": 1,
            "action": "구체적 실행 내용",
            "tool": "사용할 도구",
            "parameters": {"key": "value"},
            "expected_duration": "예상 시간",
            "success_criteria": "성공 판단 기준"
        }
    ],
    "dependencies": ["필요한 선행 조건"],
    "error_handling": "오류 발생시 대응 방안",
    "rollback_plan": "실패시 복구 방안",
    "verification": "결과 검증 방법"
}
```""",
            description="도구 실행을 위한 구체적인 계획을 수립하는 템플릿",
            required_variables=["task_goal", "selected_tool", "parameters"],
            optional_variables=["context"]
        ))
        
        # 명령 재시도 템플릿
        self.add_template(PromptTemplate(
            name="command_retry",
            type=PromptType.ERROR_HANDLING,
            template="""이전 명령 실행이 실패했습니다. 오류를 분석하여 재시도 전략을 수립해야 합니다.

[원본 명령]
$original_command

[실행 오류]
$error_details

[실행 컨텍스트]
$execution_context

[재시도 분석]
1. 오류 원인 식별
2. 수정 가능한 요소 확인
3. 대안 접근 방법 탐색
4. 성공 가능성 평가

재시도 전략을 제시하세요:
```json
{
    "error_analysis": "오류 원인 분석",
    "retry_feasible": true/false,
    "modified_approach": "수정된 접근 방법",
    "alternative_tools": ["대안 도구 목록"],
    "success_probability": 0.8,
    "retry_parameters": {"key": "value"},
    "additional_requirements": ["추가 필요 조건"]
}
```""",
            description="실패한 명령의 재시도 전략을 수립하는 템플릿",
            required_variables=["original_command", "error_details"],
            optional_variables=["execution_context"]
        ))
