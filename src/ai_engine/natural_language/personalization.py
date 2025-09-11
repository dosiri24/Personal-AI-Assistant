"""
개인화 모듈
사용자별 맞춤형 응답 생성 및 개인 컨텍스트 관리
"""

from typing import Dict, List, Optional, Any
from loguru import logger

from .types import PersonalizationContext, FeedbackData
from ..llm_provider import LLMManager
from ..prompt_templates import PromptTemplateManager
from ..prompt_optimizer import PromptOptimizer, MetricType


class PersonalizationManager:
    """개인화 관리자"""
    
    def __init__(self, llm_manager: LLMManager, prompt_manager: PromptTemplateManager, prompt_optimizer: PromptOptimizer):
        self.llm_manager = llm_manager
        self.prompt_manager = prompt_manager
        self.prompt_optimizer = prompt_optimizer
        self.user_contexts: Dict[str, PersonalizationContext] = {}
    
    async def generate_personalized_response(
        self,
        user_id: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """개인화된 응답 생성"""
        try:
            # A/B 테스트 변형 선택
            test_id = "personalized_response_v1"  # 실제로는 활성 테스트에서 선택
            variant = self.prompt_optimizer.get_variant_for_user(test_id, user_id)
            
            # 템플릿 선택 (A/B 테스트 또는 기본)
            template_name = variant.name if variant else "personalized_response"
            
            # 사용자 컨텍스트 가져오기
            user_context = self.get_user_context(user_id)
            
            # 개인화된 프롬프트 생성
            variables = {
                "current_request": message,
                "user_profile": context.get("user_profile", {}) if context else {},
                "communication_style": user_context.communication_style,
                "detail_preference": user_context.detail_preference,
                "response_tone": user_context.response_tone,
                "expertise_level": user_context.expertise_level
            }
            
            prompt_text = self.prompt_manager.render_template(template_name, variables)
            
            # AI 응답 생성
            messages = [{"role": "user", "content": prompt_text}]
            response = await self.llm_manager.generate_response(messages, temperature=0.7)
            
            # A/B 테스트 결과 기록 (변형이 있는 경우)
            if variant:
                metrics = {
                    MetricType.USER_SATISFACTION: 0.8,  # 실제로는 사용자 피드백에서 계산
                    MetricType.RESPONSE_TIME: 1.5,  # 응답 시간
                }
                self.prompt_optimizer.record_result(
                    test_id, user_id, variant.id, metrics, context
                )
            
            return response.content
            
        except Exception as e:
            logger.error(f"개인화된 응답 생성 중 오류: {e}")
            return "죄송합니다. 응답을 생성하는 중에 문제가 발생했습니다."
    
    def get_user_context(self, user_id: str) -> PersonalizationContext:
        """사용자 컨텍스트 가져오기"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = PersonalizationContext(user_id=user_id)
        return self.user_contexts[user_id]
    
    def update_user_context(self, user_id: str, updates: Dict[str, Any]) -> None:
        """사용자 컨텍스트 업데이트"""
        user_context = self.get_user_context(user_id)
        
        # 직접 속성 업데이트
        for key, value in updates.items():
            if hasattr(user_context, key):
                setattr(user_context, key, value)
        
        # preferences 딕셔너리 업데이트
        if "preferences" in updates:
            user_context.preferences.update(updates["preferences"])
        
        logger.info(f"사용자 컨텍스트 업데이트: {user_id} - {updates}")
    
    async def analyze_user_feedback(
        self,
        user_id: str,
        feedback: FeedbackData
    ) -> Dict[str, Any]:
        """사용자 피드백 분석 및 시스템 개선"""
        try:
            # 피드백 분석 프롬프트 생성
            analysis_prompt = self._create_feedback_analysis_prompt(feedback)
            
            # AI로 피드백 분석
            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.llm_manager.generate_response(messages, temperature=0.3)
            
            # 분석 결과 파싱
            analysis_data = self._extract_json_from_response(response.content)
            
            # 사용자 컨텍스트 업데이트
            self._update_user_preferences_from_feedback(user_id, analysis_data)
            
            return {
                "status": "success",
                "analysis": analysis_data,
                "improvements_applied": True
            }
                
        except Exception as e:
            logger.error(f"피드백 분석 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    def _create_feedback_analysis_prompt(self, feedback: FeedbackData) -> str:
        """피드백 분석용 프롬프트 생성"""
        return f"""
사용자 피드백을 분석하여 개인화 설정을 개선해주세요.

**피드백 정보:**
- 사용자 ID: {feedback.user_id}
- 피드백 유형: {feedback.feedback_type}
- 내용: {feedback.content}
- 평점: {feedback.rating}/5.0 (있는 경우)

**분석 요청:**
1. 피드백에서 드러나는 사용자 선호도
2. 개선 가능한 개인화 설정
3. 커뮤니케이션 스타일 조정 방향
4. 응답 품질 향상 방안

**응답 형식:**
```json
{{
    "satisfaction_score": 4.2,
    "feedback_category": "communication_style|response_detail|functionality|other",
    "user_preferences_learned": [
        "communication_style: 더 간결한 응답 선호",
        "detail_level: 기술적 세부사항 원함",
        "response_tone: 전문적인 톤 선호"
    ],
    "improvement_suggestions": [
        "응답 길이를 20% 단축",
        "기술 용어 사용 늘리기",
        "예시보다는 핵심 정보 위주"
    ],
    "priority": "high|medium|low"
}}
```
"""
    
    def _update_user_preferences_from_feedback(
        self,
        user_id: str,
        analysis_data: Dict[str, Any]
    ):
        """피드백 분석 결과로부터 사용자 선호도 업데이트"""
        try:
            preferences_learned = analysis_data.get("user_preferences_learned", [])
            
            # 새로운 선호도를 컨텍스트에 반영
            preference_updates = {}
            for preference in preferences_learned:
                if ":" in preference:
                    key, value = preference.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if "communication_style" in key:
                        preference_updates["communication_style"] = value
                    elif "detail_level" in key or "detail_preference" in key:
                        preference_updates["detail_preference"] = value
                    elif "response_tone" in key:
                        preference_updates["response_tone"] = value
                    elif "expertise_level" in key:
                        preference_updates["expertise_level"] = value
                    
            if preference_updates:
                self.update_user_context(user_id, {"preferences": preference_updates})
                
        except Exception as e:
            logger.error(f"사용자 선호도 업데이트 중 오류: {e}")
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
        import re
        import json
        
        try:
            # JSON 코드 블록 찾기
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
                
            # 중괄호로 둘러싸인 JSON 찾기
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
                
            # JSON 찾기 실패시 빈 딕셔너리 반환
            logger.warning("응답에서 JSON을 찾을 수 없습니다")
            return {}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}")
            return {}
    
    def get_user_preferences_summary(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 요약 반환"""
        user_context = self.get_user_context(user_id)
        
        return {
            "user_id": user_id,
            "communication_style": user_context.communication_style,
            "detail_preference": user_context.detail_preference,
            "response_tone": user_context.response_tone,
            "expertise_level": user_context.expertise_level,
            "custom_preferences": user_context.preferences,
            "last_updated": "최근 업데이트 시간 정보 없음"  # 실제로는 타임스탬프 추가
        }
    
    def export_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """사용자 선호도 내보내기 (백업/이관용)"""
        return {
            "user_id": user_id,
            "context": self.user_contexts.get(user_id).__dict__ if user_id in self.user_contexts else None
        }
    
    def import_user_preferences(self, preferences_data: Dict[str, Any]) -> bool:
        """사용자 선호도 가져오기 (복원용)"""
        try:
            user_id = preferences_data["user_id"]
            context_data = preferences_data["context"]
            
            if context_data:
                self.user_contexts[user_id] = PersonalizationContext(**context_data)
                logger.info(f"사용자 선호도 복원 완료: {user_id}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"사용자 선호도 복원 중 오류: {e}")
            return False
    
    def clear_user_context(self, user_id: str) -> bool:
        """사용자 컨텍스트 초기화"""
        try:
            if user_id in self.user_contexts:
                del self.user_contexts[user_id]
                logger.info(f"사용자 컨텍스트 초기화 완료: {user_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"사용자 컨텍스트 초기화 중 오류: {e}")
            return False
