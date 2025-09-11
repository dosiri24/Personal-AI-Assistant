"""
Memory Utilities

메모리 관련 유틸리티 함수들과 ImportanceCalculator를 제공합니다.
"""

from typing import Dict, List, Optional, Any, Tuple
from .base import BaseMemory, MemoryType, ImportanceLevel, ActionType
from .memory import ActionMemory, ConversationMemory, PreferenceMemory, ActionReasoningPair


class ImportanceCalculator:
    """중요도 자동 계산기"""
    
    @staticmethod
    def calculate_importance(memory: BaseMemory, 
                           context: Optional[Dict[str, Any]] = None) -> ImportanceLevel:
        """기억의 중요도를 자동 계산"""
        score = 0.0
        
        # 메모리 타입별 기본 점수
        type_scores = {
            MemoryType.ACTION: 3.0,
            MemoryType.CONVERSATION: 2.0,
            MemoryType.PROJECT: 4.0,
            MemoryType.PREFERENCE: 5.0,
            MemoryType.SYSTEM: 1.0,
            MemoryType.LEARNING: 4.0,
            MemoryType.CONTEXT: 2.0,
            MemoryType.RELATIONSHIP: 3.0
        }
        
        score += type_scores.get(memory.memory_type, 2.0)
        
        # 내용 길이에 따른 가중치
        content_length = len(memory.content)
        if content_length > 500:
            score += 1.0
        elif content_length > 200:
            score += 0.5
        
        # 메타데이터 품질에 따른 가중치
        if memory.metadata:
            score += memory.metadata.confidence * 0.5
            score += memory.metadata.completeness * 0.3
        
        # ActionMemory 특별 처리
        if isinstance(memory, ActionMemory) and memory.action_reasoning_pair:
            pair = memory.action_reasoning_pair
            # 성공률에 따른 가중치
            score += pair.success_rate * 1.0
            # 에러가 있으면 감점
            if pair.error_messages:
                score -= 0.5
            # 학습 포인트가 있으면 가점
            if pair.learning_points:
                score += len(pair.learning_points) * 0.2
        
        # 컨텍스트 정보 활용
        if context:
            # 사용자 명시적 중요도
            if context.get("user_marked_important"):
                score += 2.0
            # 반복 패턴
            if context.get("is_recurring_pattern"):
                score += 1.0
            # 시간 민감성
            if context.get("time_sensitive"):
                score += 0.5
        
        # 점수를 ImportanceLevel로 변환
        if score >= 5.0:
            return ImportanceLevel.CRITICAL
        elif score >= 4.0:
            return ImportanceLevel.HIGH
        elif score >= 3.0:
            return ImportanceLevel.MEDIUM
        elif score >= 2.0:
            return ImportanceLevel.LOW
        else:
            return ImportanceLevel.MINIMAL


# 유틸리티 함수들
def create_action_memory(user_id: str,
                        action: str,
                        reasoning: str,
                        context: str,
                        outcome: str,
                        action_type: ActionType,
                        confidence_score: float,
                        tools_used: Optional[List[str]] = None,
                        user_request: str = "",
                        **kwargs) -> ActionMemory:
    """ActionMemory 생성 헬퍼 함수"""
    
    action_reasoning_pair = ActionReasoningPair(
        action=action,
        reasoning=reasoning,
        context=context,
        outcome=outcome,
        action_type=action_type,
        confidence_score=confidence_score,
        success_rate=1.0 if "성공" in outcome.lower() else 0.5,
        tools_used=tools_used or [],
        **kwargs
    )
    
    memory = ActionMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.ACTION,
        content="",  # 자동 생성됨
        importance=ImportanceLevel.MEDIUM,  # 계산됨
        action_reasoning_pair=action_reasoning_pair,
        user_request=user_request
    )
    
    # 중요도 자동 계산
    memory.importance = ImportanceCalculator.calculate_importance(memory)
    
    return memory


def create_conversation_memory(user_id: str,
                             user_message: str,
                             ai_response: str,
                             response_type: str = "",
                             tone_used: str = "",
                             session_id: str = "") -> ConversationMemory:
    """ConversationMemory 생성 헬퍼 함수"""
    
    memory = ConversationMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.CONVERSATION,
        content="",  # 자동 생성됨
        importance=ImportanceLevel.MEDIUM,  # 계산됨
        user_message=user_message,
        ai_response=ai_response,
        response_type=response_type,
        tone_used=tone_used,
        session_id=session_id
    )
    
    # 중요도 자동 계산
    memory.importance = ImportanceCalculator.calculate_importance(memory)
    
    return memory


def create_preference_memory(user_id: str,
                           category: str,
                           value: Any,
                           confidence: float,
                           learning_source: str = "implicit") -> PreferenceMemory:
    """PreferenceMemory 생성 헬퍼 함수"""
    
    memory = PreferenceMemory(
        id="",  # 자동 생성됨
        user_id=user_id,
        memory_type=MemoryType.PREFERENCE,
        content=f"선호도: {category} = {value}",
        importance=ImportanceLevel.CRITICAL,  # 선호도는 항상 중요
        preference_category=category,
        preference_value=value,
        confidence=confidence,
        learning_source=learning_source
    )
    
    return memory


# 스키마 버전 정보
SCHEMA_VERSION = "2.0"
COMPATIBLE_VERSIONS = ["1.0", "2.0"]


def validate_memory_schema(memory_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """메모리 데이터 스키마 유효성 검증"""
    errors = []
    
    # 필수 필드 확인
    required_fields = ["id", "user_id", "memory_type", "content", "importance"]
    for field in required_fields:
        if field not in memory_data:
            errors.append(f"필수 필드 누락: {field}")
    
    # 타입 확인
    if "memory_type" in memory_data:
        try:
            MemoryType(memory_data["memory_type"])
        except ValueError:
            errors.append(f"잘못된 memory_type: {memory_data['memory_type']}")
    
    if "importance" in memory_data:
        try:
            ImportanceLevel(memory_data["importance"])
        except ValueError:
            errors.append(f"잘못된 importance: {memory_data['importance']}")
    
    return len(errors) == 0, errors
