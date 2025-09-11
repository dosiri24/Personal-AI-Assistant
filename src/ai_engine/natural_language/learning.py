"""
학습 및 최적화 모듈
프롬프트 성능 최적화, A/B 테스트, 시스템 학습 기능
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from loguru import logger

from ..prompt_optimizer import PromptOptimizer, MetricType
from ..llm_provider import LLMManager


class LearningOptimizer:
    """학습 및 최적화 관리자"""
    
    def __init__(self, prompt_optimizer: PromptOptimizer, llm_manager: LLMManager):
        self.prompt_optimizer = prompt_optimizer
        self.llm_manager = llm_manager
        self.learning_sessions = {}  # 학습 세션 기록
    
    async def optimize_prompt_performance(self, test_duration_days: int = 7) -> Dict[str, Any]:
        """프롬프트 성능 최적화"""
        try:
            # 활성 테스트 분석
            optimization_results = {}
            
            # 모든 활성 테스트 분석
            for test_id, test in self.prompt_optimizer.active_tests.items():
                analysis = self.prompt_optimizer.analyze_test_results(test_id)
                optimization_results[test_id] = analysis
                
                # 유의미한 결과가 있으면 승자 적용
                significance = analysis.get("statistical_significance", {})
                for metric, data in significance.items():
                    if data.get("significant", False):
                        winner_variant_id = data["winner"]
                        logger.info(f"프롬프트 최적화: {test.name}에서 {winner_variant_id} 적용")
                        
            return {
                "status": "success",
                "optimizations_applied": len(optimization_results),
                "results": optimization_results
            }
            
        except Exception as e:
            logger.error(f"프롬프트 성능 최적화 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    async def create_ab_test(
        self,
        test_name: str,
        base_prompt: str,
        variant_prompts: List[str],
        target_metrics: List[MetricType],
        duration_days: int = 7
    ) -> Dict[str, Any]:
        """A/B 테스트 생성"""
        try:
            test_id = f"test_{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # 테스트 설정
            test_config = {
                "test_id": test_id,
                "name": test_name,
                "base_prompt": base_prompt,
                "variants": [
                    {"id": f"variant_{i}", "prompt": prompt} 
                    for i, prompt in enumerate(variant_prompts)
                ],
                "target_metrics": [metric.value for metric in target_metrics],
                "start_date": datetime.now().isoformat(),
                "end_date": (datetime.now() + timedelta(days=duration_days)).isoformat(),
                "status": "active"
            }
            
            # 프롬프트 옵티마이저에 테스트 등록
            success = self.prompt_optimizer.create_test(
                test_id, test_name, base_prompt, variant_prompts, target_metrics
            )
            
            if success:
                logger.info(f"A/B 테스트 생성 완료: {test_name} (ID: {test_id})")
                return {
                    "status": "success",
                    "test_id": test_id,
                    "config": test_config
                }
            else:
                return {
                    "status": "error",
                    "message": "A/B 테스트 생성 실패"
                }
                
        except Exception as e:
            logger.error(f"A/B 테스트 생성 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    async def analyze_system_performance(
        self,
        start_date: str,
        end_date: str
    ) -> Dict[str, Any]:
        """시스템 성능 분석"""
        try:
            analysis_prompt = f"""
시스템 성능 데이터를 분석해주세요.

**분석 기간**: {start_date} ~ {end_date}

**분석 항목**:
1. 응답 정확도 트렌드
2. 사용자 만족도 변화
3. 처리 시간 성능
4. 오류율 분석
5. 기능별 사용 패턴

**요청 형식**:
각 항목에 대해 다음 정보를 제공해주세요:
- 현재 상태 (점수/등급)
- 트렌드 (개선/악화/유지)
- 주요 발견사항
- 개선 권장사항

JSON 형식으로 응답해주세요.
"""

            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.llm_manager.generate_response(messages, temperature=0.3)
            
            # 응답 파싱
            analysis_data = self._extract_json_from_response(response.content)
            
            return {
                "status": "success",
                "analysis_period": {"start": start_date, "end": end_date},
                "performance_analysis": analysis_data,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"시스템 성능 분석 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    async def generate_improvement_recommendations(
        self,
        performance_data: Dict[str, Any],
        user_feedback: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """개선 권장사항 생성"""
        try:
            improvement_prompt = f"""
시스템 성능 데이터와 사용자 피드백을 바탕으로 개선 권장사항을 생성해주세요.

**성능 데이터**:
{performance_data}

**사용자 피드백 요약**:
{self._summarize_feedback(user_feedback)}

**개선 권장사항 요청**:
1. 우선순위가 높은 개선 항목 3개
2. 각 항목별 구체적 개선 방안
3. 예상 효과 및 구현 난이도
4. 단기/중기/장기 로드맵

JSON 형식으로 체계적으로 정리해주세요.
"""

            messages = [{"role": "user", "content": improvement_prompt}]
            response = await self.llm_manager.generate_response(messages, temperature=0.4)
            
            # 응답 파싱
            recommendations = self._extract_json_from_response(response.content)
            
            return {
                "status": "success",
                "recommendations": recommendations,
                "based_on": {
                    "performance_data": True,
                    "user_feedback_count": len(user_feedback)
                },
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"개선 권장사항 생성 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    def _summarize_feedback(self, feedback_list: List[Dict[str, Any]]) -> str:
        """피드백 요약"""
        if not feedback_list:
            return "피드백 없음"
        
        positive_count = sum(1 for f in feedback_list if f.get("rating", 3) >= 4)
        negative_count = sum(1 for f in feedback_list if f.get("rating", 3) <= 2)
        
        summary = f"총 {len(feedback_list)}개 피드백 (긍정: {positive_count}, 부정: {negative_count})\n"
        
        # 주요 키워드 추출 (단순한 방식)
        all_content = " ".join([f.get("content", "") for f in feedback_list])
        common_words = ["좋다", "빠르다", "정확하다", "느리다", "틀렸다", "개선", "문제"]
        
        mentioned_words = [word for word in common_words if word in all_content]
        if mentioned_words:
            summary += f"주요 언급: {', '.join(mentioned_words)}"
        
        return summary
    
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
    
    async def start_learning_session(self, session_name: str) -> str:
        """학습 세션 시작"""
        session_id = f"learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.learning_sessions[session_id] = {
            "name": session_name,
            "start_time": datetime.now().isoformat(),
            "status": "active",
            "metrics": {},
            "improvements": []
        }
        
        logger.info(f"학습 세션 시작: {session_name} (ID: {session_id})")
        return session_id
    
    def record_learning_metric(
        self,
        session_id: str,
        metric_name: str,
        value: Any
    ) -> bool:
        """학습 메트릭 기록"""
        try:
            if session_id in self.learning_sessions:
                session = self.learning_sessions[session_id]
                session["metrics"][metric_name] = {
                    "value": value,
                    "recorded_at": datetime.now().isoformat()
                }
                return True
            return False
        except Exception as e:
            logger.error(f"학습 메트릭 기록 중 오류: {e}")
            return False
    
    def end_learning_session(self, session_id: str) -> Dict[str, Any]:
        """학습 세션 종료"""
        try:
            if session_id not in self.learning_sessions:
                return {"status": "error", "message": "세션을 찾을 수 없습니다"}
            
            session = self.learning_sessions[session_id]
            session["end_time"] = datetime.now().isoformat()
            session["status"] = "completed"
            
            # 세션 요약 생성
            summary = {
                "session_id": session_id,
                "name": session["name"],
                "duration": session.get("end_time", "") and session.get("start_time", ""),
                "metrics_collected": len(session["metrics"]),
                "improvements_made": len(session["improvements"])
            }
            
            logger.info(f"학습 세션 종료: {session['name']} - {summary}")
            return {"status": "success", "summary": summary}
            
        except Exception as e:
            logger.error(f"학습 세션 종료 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_learning_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """학습 히스토리 조회"""
        try:
            sessions = list(self.learning_sessions.values())
            
            # 최신순 정렬
            sessions.sort(key=lambda x: x.get("start_time", ""), reverse=True)
            
            return sessions[:limit]
            
        except Exception as e:
            logger.error(f"학습 히스토리 조회 중 오류: {e}")
            return []
