"""
Specific Memory Types

특정 메모리 타입들을 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .base import BaseMemory, MemoryType, ImportanceLevel, ActionType


@dataclass
class ActionReasoningPair:
    """행동-이유 페어 핵심 구조"""
    action: str                    # 수행한 행동
    reasoning: str                 # 행동을 선택한 이유
    context: str                   # 행동 당시의 상황/맥락
    outcome: str                   # 행동의 결과
    
    # 행동 분석 정보
    action_type: ActionType
    confidence_score: float        # 행동 선택 시 신뢰도
    success_rate: float           # 행동 성공률
    
    # 실행 정보
    tools_used: List[str] = field(default_factory=list)
    execution_time: float = 0.0    # 실행 시간 (초)
    error_messages: List[str] = field(default_factory=list)
    
    # 학습 정보
    learning_points: List[str] = field(default_factory=list)  # 학습한 점들
    improvement_suggestions: List[str] = field(default_factory=list)  # 개선 제안
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "action": self.action,
            "reasoning": self.reasoning,
            "context": self.context,
            "outcome": self.outcome,
            "action_type": self.action_type.value,
            "confidence_score": self.confidence_score,
            "success_rate": self.success_rate,
            "tools_used": self.tools_used,
            "execution_time": self.execution_time,
            "error_messages": self.error_messages,
            "learning_points": self.learning_points,
            "improvement_suggestions": self.improvement_suggestions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionReasoningPair':
        """딕셔너리로부터 객체 생성"""
        return cls(
            action=data["action"],
            reasoning=data["reasoning"],
            context=data["context"],
            outcome=data["outcome"],
            action_type=ActionType(data["action_type"]),
            confidence_score=data["confidence_score"],
            success_rate=data["success_rate"],
            tools_used=data.get("tools_used", []),
            execution_time=data.get("execution_time", 0.0),
            error_messages=data.get("error_messages", []),
            learning_points=data.get("learning_points", []),
            improvement_suggestions=data.get("improvement_suggestions", [])
        )


@dataclass
class ActionMemory(BaseMemory):
    """행동 기록 메모리 - 행동-이유 페어 기반"""
    action_reasoning_pair: Optional[ActionReasoningPair] = None
    
    # 추가 행동 정보
    user_request: str = ""         # 원본 사용자 요청
    ai_interpretation: str = ""    # AI의 요청 해석
    decision_process: str = ""     # 의사결정 과정
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.ACTION
        
        # content 자동 생성
        if self.action_reasoning_pair and not self.content:
            self.content = self._generate_content()
    
    def _generate_content(self) -> str:
        """행동-이유 페어로부터 content 생성"""
        pair = self.action_reasoning_pair
        if not pair:
            return "행동 정보 없음"
            
        return f"""
행동: {pair.action}
이유: {pair.reasoning}
상황: {pair.context}
결과: {pair.outcome}
사용 도구: {', '.join(pair.tools_used)}
성공률: {pair.success_rate:.2%}
        """.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (확장)"""
        base_dict = super().to_dict()
        base_dict.update({
            "action_reasoning_pair": self.action_reasoning_pair.to_dict() if self.action_reasoning_pair else None,
            "user_request": self.user_request,
            "ai_interpretation": self.ai_interpretation,
            "decision_process": self.decision_process
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionMemory':
        """딕셔너리로부터 객체 생성"""
        # BaseMemory 필드들 직접 추출
        action_reasoning_data = data.get("action_reasoning_pair")
        action_reasoning_pair = ActionReasoningPair.from_dict(action_reasoning_data) if action_reasoning_data else None
        
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            importance=ImportanceLevel(data["importance"]),
            action_reasoning_pair=action_reasoning_pair,
            user_request=data.get("user_request", ""),
            ai_interpretation=data.get("ai_interpretation", ""),
            decision_process=data.get("decision_process", "")
        )


@dataclass
class ConversationMemory(BaseMemory):
    """대화 기록 메모리"""
    user_message: str = ""
    ai_response: str = ""
    response_type: str = ""        # 응답 타입 (ACKNOWLEDGMENT, CLARIFICATION 등)
    tone_used: str = ""           # 사용된 톤 (전문적, 친근한 등)
    session_id: str = ""
    conversation_turn: int = 0     # 대화 순서
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.CONVERSATION
        
        # content 자동 생성
        if not self.content and self.user_message and self.ai_response:
            self.content = f"사용자: {self.user_message}\nAI: {self.ai_response}"


@dataclass 
class PreferenceMemory(BaseMemory):
    """사용자 선호도 메모리"""
    preference_category: str = ""  # 카테고리 (tone, schedule, communication 등)
    preference_value: Any = None   # 선호도 값
    confidence: float = 0.0       # 선호도 신뢰도
    learning_source: str = ""     # 학습 출처 (explicit, implicit, inferred)
    frequency: int = 0            # 관찰 빈도
    
    def __post_init__(self):
        super().__post_init__()
        self.memory_type = MemoryType.PREFERENCE
        self.importance = ImportanceLevel.CRITICAL  # 선호도는 기본적으로 중요
