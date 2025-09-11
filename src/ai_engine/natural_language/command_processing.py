"""
명령 처리 모듈
사용자의 자연어 명령을 파싱하고 의도를 분류하며 개체명을 추출하는 기능
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from .types import ParsedCommand, IntentType, UrgencyLevel, ExecutionResult
from ..llm_provider import LLMManager
from ..prompt_templates import PromptTemplateManager


class CommandProcessor:
    """명령 처리기 - 자연어 명령 파싱 및 분석"""
    
    def __init__(self, llm_manager: LLMManager, prompt_manager: PromptTemplateManager):
        self.llm_manager = llm_manager
        self.prompt_manager = prompt_manager
    
    async def parse_command(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ParsedCommand:
        """사용자 명령 파싱"""
        try:
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
            messages = [{"role": "user", "content": prompt_text}]
            response = await self.llm_manager.generate_response(
                messages, 
                temperature=0.3  # 낮은 온도로 일관된 분석
            )
            
            # 응답 파싱
            parsed_data = self._extract_json_from_response(response.content)
            
            # Intent 분류 - LLM의 intent_category 사용
            intent_map = {
                "task_management": IntentType.TASK_MANAGEMENT,
                "information_search": IntentType.INFORMATION_SEARCH,
                "web_scraping": IntentType.WEB_SCRAPING,
                "system_control": IntentType.SYSTEM_CONTROL,
                "communication": IntentType.COMMUNICATION,
                "file_management": IntentType.FILE_MANAGEMENT,
                "automation": IntentType.AUTOMATION,
                "query": IntentType.QUERY,
                "unclear": IntentType.UNCLEAR,
            }
            intent = intent_map.get(str(parsed_data.get("intent_category", "")).lower(), IntentType.UNCLEAR)
            
            # ParsedCommand 객체 생성
            return ParsedCommand(
                original_text=user_command,
                intent=intent,
                confidence=parsed_data.get("confidence", 0.5),
                entities=self._extract_entities(user_command, parsed_data),
                # 긴급도 - LLM의 urgency 사용
                urgency={
                    "immediate": UrgencyLevel.IMMEDIATE,
                    "high": UrgencyLevel.HIGH,
                    "medium": UrgencyLevel.MEDIUM,
                    "low": UrgencyLevel.LOW,
                }.get(str(parsed_data.get("urgency", "")).lower(), UrgencyLevel.MEDIUM),
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
    
    def validate_command_confidence(self, parsed_command: ParsedCommand, threshold: float = 0.7) -> bool:
        """명령의 신뢰도 검증"""
        return parsed_command.confidence >= threshold
    
    def should_request_clarification(self, parsed_command: ParsedCommand) -> bool:
        """명확화 요청이 필요한지 판단"""
        return (
            parsed_command.confidence < 0.7 or
            parsed_command.intent == IntentType.UNCLEAR or
            len(parsed_command.clarification_needed) > 0
        )
    
    def extract_intent_keywords(self, text: str) -> Dict[IntentType, float]:
        """키워드 기반 의도 스코어링 (백업용)"""
        intent_keywords = {
            IntentType.TASK_MANAGEMENT: ["할일", "작업", "일정", "스케줄", "계획", "회의", "미팅", "약속"],
            IntentType.INFORMATION_SEARCH: ["검색", "찾아", "알려", "정보", "검색해", "찾아줘"],
            IntentType.WEB_SCRAPING: ["스크래핑", "크롤링", "웹에서", "사이트에서", "페이지에서"],
            IntentType.SYSTEM_CONTROL: ["시스템", "재시작", "종료", "실행", "프로세스"],
            IntentType.COMMUNICATION: ["메시지", "전송", "답장", "연락", "알림"],
            IntentType.FILE_MANAGEMENT: ["파일", "폴더", "저장", "삭제", "이동", "복사"],
            IntentType.AUTOMATION: ["자동화", "자동으로", "정기적으로", "반복"],
            IntentType.QUERY: ["뭐야", "뭔가", "어떻게", "왜", "언제", "어디"]
        }
        
        text_lower = text.lower()
        scores = {}
        
        for intent, keywords in intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                scores[intent] = score / len(keywords)  # 정규화
        
        return scores
