"""
AI 의사결정 엔진 - 에이전틱 방식

LLM이 직접 자연어를 이해하고 도구를 선택하여 실행하는 진정한 에이전트입니다.
구시대적인 키워드 매칭이나 작업 유형 분류 없이 순수하게 AI가 판단합니다.
"""

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from datetime import datetime

from ..utils.logger import get_logger
from .llm_provider import LLMProvider, LLMResponse, ChatMessage
from .prompt_templates import PromptManager


class ConfidenceLevel(Enum):
    """신뢰도 레벨"""
    VERY_HIGH = "very_high"      # 0.9 이상
    HIGH = "high"                # 0.7 - 0.9
    MEDIUM = "medium"            # 0.5 - 0.7
    LOW = "low"                  # 0.3 - 0.5
    VERY_LOW = "very_low"        # 0.3 미만


@dataclass
class Tool:
    """도구 정보"""
    name: str
    description: str
    capabilities: List[str]
    required_params: List[str]
    optional_params: List[str] = field(default_factory=list)
    confidence_threshold: float = 0.7
    execution_time_estimate: int = 30  # 초
    
    def to_dict(self) -> Dict[str, Any]:
        """도구 정보를 딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
            "confidence_threshold": self.confidence_threshold,
            "execution_time_estimate": self.execution_time_estimate
        }


@dataclass
class Decision:
    """의사결정 결과"""
    selected_tools: List[str]
    execution_plan: List[Dict[str, Any]]
    confidence_score: float
    confidence_level: ConfidenceLevel
    reasoning: str
    estimated_time: int
    requires_user_input: bool = False
    user_input_prompt: Optional[str] = None
    fallback_plan: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """의사결정 결과를 딕셔너리로 변환"""
        return {
            "selected_tools": self.selected_tools,
            "execution_plan": self.execution_plan,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level.value,
            "reasoning": self.reasoning,
            "estimated_time": self.estimated_time,
            "requires_user_input": self.requires_user_input,
            "user_input_prompt": self.user_input_prompt,
            "fallback_plan": self.fallback_plan or []
        }


@dataclass
class DecisionContext:
    """의사결정 컨텍스트"""
    user_message: str
    user_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    available_tools: List[Tool] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    current_time: datetime = field(default_factory=datetime.now)
    system_state: Dict[str, Any] = field(default_factory=dict)


class AgenticDecisionEngine:
    """
    에이전틱 AI 의사결정 엔진
    
    LLM이 직접 자연어를 이해하고 도구를 선택하여 실행 계획을 수립합니다.
    중간 분류 과정 없이 순수한 AI 추론으로 작동합니다.
    """
    
    def __init__(self, llm_provider: LLMProvider, prompt_manager: PromptManager):
        self.llm_provider = llm_provider
        self.prompt_manager = prompt_manager
        self.logger = get_logger("agentic_decision_engine")
        self.available_tools: Dict[str, Tool] = {}
        
        # 기본 도구들 등록
        self._register_default_tools()
        
        self.logger.info("에이전틱 의사결정 엔진 초기화 완료")
    
    def _register_default_tools(self):
        """기본 도구들을 등록합니다"""
        default_tools = [
            Tool(
                name="notion_calendar",
                description="Notion 캘린더에 일정을 추가, 수정, 삭제합니다",
                capabilities=["일정 추가", "일정 조회", "일정 수정", "일정 삭제"],
                required_params=["action", "title"],
                optional_params=["date", "time", "description", "duration"]
            ),
            Tool(
                name="notion_todo",
                description="Notion 할일 데이터베이스를 관리합니다",
                capabilities=["할일 추가", "할일 완료", "할일 조회", "우선순위 설정"],
                required_params=["action", "title"],
                optional_params=["priority", "due_date", "category", "description"]
            ),
            Tool(
                name="web_search",
                description="웹에서 정보를 검색합니다",
                capabilities=["웹 검색", "실시간 정보 조회"],
                required_params=["query"],
                optional_params=["max_results", "date_range"]
            ),
            Tool(
                name="file_manager",
                description="파일과 폴더를 관리합니다",
                capabilities=["파일 생성", "파일 삭제", "파일 이동", "폴더 생성"],
                required_params=["action", "path"],
                optional_params=["content", "destination"]
            ),
            Tool(
                name="email_client",
                description="이메일을 읽고 보냅니다",
                capabilities=["이메일 읽기", "이메일 보내기", "이메일 검색"],
                required_params=["action"],
                optional_params=["to", "subject", "body", "search_query"]
            )
        ]
        
        for tool in default_tools:
            self.available_tools[tool.name] = tool
            
        self.logger.debug(f"{len(default_tools)}개 기본 도구 등록 완료")
    
    async def make_decision(self, context: DecisionContext) -> Decision:
        """
        순수 AI 추론으로 의사결정을 수행합니다
        
        Args:
            context: 의사결정 컨텍스트
            
        Returns:
            의사결정 결과
        """
        try:
            self.logger.info(f"에이전틱 의사결정 시작: {context.user_id}")
            
            # 사용 가능한 도구 정보 준비
            tools_info = [tool.to_dict() for tool in self.available_tools.values()]
            
            # 의사결정 프롬프트 생성
            decision_prompt = self._create_decision_prompt(context, tools_info)
            
            # LLM에게 의사결정 요청
            messages = [ChatMessage(role="user", content=decision_prompt)]
            response = await self.llm_provider.generate_response(messages)
            
            # 응답 파싱
            decision = await self._parse_decision_response(response.content, context)
            
            self.logger.info(f"에이전틱 의사결정 완료: 신뢰도 {decision.confidence_score:.2f}")
            return decision
            
        except Exception as e:
            self.logger.error(f"의사결정 중 오류: {e}")
            return self._create_fallback_decision(context)
    
    def _create_decision_prompt(self, context: DecisionContext, tools_info: List[Dict]) -> str:
        """의사결정을 위한 프롬프트를 생성합니다"""
        return f"""당신은 개인 AI 비서입니다. 사용자의 요청을 분석하여 적절한 도구를 선택하고 실행 계획을 수립해야 합니다.

**사용자 요청:**
"{context.user_message}"

**현재 시간:** {context.current_time.strftime('%Y년 %m월 %d일 %H시 %M분')}
**사용자 ID:** {context.user_id}

**사용 가능한 도구들:**
{json.dumps(tools_info, ensure_ascii=False, indent=2)}

**대화 기록:**
{json.dumps(context.conversation_history[-3:], ensure_ascii=False, indent=2) if context.conversation_history else "없음"}

**지침:**
1. 사용자의 의도를 정확히 파악하세요
2. 가장 적합한 도구(들)을 선택하세요
3. 단계별 실행 계획을 수립하세요
4. 신뢰도를 평가하세요 (0.0-1.0)
5. 추가 정보가 필요한지 판단하세요

**응답 형식 (JSON):**
```json
{{
    "selected_tools": ["도구명1", "도구명2"],
    "execution_plan": [
        {{
            "step": 1,
            "tool": "도구명",
            "action": "수행할 작업",
            "parameters": {{"key": "value"}},
            "description": "단계 설명"
        }}
    ],
    "reasoning": "왜 이런 결정을 내렸는지 Chain of Thought 방식으로 설명",
    "confidence_score": 0.85,
    "requires_user_input": false,
    "user_input_prompt": null,
    "estimated_time": 30
}}
```

사용자의 요청을 신중히 분석하고 최적의 계획을 수립해주세요."""
    
    async def _parse_decision_response(self, response_content: str, context: DecisionContext) -> Decision:
        """LLM 응답을 파싱하여 Decision 객체로 변환합니다"""
        try:
            self.logger.debug(f"LLM 응답 파싱 시작: {response_content[:200]}")
            
            # JSON 응답 추출
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_content[json_start:json_end]
                parsed_response = json.loads(json_str)
                
                self.logger.debug(f"파싱된 응답: {parsed_response}")
                
                # Decision 객체 생성
                confidence_score = parsed_response.get("confidence_score", 0.7)
                selected_tools = parsed_response.get("selected_tools", [])
                
                self.logger.info(f"선택된 도구들: {selected_tools}, 신뢰도: {confidence_score}")
                
                return Decision(
                    selected_tools=selected_tools,
                    execution_plan=parsed_response.get("execution_plan", []),
                    confidence_score=confidence_score,
                    confidence_level=self._get_confidence_level(confidence_score),
                    reasoning=parsed_response.get("reasoning", "AI가 분석한 결과입니다."),
                    estimated_time=parsed_response.get("estimated_time", 30),
                    requires_user_input=parsed_response.get("requires_user_input", False),
                    user_input_prompt=parsed_response.get("user_input_prompt"),
                    fallback_plan=parsed_response.get("fallback_plan", [])
                )
            else:
                raise ValueError("JSON 형식의 응답을 찾을 수 없습니다")
                
        except Exception as e:
            self.logger.error(f"응답 파싱 중 오류: {e}")
            # 기본 결정으로 폴백
            return self._create_simple_decision(response_content, context)
    
    def _create_simple_decision(self, response_content: str, context: DecisionContext) -> Decision:
        """파싱 실패시 간단한 결정을 생성합니다"""
        # 웹 검색을 기본으로 선택
        return Decision(
            selected_tools=["web_search"],
            execution_plan=[
                {
                    "step": 1,
                    "tool": "web_search",
                    "action": "search",
                    "parameters": {"query": context.user_message},
                    "description": "사용자 요청에 대한 웹 검색 수행"
                }
            ],
            confidence_score=0.6,
            confidence_level=ConfidenceLevel.MEDIUM,
            reasoning=f"요청을 분석한 결과: {response_content[:200]}...",
            estimated_time=30,
            requires_user_input=False
        )
    
    def _get_confidence_level(self, confidence_score: float) -> ConfidenceLevel:
        """신뢰도 점수를 레벨로 변환"""
        if confidence_score >= 0.9:
            return ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.7:
            return ConfidenceLevel.HIGH
        elif confidence_score >= 0.5:
            return ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.3:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW
    
    def _create_fallback_decision(self, context: DecisionContext) -> Decision:
        """오류 발생시 기본 의사결정 생성"""
        return Decision(
            selected_tools=["web_search"],
            execution_plan=[
                {
                    "step": 1,
                    "tool": "web_search",
                    "action": "search",
                    "parameters": {"query": context.user_message},
                    "description": "오류로 인한 기본 웹 검색"
                }
            ],
            confidence_score=0.3,
            confidence_level=ConfidenceLevel.LOW,
            reasoning="시스템 오류로 인해 기본 웹 검색을 수행합니다.",
            estimated_time=30,
            requires_user_input=False
        )
    
    def register_tool(self, tool: Tool):
        """새로운 도구를 등록합니다"""
        self.available_tools[tool.name] = tool
        self.logger.info(f"도구 등록: {tool.name}")
    
    def unregister_tool(self, tool_name: str):
        """도구를 제거합니다"""
        if tool_name in self.available_tools:
            del self.available_tools[tool_name]
            self.logger.info(f"도구 제거: {tool_name}")
    
    def get_available_tools(self) -> List[Tool]:
        """사용 가능한 도구 목록을 반환합니다"""
        return list(self.available_tools.values())
        
    async def parse_natural_command(self, 
                                  natural_command: str, 
                                  tool_name: str,
                                  current_date: Optional[str] = None) -> Dict[str, Any]:
        """
        자연어 명령을 직접 도구 파라미터로 변환 (에이전틱 AI 방식)
        
        Args:
            natural_command: 자연어 명령 (예: "내일까지 프로젝트 완료하기 급함")
            tool_name: 대상 도구 이름 (예: "notion_todo")
            current_date: 현재 날짜 (ISO 형식)
            
        Returns:
            Dict[str, Any]: 도구 실행을 위한 파라미터
        """
        self.logger.info(f"자연어 명령 파싱: '{natural_command}' → {tool_name}")
        
        if current_date is None:
            current_date = datetime.now().isoformat()
            
        # 도구 정보 가져오기
        if tool_name not in self.available_tools:
            raise ValueError(f"알 수 없는 도구: {tool_name}")
            
        tool = self.available_tools[tool_name]
        
        # LLM이 직접 자연어를 파라미터로 변환하는 프롬프트
        system_prompt = f"""당신은 자연어 명령을 {tool.name} 도구의 파라미터로 변환하는 AI입니다.

도구 정보:
- 이름: {tool.name}
- 설명: {tool.description}
- 기능: {', '.join(tool.capabilities)}
- 필수 파라미터: {', '.join(tool.required_params)}
- 선택적 파라미터: {', '.join(tool.optional_params)}

현재 날짜: {current_date}

자연어 명령을 분석하여 정확한 JSON 파라미터를 생성하세요.

중요한 규칙:
1. 날짜/시간 표현을 ISO 형식으로 변환 (예: "내일" → "2025-09-05T23:59:00+00:00")
2. 한국어 우선순위를 정확히 매핑 (급한/중요한 → "높음", 보통 → "중간", 천천히/나중에 → "낮음")
3. action 선택 가이드라인:
   - "~하기", "~작업", "~추가" → "create" (새로운 할일 생성)
   - "~완료", "완료했어" (기존 할일 ID 있음) → "complete" (기존 할일 완료)
   - "~수정", "~변경" → "update"
   - "~삭제", "~제거" → "delete"
   - "목록", "리스트" → "list"
   - "조회", "확인" → "get"
4. 제목에서 날짜/우선순위 키워드 제거하여 깔끔하게 정리
5. "완료하기"는 새로운 할일을 만드는 것이므로 반드시 "create" action 사용

응답은 반드시 유효한 JSON 형식으로만 답하세요."""

        user_prompt = f"자연어 명령: '{natural_command}'"
        
        try:
            # LLM에게 직접 파라미터 생성 요청
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=user_prompt)
            ]
            
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.1,  # 정확성을 위해 낮은 온도
                max_tokens=1000
            )
            
            # JSON 파싱
            content = response.content.strip()
            
            # JSON 블록에서 추출 (```json 감싸진 경우 처리)
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
                
            parameters = json.loads(content)
            
            self.logger.info(f"LLM 파라미터 생성 완료: {parameters}")
            return parameters
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON 파싱 오류: {e}, 응답: {response.content}")
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {response.content}")
        except Exception as e:
            self.logger.error(f"자연어 파싱 실패: {e}")
            raise


# 기존 DecisionEngine과의 호환성을 위한 별칭
DecisionEngine = AgenticDecisionEngine
