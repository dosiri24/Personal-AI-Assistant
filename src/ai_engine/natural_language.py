"""자연어 처리 모듈

Google Gemini 2.5 Pro를 활용한 자연어 이해 및 처리
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from .llm_provider import LLMProviderManager, ChatMessage, LLMResponse
from .prompt_templates import PromptManager, PromptType, ContextAwarePromptManager
from .prompt_optimizer import PromptOptimizer, MetricType
from ..config import Settings


class IntentType(Enum):
    """의도 분류"""
    TASK_MANAGEMENT = "task_management"  # 할일/일정 관리
    INFORMATION_SEARCH = "information_search"  # 정보 검색
    SYSTEM_CONTROL = "system_control"  # 시스템 제어
    COMMUNICATION = "communication"  # 소통/메시지
    FILE_MANAGEMENT = "file_management"  # 파일 관리
    AUTOMATION = "automation"  # 자동화 설정
    QUERY = "query"  # 질문/조회
    UNCLEAR = "unclear"  # 불분명


class UrgencyLevel(Enum):
    """긴급도 수준"""
    IMMEDIATE = "immediate"  # 즉시
    HIGH = "high"  # 높음
    MEDIUM = "medium"  # 보통
    LOW = "low"  # 낮음


@dataclass
class ParsedCommand:
    """파싱된 명령 데이터"""
    original_text: str
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    urgency: UrgencyLevel
    requires_tools: List[str]
    clarification_needed: List[str]
    metadata: Dict[str, Any]


@dataclass 
class TaskPlan:
    """작업 계획 데이터"""
    goal: str
    steps: List[Dict[str, Any]]
    required_tools: List[str]
    estimated_duration: Optional[str]
    difficulty: str
    confidence: float
    dependencies: List[str]


class NaturalLanguageProcessor:
    """자연어 처리기"""
    
    def __init__(self, config: Settings):
        self.config = config
        self.llm_manager = LLMProviderManager(config)
        self.prompt_manager = ContextAwarePromptManager()  # 컨텍스트 인식 프롬프트 매니저 사용
        self.prompt_optimizer = PromptOptimizer()  # A/B 테스트 시스템
        self.initialized = False
        
    async def initialize(self) -> bool:
        """자연어 처리기 초기화"""
        try:
            # LLM 프로바이더 초기화
            if not await self.llm_manager.initialize_providers():
                logger.error("LLM 프로바이더 초기화 실패")
                return False
                
            self.initialized = True
            logger.info("자연어 처리기 초기화 완료")
            return True
            
        except Exception as e:
            logger.error(f"자연어 처리기 초기화 중 오류: {e}")
            return False
            
    async def parse_command(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ParsedCommand:
        """사용자 명령 파싱"""
        try:
            if not self.initialized:
                raise RuntimeError("자연어 처리기가 초기화되지 않았습니다")
                
            # 컨텍스트 준비
            current_time = datetime.now().isoformat()
            memory_context = context.get("memory_context", "관련 기억 없음") if context else "관련 기억 없음"
            
            # 명령 분석 프롬프트 렌더링
            prompt_text = self.prompt_manager.render_template(
                "command_analysis",
                {
                    "user_command": user_command,
                    "current_time": current_time,
                    "user_id": user_id,
                    "platform": "Discord",
                    "memory_context": memory_context
                }
            )
            
            # AI 응답 생성
            messages = [ChatMessage(role="user", content=prompt_text)]
            response = await self.llm_manager.generate_response(
                messages, 
                temperature=0.3  # 낮은 온도로 일관된 분석
            )
            
            # 응답 파싱
            parsed_data = self._extract_json_from_response(response.content)
            
            # ParsedCommand 객체 생성
            return ParsedCommand(
                original_text=user_command,
                intent=self._classify_intent(parsed_data.get("intent", "")),
                confidence=parsed_data.get("confidence", 0.5),
                entities=self._extract_entities(user_command, parsed_data),
                urgency=self._determine_urgency(parsed_data),
                requires_tools=parsed_data.get("required_tools", []),
                clarification_needed=parsed_data.get("clarification_needed", []),
                metadata={
                    "goal": parsed_data.get("goal", ""),
                    "action_plan": parsed_data.get("action_plan", []),
                    "difficulty": parsed_data.get("difficulty", "medium"),
                    "analysis_response": parsed_data
                }
            )
            
        except Exception as e:
            logger.error(f"명령 파싱 중 오류: {e}")
            # 기본 파싱 결과 반환
            return ParsedCommand(
                original_text=user_command,
                intent=IntentType.UNCLEAR,
                confidence=0.1,
                entities={},
                urgency=UrgencyLevel.MEDIUM,
                requires_tools=[],
                clarification_needed=["명령을 이해할 수 없습니다. 더 구체적으로 설명해 주세요."],
                metadata={"error": str(e)}
            )
            
    async def create_task_plan(
        self,
        parsed_command: ParsedCommand,
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """작업 계획 생성"""
        try:
            # 기본 계획에서 상세 계획 생성
            action_plan = parsed_command.metadata.get("action_plan", [])
            
            return TaskPlan(
                goal=parsed_command.metadata.get("goal", parsed_command.original_text),
                steps=action_plan,
                required_tools=parsed_command.requires_tools,
                estimated_duration=self._estimate_duration(parsed_command.metadata.get("difficulty", "medium")),
                difficulty=parsed_command.metadata.get("difficulty", "medium"),
                confidence=parsed_command.confidence,
                dependencies=[]
            )
            
        except Exception as e:
            logger.error(f"작업 계획 생성 중 오류: {e}")
            # 기본 계획 반환
            return TaskPlan(
                goal=parsed_command.original_text,
                steps=[{"step": 1, "action": "사용자 명령 실행", "tool": "manual"}],
                required_tools=parsed_command.requires_tools,
                estimated_duration="알 수 없음",
                difficulty="medium",
                confidence=0.5,
                dependencies=[]
            )
            
    def _estimate_duration(self, difficulty: str) -> str:
        """작업 소요 시간 추정"""
        duration_map = {
            "easy": "1-2분",
            "medium": "3-5분", 
            "hard": "5-10분"
        }
        return duration_map.get(difficulty, "알 수 없음")
            
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
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
            
    def _classify_intent(self, intent_text: str) -> IntentType:
        """의도 분류"""
        intent_lower = intent_text.lower()
        
        if any(word in intent_lower for word in ["일정", "캘린더", "할일", "작업", "리마인더"]):
            return IntentType.TASK_MANAGEMENT
        elif any(word in intent_lower for word in ["검색", "찾기", "정보", "알아보기"]):
            return IntentType.INFORMATION_SEARCH
        elif any(word in intent_lower for word in ["시스템", "설정", "제어", "실행"]):
            return IntentType.SYSTEM_CONTROL
        elif any(word in intent_lower for word in ["메시지", "연락", "전송", "공유"]):
            return IntentType.COMMUNICATION
        elif any(word in intent_lower for word in ["파일", "폴더", "문서", "저장"]):
            return IntentType.FILE_MANAGEMENT
        elif any(word in intent_lower for word in ["자동화", "스케줄", "반복", "설정"]):
            return IntentType.AUTOMATION
        elif any(word in intent_lower for word in ["질문", "궁금", "어떻게", "무엇"]):
            return IntentType.QUERY
        else:
            return IntentType.UNCLEAR
            
    def _determine_urgency(self, parsed_data: Dict[str, Any]) -> UrgencyLevel:
        """긴급도 판단"""
        difficulty = parsed_data.get("difficulty", "medium")
        action_plan = parsed_data.get("action_plan", [])
        
        # 즉시 실행이 필요한 키워드 확인
        urgent_keywords = ["즉시", "지금", "빨리", "긴급", "당장"]
        text = parsed_data.get("intent", "") + " " + parsed_data.get("goal", "")
        
        if any(keyword in text for keyword in urgent_keywords):
            return UrgencyLevel.IMMEDIATE
        elif difficulty == "hard" or len(action_plan) > 3:
            return UrgencyLevel.HIGH
        elif difficulty == "easy":
            return UrgencyLevel.LOW
        else:
            return UrgencyLevel.MEDIUM
            
    def _extract_entities(self, text: str, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """개체명 추출"""
        entities = {}
        
        # 시간 표현 추출
        time_patterns = [
            r'(\d{1,2}:\d{2})',  # 시:분
            r'(\d{1,2}시)',      # N시
            r'(오전|오후)',       # 오전/오후
            r'(내일|모레|다음주|다음달)',  # 상대 시간
            r'(\d{1,2}월\s*\d{1,2}일)',  # 월일
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, text)
            if matches:
                entities["time_expressions"] = matches
                
        # 날짜 표현 추출
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{1,2}/\d{1,2})',    # M/D
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            if matches:
                entities["date_expressions"] = matches
                
        # 파싱된 데이터에서 추가 정보 추출
        if "action_plan" in parsed_data:
            entities["planned_actions"] = parsed_data["action_plan"]
            
        return entities
    
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
            
            # 개인화된 프롬프트 생성
            variables = {
                "current_request": message,
                "user_profile": context.get("user_profile", {}) if context else {},
                "communication_style": "친근한",
                "detail_preference": "중간",
                "response_tone": "도움이 되는",
                "expertise_level": "중급"
            }
            
            prompt_text = self.prompt_manager.get_context_aware_prompt(
                template_name, user_id, variables
            )
            
            # AI 응답 생성
            messages = [ChatMessage(role="user", content=prompt_text)]
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
    
    async def analyze_user_feedback(
        self,
        user_id: str,
        feedback: Dict[str, Any]
    ) -> Dict[str, Any]:
        """사용자 피드백 분석 및 시스템 개선"""
        try:
            # 피드백 분석 프롬프트 사용
            analysis_result = self.prompt_manager.analyze_feedback_and_improve(user_id, feedback)
            
            if analysis_result["status"] == "success":
                # AI로 피드백 분석
                messages = [ChatMessage(role="user", content=analysis_result["analysis_prompt"])]
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
            else:
                return analysis_result
                
        except Exception as e:
            logger.error(f"피드백 분석 중 오류: {e}")
            return {"status": "error", "error": str(e)}
    
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
                if "communication_style" in preference:
                    preference_updates["communication_style"] = preference.split(":")[1].strip()
                elif "detail_level" in preference:
                    preference_updates["detail_preference"] = preference.split(":")[1].strip()
                elif "response_tone" in preference:
                    preference_updates["response_tone"] = preference.split(":")[1].strip()
                    
            if preference_updates:
                self.prompt_manager.update_user_context(
                    user_id, 
                    {"preferences": preference_updates}
                )
                logger.info(f"사용자 선호도 업데이트: {user_id} - {preference_updates}")
                
        except Exception as e:
            logger.error(f"사용자 선호도 업데이트 중 오류: {e}")
    
    async def create_context_aware_task_plan(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """컨텍스트 인식 작업 계획 생성"""
        try:
            # 컨텍스트 인식 계획 수립 프롬프트 사용
            variables = {
                "user_command": user_command,
                "current_time": datetime.now().isoformat(),
                "user_context": context or {},
                "system_capabilities": ["일정관리", "파일조작", "정보검색", "자동화"]
            }
            
            prompt_text = self.prompt_manager.get_context_aware_prompt(
                "context_aware_planning", user_id, variables
            )
            
            # AI 응답 생성
            messages = [ChatMessage(role="user", content=prompt_text)]
            response = await self.llm_manager.generate_response(messages, temperature=0.4)
            
            # 응답 파싱
            plan_data = self._extract_json_from_response(response.content)
            
            return TaskPlan(
                goal=plan_data.get("goal", ""),
                steps=plan_data.get("steps", []),
                required_tools=plan_data.get("required_tools", []),
                estimated_duration=plan_data.get("estimated_duration"),
                difficulty=plan_data.get("difficulty", "medium"),
                confidence=plan_data.get("confidence", 0.5),
                dependencies=plan_data.get("dependencies", [])
            )
            
        except Exception as e:
            logger.error(f"컨텍스트 인식 작업 계획 생성 중 오류: {e}")
            return TaskPlan(
                goal="작업 계획 생성 실패",
                steps=[],
                required_tools=[],
                estimated_duration=None,
                difficulty="unknown",
                confidence=0.0,
                dependencies=[]
            )
    
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
