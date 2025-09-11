"""
메모리 및 검색 관련 프롬프트 템플릿
과거 경험 검색, 패턴 분석, 컨텍스트 활용을 담당
"""

from .base import BasePromptManager, PromptTemplate, PromptType


class MemoryPromptManager(BasePromptManager):
    """메모리 및 검색 관련 프롬프트 템플릿 매니저"""
    
    def __init__(self):
        super().__init__()
        self._initialize_templates()
    
    def _initialize_templates(self):
        """메모리 및 검색 관련 템플릿 초기화"""
        
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
        
        # 패턴 분석 템플릿
        self.add_template(PromptTemplate(
            name="pattern_analysis",
            type=PromptType.PATTERN_ANALYSIS,
            template="""수집된 과거 데이터에서 의미있는 패턴을 분석합니다.

[분석 대상 데이터]
$analysis_data

[분석 목적]
$analysis_purpose

[분석 범위]
$analysis_scope

[패턴 분석 요소]
1. 시간적 패턴 (시간대, 요일, 월별)
2. 행동 패턴 (선호도, 성공률, 실패 원인)
3. 컨텍스트 패턴 (상황별, 환경별)
4. 상관관계 및 인과관계

발견된 패턴과 인사이트를 보고하세요:
```json
{
    "temporal_patterns": {
        "time_of_day": "시간대별 패턴",
        "day_of_week": "요일별 패턴",
        "seasonal": "계절별 패턴"
    },
    "behavioral_patterns": {
        "preferences": ["선호 패턴들"],
        "success_factors": ["성공 요인들"],
        "failure_causes": ["실패 원인들"]
    },
    "contextual_patterns": {
        "situational": "상황별 패턴",
        "environmental": "환경별 패턴"
    },
    "insights": ["주요 인사이트들"],
    "recommendations": ["권장사항들"]
}
```""",
            description="과거 데이터에서 행동 패턴을 분석하는 템플릿",
            required_variables=["analysis_data", "analysis_purpose"],
            optional_variables=["analysis_scope"]
        ))
        
        # 컨텍스트 매칭 템플릿
        self.add_template(PromptTemplate(
            name="context_matching",
            type=PromptType.CONTEXT_MATCHING,
            template="""현재 상황과 유사한 과거 컨텍스트를 찾아 매칭합니다.

[현재 컨텍스트]
$current_context

[과거 컨텍스트 데이터]
$historical_contexts

[매칭 기준]
$matching_criteria

[컨텍스트 매칭 과정]
1. 컨텍스트 특징 추출
2. 유사도 계산
3. 관련성 평가
4. 적용 가능성 검토

유사한 과거 컨텍스트와 적용 방안을 제시하세요:
```json
{
    "context_features": {
        "key_attributes": ["주요 특징들"],
        "environmental_factors": ["환경 요인들"],
        "constraints": ["제약 조건들"]
    },
    "similar_contexts": [
        {
            "context_id": "컨텍스트 ID",
            "similarity_score": 0.85,
            "matching_factors": ["일치하는 요인들"],
            "outcome": "당시 결과",
            "applicable_strategies": ["적용 가능한 전략들"]
        }
    ],
    "recommendations": {
        "best_match": "가장 유사한 컨텍스트",
        "adaptation_needed": ["필요한 조정사항"],
        "confidence": 0.9
    }
}
```""",
            description="현재 상황과 유사한 과거 컨텍스트를 매칭하는 템플릿",
            required_variables=["current_context", "historical_contexts"],
            optional_variables=["matching_criteria"]
        ))
        
        # 학습 통합 템플릿
        self.add_template(PromptTemplate(
            name="learning_integration",
            type=PromptType.LEARNING_INTEGRATION,
            template="""새로운 경험을 기존 지식과 통합하여 학습을 강화합니다.

[새로운 경험]
$new_experience

[기존 지식 베이스]
$existing_knowledge

[학습 목표]
$learning_objectives

[통합 과정]
1. 새로운 정보의 검증
2. 기존 지식과의 연결점 파악
3. 충돌하는 정보 해결
4. 지식 구조 업데이트

학습 통합 결과를 제시하세요:
```json
{
    "validation_result": {
        "is_valid": true,
        "confidence": 0.95,
        "verification_method": "검증 방법"
    },
    "knowledge_connections": [
        {
            "existing_concept": "기존 개념",
            "new_insight": "새로운 통찰",
            "connection_type": "연결 유형"
        }
    ],
    "conflicts_resolved": [
        {
            "conflict": "충돌 내용",
            "resolution": "해결 방법",
            "updated_belief": "업데이트된 믿음"
        }
    ],
    "knowledge_updates": {
        "new_concepts": ["새로운 개념들"],
        "modified_concepts": ["수정된 개념들"],
        "deprecated_concepts": ["폐기된 개념들"]
    },
    "learning_impact": "학습 효과 평가"
}
```""",
            description="새로운 경험을 기존 지식과 통합하는 템플릿",
            required_variables=["new_experience", "existing_knowledge"],
            optional_variables=["learning_objectives"]
        ))
        
        # 예측 생성 템플릿
        self.add_template(PromptTemplate(
            name="prediction_generation",
            type=PromptType.PREDICTION_GENERATION,
            template="""과거 패턴을 바탕으로 미래 상황을 예측합니다.

[예측 대상]
$prediction_target

[과거 데이터]
$historical_data

[현재 상황]
$current_situation

[예측 변수]
$prediction_variables

[예측 과정]
1. 관련 패턴 식별
2. 트렌드 분석
3. 영향 요인 평가
4. 시나리오 생성

예측 결과를 제시하세요:
```json
{
    "prediction_summary": "예측 요약",
    "confidence_level": 0.8,
    "time_horizon": "예측 기간",
    "scenarios": [
        {
            "scenario": "시나리오명",
            "probability": 0.6,
            "description": "상세 설명",
            "key_factors": ["주요 요인들"],
            "potential_outcomes": ["가능한 결과들"]
        }
    ],
    "risk_factors": ["위험 요소들"],
    "monitoring_points": ["모니터링 지점들"],
    "adaptation_triggers": ["적응 트리거들"]
}
```""",
            description="과거 패턴을 바탕으로 미래를 예측하는 템플릿",
            required_variables=["prediction_target", "historical_data", "current_situation"],
            optional_variables=["prediction_variables"]
        ))
