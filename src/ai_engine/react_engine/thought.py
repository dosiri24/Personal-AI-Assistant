"""
사고 생성 모듈 (ThoughtGenerator)

ReAct 엔진의 사고(Reasoning) 부분을 담당하는 모듈
"""

import asyncio
from typing import Optional, List, Dict, Any
from ..agent_state import AgentScratchpad, AgentContext, ThoughtRecord
from ..llm_provider import LLMProvider, ChatMessage
from ...utils.logger import get_logger

logger = get_logger(__name__)


class ThoughtGenerator:
    """사고 생성기 - ReAct의 Reasoning 부분"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
    
    async def generate_thought(self, scratchpad: AgentScratchpad, context: AgentContext) -> Optional[ThoughtRecord]:
        """현재 상황을 분석하고 다음 행동에 대해 사고"""
        logger.debug(f"사고 과정 생성 시작: 현재단계={len(scratchpad.steps)}")
        
        try:
            # 시스템 프롬프트 생성
            system_prompt = self._create_thinking_system_prompt(context)
            
            # 현재 상황과 히스토리를 포함한 사용자 프롬프트
            user_prompt = self._create_thinking_user_prompt(scratchpad, context)
            
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            # LLM에게 사고 요청
            logger.debug("LLM에게 사고 분석 요청 중...")
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.4,  # 빠른 결정을 위해 온도 감소
                max_tokens=8192  # 사고 과정 토큰 수 증가 (4096→8192)
            )
            
            thought_content = response.content.strip()
            
            # 사고 품질 평가 (간단한 휴리스틱)
            confidence = self._evaluate_thought_quality(thought_content)
            reasoning_depth = self._assess_reasoning_depth(thought_content)
            tags = self._extract_thought_tags(thought_content)
            
            thought = scratchpad.add_thought(
                content=thought_content,
                reasoning_depth=reasoning_depth,
                confidence=confidence,
                tags=tags
            )
            
            logger.debug(f"사고 생성 완료: 길이={len(thought_content)}자, "
                        f"신뢰도={confidence:.2f}, 깊이={reasoning_depth}")
            return thought
            
        except Exception as e:
            logger.error(f"사고 생성 실패: {e}")
            # 기본 사고로 폴백
            thought = scratchpad.add_thought(
                content=f"현재 상황을 분석하고 다음 단계를 계획해야 합니다. (오류: {str(e)})",
                reasoning_depth=1,
                confidence=0.3,
                tags=["fallback", "error"]
            )
            logger.warning("기본 사고로 폴백 처리됨")
            return thought
    
    def _create_thinking_system_prompt(self, context: AgentContext) -> str:
        """사고 시스템 프롬프트 생성"""
        return f'''당신은 지능적인 AI 에이전트입니다. 주어진 목표를 달성하기 위해 체계적으로 사고해야 합니다.

목표: {context.goal}

현재 상황을 면밀히 분석하고 다음 행동을 결정하기 위한 사고 과정을 진행하세요.

사고 지침:
1. 현재까지의 진행 상황을 요약하세요
2. 목표 달성을 위해 아직 필요한 것들을 파악하세요  
3. 다음에 취해야 할 가장 적절한 행동을 결정하세요
4. 잠재적 문제점이나 대안을 고려하세요

간결하고 명확하게 사고 과정을 설명하세요.'''
    
    def _create_thinking_user_prompt(self, scratchpad: AgentScratchpad, context: AgentContext) -> str:
        """사고 사용자 프롬프트 생성"""
        prompt_parts = []
        
        # 이전 단계들 요약 (최근 3개만)
        if scratchpad.steps:
            prompt_parts.append("=== 최근 진행 상황 ===")
            recent_steps = scratchpad.steps[-3:]
            for i, step in enumerate(recent_steps, 1):
                prompt_parts.append(f"{i}. 사고: {step.thought.content[:100]}...")
                if step.action:
                    prompt_parts.append(f"   행동: {step.action.action_type.value} - {step.action.description}")
                if step.observation:
                    prompt_parts.append(f"   결과: {step.observation.content[:100]}...")
                prompt_parts.append("")
        
        # 현재 상황
        prompt_parts.append("=== 현재 상황 ===")
        prompt_parts.append(f"목표: {context.goal}")
        prompt_parts.append(f"진행된 단계: {len(scratchpad.steps)}개")
        
        if context.available_tools:
            prompt_parts.append(f"사용 가능한 도구: {', '.join(context.available_tools)}")
        
        prompt_parts.append("")
        prompt_parts.append("위 정보를 바탕으로 다음 행동을 위한 사고 과정을 진행하세요.")
        
        return "\n".join(prompt_parts)
    
    def _evaluate_thought_quality(self, thought_content: str) -> float:
        """사고 품질 평가 (간단한 휴리스틱)"""
        if not thought_content or len(thought_content) < 10:
            return 0.2
        
        quality_score = 0.5  # 기본 점수
        
        # 길이 평가
        if 50 <= len(thought_content) <= 500:
            quality_score += 0.2
        
        # 키워드 기반 평가
        positive_keywords = ["분석", "계획", "단계", "목표", "필요", "고려", "결정"]
        found_keywords = sum(1 for keyword in positive_keywords if keyword in thought_content)
        quality_score += min(found_keywords * 0.05, 0.3)
        
        return min(quality_score, 1.0)
    
    def _assess_reasoning_depth(self, thought_content: str) -> int:
        """추론 깊이 평가"""
        if not thought_content:
            return 1
        
        depth_indicators = ["왜냐하면", "따라서", "그러므로", "또한", "하지만", "만약"]
        depth = 1 + sum(1 for indicator in depth_indicators if indicator in thought_content)
        
        return min(depth, 5)  # 최대 5단계
    
    def _extract_thought_tags(self, thought_content: str) -> List[str]:
        """사고 내용에서 태그 추출"""
        tags = []
        
        # 키워드 기반 태그 추출
        if "분석" in thought_content:
            tags.append("analysis")
        if "계획" in thought_content:
            tags.append("planning")
        if "문제" in thought_content or "오류" in thought_content:
            tags.append("problem_solving")
        if "도구" in thought_content or "실행" in thought_content:
            tags.append("action_oriented")
        if "완료" in thought_content or "달성" in thought_content:
            tags.append("completion")
            
        return tags if tags else ["general"]
