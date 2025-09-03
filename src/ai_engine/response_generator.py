"""
자연어 응답 생성 시스템

AI가 사용자와 자연스럽게 소통하고 작업 진행 상황을 실시간으로 보고하는 시스템입니다.
컨텍스트를 인식하여 개인화된 응답을 생성하고, 작업 결과를 이해하기 쉽게 전달합니다.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from datetime import datetime

from ..utils.logger import get_logger
from .llm_provider import LLMProvider, ChatMessage
from .prompt_templates import PromptManager
from .decision_engine import Decision, DecisionContext


class ResponseType(Enum):
    """응답 유형"""
    ACKNOWLEDGMENT = "acknowledgment"      # 명령 수락 확인
    PROGRESS_UPDATE = "progress_update"    # 진행 상황 업데이트
    CLARIFICATION = "clarification"        # 추가 정보 요청
    SUCCESS_REPORT = "success_report"      # 성공 보고
    ERROR_REPORT = "error_report"          # 오류 보고
    GENERAL_RESPONSE = "general_response"  # 일반 응답


class ResponseTone(Enum):
    """응답 톤"""
    PROFESSIONAL = "professional"    # 전문적
    FRIENDLY = "friendly"           # 친근한
    CASUAL = "casual"               # 캐주얼한
    FORMAL = "formal"               # 격식있는
    ENTHUSIASTIC = "enthusiastic"   # 열정적인


@dataclass
class ResponseContext:
    """응답 생성 컨텍스트"""
    user_id: str
    user_message: str
    response_type: ResponseType
    decision: Optional[Decision] = None
    execution_result: Optional[Dict[str, Any]] = None
    error_info: Optional[Dict[str, Any]] = None
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    current_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """컨텍스트를 딕셔너리로 변환"""
        return {
            "user_id": self.user_id,
            "user_message": self.user_message,
            "response_type": self.response_type.value,
            "decision": self.decision.to_dict() if self.decision else None,
            "execution_result": self.execution_result,
            "error_info": self.error_info,
            "conversation_history": self.conversation_history[-5:],  # 최근 5개만
            "user_preferences": self.user_preferences,
            "current_time": self.current_time.isoformat()
        }


@dataclass
class ResponseOptions:
    """응답 생성 옵션"""
    tone: ResponseTone = ResponseTone.FRIENDLY
    include_reasoning: bool = False
    include_next_steps: bool = True
    max_length: int = 500
    use_emojis: bool = True
    include_technical_details: bool = False


@dataclass
class GeneratedResponse:
    """생성된 응답"""
    content: str
    response_type: ResponseType
    tone: ResponseTone
    estimated_reading_time: int  # 초
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """응답을 딕셔너리로 변환"""
        return {
            "content": self.content,
            "response_type": self.response_type.value,
            "tone": self.tone.value,
            "estimated_reading_time": self.estimated_reading_time,
            "metadata": self.metadata or {}
        }


class ResponseGenerator:
    """
    자연어 응답 생성기
    
    컨텍스트를 인식하여 개인화된 자연어 응답을 생성합니다.
    작업 진행 상황, 결과, 오류 등을 사용자가 이해하기 쉽게 전달합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider, prompt_manager: PromptManager):
        self.llm_provider = llm_provider
        self.prompt_manager = prompt_manager
        self.logger = get_logger("response_generator")
        
        # 사용자별 개인화 설정 저장
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("자연어 응답 생성기 초기화 완료")
    
    async def generate_response(
        self, 
        context: ResponseContext, 
        options: Optional[ResponseOptions] = None
    ) -> GeneratedResponse:
        """
        컨텍스트에 맞는 자연어 응답을 생성합니다
        
        Args:
            context: 응답 생성 컨텍스트
            options: 응답 생성 옵션
            
        Returns:
            생성된 자연어 응답
        """
        if options is None:
            options = ResponseOptions()
            
        try:
            self.logger.info(f"응답 생성 시작: {context.response_type.value}")
            
            # 사용자 선호도 업데이트
            self._update_user_preferences(context.user_id, options)
            
            # 응답 타입별 처리
            if context.response_type == ResponseType.ACKNOWLEDGMENT:
                response = await self._generate_acknowledgment(context, options)
            elif context.response_type == ResponseType.PROGRESS_UPDATE:
                response = await self._generate_progress_update(context, options)
            elif context.response_type == ResponseType.CLARIFICATION:
                response = await self._generate_clarification(context, options)
            elif context.response_type == ResponseType.SUCCESS_REPORT:
                response = await self._generate_success_report(context, options)
            elif context.response_type == ResponseType.ERROR_REPORT:
                response = await self._generate_error_report(context, options)
            else:
                response = await self._generate_general_response(context, options)
            
            self.logger.info(f"응답 생성 완료: {len(response.content)}자")
            return response
            
        except Exception as e:
            self.logger.error(f"응답 생성 중 오류: {e}")
            return self._create_fallback_response(context, options)
    
    async def _generate_acknowledgment(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """명령 수락 확인 응답 생성"""
        prompt = self._create_acknowledgment_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.ACKNOWLEDGMENT,
            tone=options.tone,
            estimated_reading_time=reading_time,
            metadata={
                "decision_confidence": context.decision.confidence_score if context.decision else None,
                "estimated_execution_time": context.decision.estimated_time if context.decision else None
            }
        )
    
    async def _generate_progress_update(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """진행 상황 업데이트 응답 생성"""
        prompt = self._create_progress_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.PROGRESS_UPDATE,
            tone=options.tone,
            estimated_reading_time=reading_time,
            metadata={
                "execution_status": context.execution_result.get("status") if context.execution_result else None,
                "progress_percentage": context.execution_result.get("progress") if context.execution_result else None
            }
        )
    
    async def _generate_clarification(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """추가 정보 요청 응답 생성"""
        prompt = self._create_clarification_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.CLARIFICATION,
            tone=options.tone,
            estimated_reading_time=reading_time,
            metadata={
                "required_info": context.decision.user_input_prompt if context.decision else None,
                "confidence_score": context.decision.confidence_score if context.decision else None
            }
        )
    
    async def _generate_success_report(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """성공 보고 응답 생성"""
        prompt = self._create_success_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.SUCCESS_REPORT,
            tone=options.tone,
            estimated_reading_time=reading_time,
            metadata={
                "execution_time": context.execution_result.get("execution_time") if context.execution_result else None,
                "tools_used": context.decision.selected_tools if context.decision else None
            }
        )
    
    async def _generate_error_report(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """오류 보고 응답 생성"""
        prompt = self._create_error_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.ERROR_REPORT,
            tone=options.tone,
            estimated_reading_time=reading_time,
            metadata={
                "error_type": context.error_info.get("type") if context.error_info else None,
                "recovery_suggestion": context.error_info.get("suggestion") if context.error_info else None
            }
        )
    
    async def _generate_general_response(
        self, 
        context: ResponseContext, 
        options: ResponseOptions
    ) -> GeneratedResponse:
        """일반 응답 생성"""
        prompt = self._create_general_prompt(context, options)
        
        messages = [ChatMessage(role="user", content=prompt)]
        response = await self.llm_provider.generate_response(messages)
        
        content = self._clean_response_content(response.content)
        reading_time = self._estimate_reading_time(content)
        
        return GeneratedResponse(
            content=content,
            response_type=ResponseType.GENERAL_RESPONSE,
            tone=options.tone,
            estimated_reading_time=reading_time
        )
    
    def _create_acknowledgment_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """명령 수락 확인 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        decision_info = ""
        if context.decision:
            decision_info = f"""
**AI 분석 결과:**
- 선택된 도구: {', '.join(context.decision.selected_tools)}
- 신뢰도: {context.decision.confidence_score:.2f}
- 예상 소요시간: {context.decision.estimated_time}초
- 실행 계획: {len(context.decision.execution_plan)}단계
"""
            if options.include_reasoning and context.decision.reasoning:
                decision_info += f"- AI 추론: {context.decision.reasoning[:200]}..."
        
        return f"""사용자가 다음과 같은 명령을 요청했습니다:
"{context.user_message}"

당신은 개인 AI 비서로서 이 명령을 처리하겠다고 확인하는 응답을 {tone_guide} {emoji_guide} 생성해주세요.

{decision_info}

**사용자 정보:**
- 사용자 ID: {context.user_id}
- 현재 시간: {context.current_time.strftime('%Y년 %m월 %d일 %H시 %M분')}

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 명령을 이해했음을 확인
- 작업 시작을 알림
{"- 다음 단계 안내 포함" if options.include_next_steps else ""}
{"- 기술적 세부사항 포함" if options.include_technical_details else "- 기술적 세부사항 제외"}

자연스럽고 도움이 되는 응답을 생성해주세요."""
    
    def _create_progress_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """진행 상황 업데이트 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        progress_info = ""
        if context.execution_result:
            progress_info = f"""
**현재 진행 상황:**
- 상태: {context.execution_result.get('status', '진행 중')}
- 진행률: {context.execution_result.get('progress', 0)}%
- 현재 단계: {context.execution_result.get('current_step', 'N/A')}
- 완료된 작업: {context.execution_result.get('completed_tasks', [])}
"""
        
        return f"""사용자의 명령 "{context.user_message}"을 처리하고 있습니다.

{progress_info}

현재 진행 상황을 사용자에게 {tone_guide} {emoji_guide} 업데이트하는 응답을 생성해주세요.

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 현재 진행 상황 명확히 전달
- 예상 완료 시간 안내
{"- 다음 단계 미리보기" if options.include_next_steps else ""}

사용자가 안심할 수 있도록 명확하고 투명한 업데이트를 제공해주세요."""
    
    def _create_clarification_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """추가 정보 요청 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        required_info = ""
        if context.decision and context.decision.user_input_prompt:
            required_info = f"필요한 정보: {context.decision.user_input_prompt}"
        
        return f"""사용자가 "{context.user_message}"라고 요청했지만, 작업을 완료하기 위해 추가 정보가 필요합니다.

{required_info}

사용자에게 추가 정보를 {tone_guide} {emoji_guide} 요청하는 응답을 생성해주세요.

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 왜 추가 정보가 필요한지 설명
- 구체적으로 어떤 정보가 필요한지 명시
- 예시나 옵션 제공 (가능한 경우)

사용자가 쉽게 답변할 수 있도록 명확하고 도움이 되는 질문을 해주세요."""
    
    def _create_success_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """성공 보고 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        result_info = ""
        if context.execution_result:
            result_info = f"""
**실행 결과:**
- 완료된 작업: {context.execution_result.get('completed_tasks', [])}
- 소요 시간: {context.execution_result.get('execution_time', 'N/A')}초
- 사용된 도구: {context.decision.selected_tools if context.decision else 'N/A'}
- 추가 정보: {context.execution_result.get('additional_info', '')}
"""
        
        return f"""사용자의 명령 "{context.user_message}"을 성공적으로 완료했습니다!

{result_info}

성공 완료를 {tone_guide} {emoji_guide} 보고하는 응답을 생성해주세요.

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 완료된 작업 요약
- 결과물이나 변경사항 설명
{"- 관련 다음 단계 제안" if options.include_next_steps else ""}

사용자가 만족할 수 있는 명확하고 긍정적인 완료 보고를 해주세요."""
    
    def _create_error_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """오류 보고 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        error_info = ""
        if context.error_info:
            error_info = f"""
**오류 정보:**
- 오류 유형: {context.error_info.get('type', 'Unknown')}
- 오류 메시지: {context.error_info.get('message', 'N/A')}
- 발생 단계: {context.error_info.get('step', 'N/A')}
- 해결 방법: {context.error_info.get('suggestion', '다시 시도해주세요')}
"""
        
        return f"""사용자의 명령 "{context.user_message}"을 처리하는 중 문제가 발생했습니다.

{error_info}

오류 상황을 {tone_guide} {emoji_guide} 보고하고 해결 방법을 제안하는 응답을 생성해주세요.

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 문제 상황 명확히 설명
- 사용자가 취할 수 있는 조치 안내
- 대안이나 우회 방법 제시 (가능한 경우)
- 사과와 함께 해결 의지 표현

사용자가 이해하기 쉽고 도움이 되는 오류 보고를 해주세요."""
    
    def _create_general_prompt(self, context: ResponseContext, options: ResponseOptions) -> str:
        """일반 응답 프롬프트 생성"""
        emoji_guide = "이모지를 적절히 사용하여" if options.use_emojis else "이모지 없이"
        tone_guide = self._get_tone_guide(options.tone)
        
        return f"""사용자가 "{context.user_message}"라고 말했습니다.

개인 AI 비서로서 이에 대한 {tone_guide} {emoji_guide} 응답을 생성해주세요.

**사용자 정보:**
- 사용자 ID: {context.user_id}
- 현재 시간: {context.current_time.strftime('%Y년 %m월 %d일 %H시 %M분')}

**응답 요구사항:**
- 길이: {options.max_length}자 이내
- 톤: {tone_guide}
- 사용자의 의도를 파악하고 적절히 응답
- 도움이 되는 정보나 제안 포함

자연스럽고 유용한 응답을 생성해주세요."""
    
    def _get_tone_guide(self, tone: ResponseTone) -> str:
        """톤에 따른 가이드 텍스트 반환"""
        tone_guides = {
            ResponseTone.PROFESSIONAL: "전문적이고 정중하게",
            ResponseTone.FRIENDLY: "친근하고 따뜻하게", 
            ResponseTone.CASUAL: "편안하고 자연스럽게",
            ResponseTone.FORMAL: "격식있고 정중하게",
            ResponseTone.ENTHUSIASTIC: "열정적이고 긍정적으로"
        }
        return tone_guides.get(tone, "친근하고 도움이 되도록")
    
    def _clean_response_content(self, content: str) -> str:
        """응답 내용 정리"""
        # 불필요한 마크다운 제거
        content = content.replace("```", "").replace("**", "").strip()
        
        # 길이 제한 (Discord 메시지 제한)
        if len(content) > 1900:
            content = content[:1900] + "..."
        
        return content
    
    def _estimate_reading_time(self, content: str) -> int:
        """읽기 시간 추정 (초 단위)"""
        # 평균 읽기 속도: 분당 200단어 (한국어는 글자 기준)
        char_count = len(content)
        reading_time = max(1, char_count // 5)  # 5글자당 1초
        return min(reading_time, 60)  # 최대 60초
    
    def _update_user_preferences(self, user_id: str, options: ResponseOptions):
        """사용자 선호도 업데이트"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        
        prefs = self.user_preferences[user_id]
        prefs.update({
            "preferred_tone": options.tone.value,
            "use_emojis": options.use_emojis,
            "include_technical_details": options.include_technical_details,
            "last_updated": datetime.now().isoformat()
        })
    
    def get_user_preferences(self, user_id: str) -> ResponseOptions:
        """사용자 선호도 기반 응답 옵션 반환"""
        prefs = self.user_preferences.get(user_id, {})
        
        return ResponseOptions(
            tone=ResponseTone(prefs.get("preferred_tone", ResponseTone.FRIENDLY.value)),
            use_emojis=prefs.get("use_emojis", True),
            include_technical_details=prefs.get("include_technical_details", False)
        )
    
    def _create_fallback_response(self, context: ResponseContext, options: ResponseOptions) -> GeneratedResponse:
        """오류 발생시 기본 응답 생성"""
        fallback_messages = {
            ResponseType.ACKNOWLEDGMENT: "명령을 확인했습니다. 처리를 시작하겠습니다! 🚀",
            ResponseType.PROGRESS_UPDATE: "작업을 계속 진행하고 있습니다... ⏳",
            ResponseType.CLARIFICATION: "죄송합니다. 추가 정보가 필요합니다. 다시 요청해주시겠어요? 🤔",
            ResponseType.SUCCESS_REPORT: "작업을 완료했습니다! ✅",
            ResponseType.ERROR_REPORT: "죄송합니다. 문제가 발생했습니다. 다시 시도해주세요. ❌",
            ResponseType.GENERAL_RESPONSE: "알겠습니다! 도움이 필요하시면 언제든 말씀해주세요. 😊"
        }
        
        content = fallback_messages.get(context.response_type, "응답을 생성할 수 없습니다.")
        
        return GeneratedResponse(
            content=content,
            response_type=context.response_type,
            tone=options.tone,
            estimated_reading_time=3
        )
