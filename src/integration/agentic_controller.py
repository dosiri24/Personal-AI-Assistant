"""
에이전틱 AI 통합 컨트롤러

기존 MCPIntegration과 새로운 ReAct 엔진을 연결하는 어댑터 레이어입니다.
기존 기능의 호환성을 보장하면서 진정한 에이전틱 AI 기능을 제공합니다.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from ..ai_engine.agent_state import AgentContext, AgentResult
from ..ai_engine.react_engine import ReactEngine
from ..ai_engine.llm_provider import LLMProvider
from ..ai_engine.prompt_templates import PromptManager
from ..mcp.registry import ToolRegistry
from ..mcp.executor import ToolExecutor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AgenticController:
    """
    에이전틱 AI 통합 컨트롤러
    
    기존 시스템과 새로운 ReAct 엔진을 연결하는 핵심 컨트롤러입니다.
    요청의 복잡도에 따라 적절한 처리 방식을 선택합니다.
    """
    
    def __init__(
        self,
        llm_provider: LLMProvider,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        prompt_manager: PromptManager
    ):
        self.llm_provider = llm_provider
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.prompt_manager = prompt_manager
        
        # ReAct 엔진 초기화
        self.react_engine = ReactEngine(
            llm_provider=llm_provider,
            tool_registry=tool_registry,
            tool_executor=tool_executor,
            prompt_manager=prompt_manager,
            max_iterations=10,
            timeout_seconds=300
        )
        
        # 성능 통계
        self.stats = {
            "total_requests": 0,
            "react_requests": 0,
            "legacy_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_execution_time": 0.0,
            "average_execution_time": 0.0,
            "min_execution_time": float('inf'),
            "max_execution_time": 0.0,
            "success_rate": 0.0
        }
        
        logger.info("에이전틱 AI 컨트롤러 초기화 완료")
    
    async def process_request(
        self,
        user_input: str,
        user_id: str = "default",
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        force_react: bool = False,
        use_advanced_planning: bool = True,  # Phase 2: 고급 계획 기능 활성화
        max_iterations: int = 10,
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """
        사용자 요청 처리 (적응적 라우팅)
        
        Args:
            user_input: 사용자 입력
            user_id: 사용자 ID
            conversation_history: 대화 히스토리
            force_react: ReAct 엔진 강제 사용
            use_advanced_planning: 고급 계획 기능 사용 여부
            max_iterations: 최대 반복 횟수
            timeout_seconds: 타임아웃 (초)
            
        Returns:
            Dict: 처리 결과 {"text": str, "execution": dict, "metadata": dict}
        """
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        # 복잡도 분석을 통한 처리 방식 결정
        complexity_analysis = await self._analyze_request_complexity(user_input, conversation_history)
        
        # force_react 플래그가 설정된 경우 강제로 ReAct 사용
        if force_react or complexity_analysis["use_react"]:
            if use_advanced_planning and complexity_analysis.get("complexity_score", 0) >= 7:
                logger.info("고급 계획 기반 ReAct 엔진 사용 결정")
                self.stats["react_requests"] += 1
                result = await self._process_with_advanced_planning(
                    user_input, user_id, conversation_history, max_iterations, timeout_seconds
                )
            else:
                logger.info("기본 ReAct 엔진 사용 결정")
                self.stats["react_requests"] += 1
                result = await self._process_with_react_engine(
                    user_input, user_id, conversation_history, max_iterations, timeout_seconds
                )
        else:
            logger.info("레거시 처리 방식 사용 결정")
            self.stats["legacy_requests"] += 1
            result = await self._process_with_legacy_system(
                user_input, user_id, conversation_history
            )
        
        # 통계 업데이트 (안전한 처리)
        try:
            execution_time = time.time() - start_time
            success = result.get("execution", {}).get("status") == "success"
            self._update_stats(execution_time, success)
        except Exception as stats_error:
            logger.error(f"통계 업데이트 실패 (처리는 계속): {stats_error}")
            # 통계 업데이트 실패해도 메인 처리는 계속 진행
        
        return result
    
    def get_stats(self) -> Dict[str, Any]:
        """성능 통계 반환"""
        logger.debug("성능 통계 조회")
        return {
            **self.stats,
            "react_usage_rate": self.stats["react_requests"] / max(self.stats["total_requests"], 1),
            "legacy_usage_rate": self.stats["legacy_requests"] / max(self.stats["total_requests"], 1)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
        try:
            logger.debug("시스템 상태 점검 시작")
            
            # LLM 프로바이더 상태 확인
            llm_available = self.llm_provider.is_available()
            logger.debug(f"LLM 프로바이더 상태: {llm_available}")
            
            # 도구 레지스트리 상태 확인  
            tools_count = len(list(self.tool_registry.list_tools()))
            logger.debug(f"등록된 도구 수: {tools_count}")
            
            # ReAct 엔진 상태 확인
            react_available = self.react_engine is not None
            logger.debug(f"ReAct 엔진 상태: {react_available}")
            
            status = "healthy" if llm_available and react_available else "degraded"
            logger.info(f"시스템 상태 점검 완료: {status}")
            
            return {
                "status": status,
                "llm_available": llm_available,
                "react_available": react_available,
                "tools_count": tools_count,
                "stats": self.get_stats()
            }
        except Exception as e:
            logger.error(f"상태 확인 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _process_with_react_engine(
        self,
        user_input: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]],
        max_iterations: int,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """ReAct 엔진을 사용한 처리"""
        logger.info(f"ReAct 엔진 처리 시작: 사용자={user_id}, 입력='{user_input[:50]}...', "
                   f"최대반복={max_iterations}, 타임아웃={timeout_seconds}초")
        
        try:
            # 컨텍스트 생성
            context = AgentContext(
                user_id=user_id,
                session_id=f"{user_id}_{int(time.time())}",
                goal=user_input,
                available_tools=list(self.tool_registry.list_tools()),
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds,
                conversation_history=(conversation_history or [])[-10:],  # 최근 10개 대화까지
                constraints={"conversation_history": (conversation_history or [])[:10]}
            )
            
            logger.debug(f"AgentContext 생성 완료: 세션={context.session_id}, "
                        f"사용가능도구={len(context.available_tools)}개")
            
            # ReAct 엔진 실행
            result = await self.react_engine.execute_goal(
                goal=user_input,
                context=context,
                available_tools=context.available_tools
            )
            
            # 결과 포맷팅
            if result.success:
                logger.info(f"ReAct 엔진 성공: {len(result.scratchpad.steps)}회 반복, "
                           f"{result.scratchpad.total_tool_calls}회 도구 호출")
                return {
                    "text": result.final_answer,
                    "execution": {
                        "status": "success",
                        "method": "react",
                        "iterations": len(result.scratchpad.steps),
                        "tools_used": list(result.scratchpad.unique_tools_used),
                        "total_tool_calls": result.scratchpad.total_tool_calls,
                        "successful_calls": result.scratchpad.successful_tool_calls,
                        "scratchpad_summary": result.scratchpad.get_latest_context()
                    },
                    "metadata": result.metadata
                }
            else:
                logger.warning(f"ReAct 엔진 부분 실패: {result.error_message}")
                
                # 타임아웃의 경우 더 나은 응답 제공
                response_text = result.final_answer
                if result.error_message == "TIMEOUT_EXCEEDED" and result.metadata.get("response"):
                    response_text = result.metadata["response"]
                elif not response_text or response_text.strip() == "":
                    response_text = "요청을 처리하는 중 문제가 발생했어요. 다시 시도해주세요."
                
                return {
                    "text": response_text,
                    "execution": {
                        "status": "partial_failure",
                        "method": "react",
                        "error": result.error_message,
                        "iterations": len(result.scratchpad.steps),
                        "progress": result.scratchpad.get_latest_context()
                    },
                    "metadata": result.metadata
                }
                
        except Exception as e:
            logger.error(f"ReAct 엔진 처리 실패: {e}")
            return {
                "text": f"ReAct 엔진 처리 중 오류가 발생했습니다: {str(e)}",
                "execution": {
                    "status": "error",
                    "method": "react",
                    "error": str(e)
                },
                "metadata": {}
            }
    
    async def _process_with_advanced_planning(
        self,
        user_input: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]],
        max_iterations: int,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """고급 계획 기반 처리 (Phase 2)"""
        try:
            # AgentContext 생성
            context = AgentContext(
                user_id=user_id,
                session_id=f"session_{int(time.time())}",
                goal=user_input,
                available_tools=self.tool_registry.list_tools(),
                conversation_history=(conversation_history or [])[-10:],  # 최근 10개 대화까지
                max_iterations=max_iterations,
                timeout_seconds=timeout_seconds
            )
            
            # 고급 계획 기반 실행
            result = await self.react_engine.execute_goal_with_planning(context)
            
            self.stats["react_requests"] += 1
            
            logger.info(f"고급 계획 처리 완료: {'성공' if result.success else '실패'}")
            
            return {
                "text": result.final_answer,
                "execution": {
                    "status": "success" if result.success else "failure",
                    "method": "advanced_planning",
                    "iterations": result.metadata.get("iterations", 0),
                    "execution_time": result.metadata.get("execution_time", 0),
                    "plan_id": result.metadata.get("plan_id"),
                    "scratchpad_steps": len(result.scratchpad.steps) if result.scratchpad else 0,
                    "tools_used": list(result.scratchpad.unique_tools_used) if result.scratchpad else [],
                    "error_message": result.error_message
                },
                "metadata": {
                    "complexity": "high",
                    "planning_enabled": True,
                    "adaptation_events": result.metadata.get("adaptation_events", [])
                }
            }
            
        except Exception as e:
            logger.error(f"고급 계획 처리 실패: {e}")
            # 기본 ReAct 엔진으로 폴백
            logger.info("기본 ReAct 엔진으로 폴백")
            return await self._process_with_react_engine(
                user_input, user_id, conversation_history, max_iterations, timeout_seconds
            )
    
    async def _process_with_legacy_system(
        self,
        user_input: str,
        user_id: str,
        conversation_history: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """레거시 시스템을 사용한 처리 (기존 방식)"""
        logger.info(f"레거시 시스템 처리 시작: 사용자={user_id}, 복잡도=단순")
        
        try:
            # 기존 MCPIntegration 방식을 시뮬레이션
            # 실제로는 기존 decision_engine을 사용
            from ..ai_engine.decision_engine import AgenticDecisionEngine, DecisionContext
            
            decision_engine = AgenticDecisionEngine(
                llm_provider=self.llm_provider,
                prompt_manager=self.prompt_manager
            )
            
            logger.debug("레거시 의사결정 엔진 생성 완료")
            
            # 기존 방식으로 의사결정
            context = DecisionContext(
                user_message=user_input,
                user_id=user_id,
                conversation_history=conversation_history or []
            )
            
            decision = await decision_engine.make_decision(context)
            logger.debug(f"의사결정 완료: 도구={decision.selected_tools}")
            
            # 단순 도구 실행
            if decision.selected_tools:
                tool_name = decision.selected_tools[0]
                if decision.execution_plan:
                    step = decision.execution_plan[0]
                    parameters = step.get("parameters", {})
                    
                    logger.debug(f"도구 실행: {tool_name}, 파라미터={parameters}")
                    
                    # 도구 실행
                    execution_result = await self.tool_executor.execute_tool(
                        tool_name=tool_name,
                        parameters=parameters
                    )
                    
                    if execution_result.result.is_success:
                        logger.info(f"레거시 처리 성공: {tool_name}")
                        return {
                            "text": f"작업이 완료되었습니다: {execution_result.result.data}",
                            "execution": {
                                "status": "success",
                                "method": "legacy",
                                "tool_name": tool_name,
                                "parameters": parameters,
                                "result_data": execution_result.result.data
                            },
                            "metadata": {}
                        }
                    else:
                        logger.warning(f"레거시 도구 실행 실패: {execution_result.result.error_message}")
                        return {
                            "text": f"작업 실행 중 오류가 발생했습니다: {execution_result.result.error_message}",
                            "execution": {
                                "status": "error",
                                "method": "legacy",
                                "tool_name": tool_name,
                                "error": execution_result.result.error_message
                            },
                            "metadata": {}
                        }
            else:
                # 직접 답변
                logger.debug("직접 답변 생성")
                return {
                    "text": decision.reasoning or "요청을 처리했습니다.",
                    "execution": {
                        "status": "direct_response",
                        "method": "legacy"
                    },
                    "metadata": {}
                }
                
        except Exception as e:
            logger.error(f"레거시 시스템 처리 실패: {e}")
            return {
                "text": f"처리 중 오류가 발생했습니다: {str(e)}",
                "execution": {
                    "status": "error",
                    "method": "legacy",
                    "error": str(e)
                },
                "metadata": {}
            }
    
    async def _analyze_request_complexity(
        self,
        user_input: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """완전 LLM 기반 복잡도 분석 - 동적 점수 계산"""
        logger.debug(f"복잡도 분석 시작: '{user_input[:30]}...'")
        
        # 빠른 휴리스틱 판단 (간단한 패턴)
        simple_patterns = ['안녕', '고마워', '감사', '네', '아니오', '좋아', '싫어']
        todo_patterns = ['todo', '할일', '추가해줘', '만들어줘']
        
        user_lower = user_input.lower()
        
        # 매우 간단한 요청 (1-2점)
        if any(pattern in user_lower for pattern in simple_patterns) and len(user_input) < 20:
            return {
                'use_react': False,  # 간단한 요청은 ReAct 불필요
                'complexity': 'simple',
                'complexity_score': 2,
                'reasoning': '간단한 응답 요청'
            }
        
        # TODO 관련 단순 요청 (4-5점)
        if any(pattern in user_lower for pattern in todo_patterns) and ',' not in user_input:
            return {
                'use_react': True,   # TODO 작업은 ReAct 필요
                'complexity': 'medium',
                'complexity_score': 4,
                'reasoning': '단일 TODO 작업'
            }
        
        try:
            from ..ai_engine.llm_provider import ChatMessage
            
            # 더 정교한 복잡도 분석 프롬프트
            analysis_prompt = f"""사용자 요청을 분석해주세요: "{user_input}"

다음 기준으로 복잡도를 평가하고 점수를 매겨주세요:

복잡도 기준:
- 1-3점: 단순 응답 (인사, 감사, 간단한 질문)
- 4-6점: 중간 복잡도 (단일 도구 사용, 기본 검색)
- 7-10점: 높은 복잡도 (다단계 작업, 계획 수립, 분석, 여러 도구 조합)

다음 형식으로 답해주세요:
분류: [단순/복잡]
점수: [1-10]
이유: [분석 근거]"""

            messages = [ChatMessage(role="user", content=analysis_prompt)]
            
            response = await self.llm_provider.generate_response(
                messages,
                temperature=0.2,  # 빠른 판단을 위해 온도 감소
                max_tokens=8192   # 응답 생성 토큰 수 증가 (4096→8192)
            )
            
            if response and response.content:
                response_text = response.content.strip()
                
                # 점수 추출
                complexity_score = 5  # 기본값
                try:
                    import re
                    score_match = re.search(r'점수:\s*(\d+)', response_text)
                    if score_match:
                        complexity_score = int(score_match.group(1))
                        complexity_score = max(1, min(10, complexity_score))  # 1-10 범위 제한
                except:
                    pass
                
                # 분류 파싱
                response_lower = response_text.lower()
                if "분류: 단순" in response_lower or complexity_score <= 3:
                    use_react = False
                    complexity = "simple"
                elif "분류: 복잡" in response_lower or complexity_score >= 7:
                    use_react = True
                    complexity = "complex"
                else:
                    # 중간 복잡도 (4-6점)
                    use_react = True
                    complexity = "medium"
                
                logger.info(f"복잡도 분석 완료: {complexity} (점수: {complexity_score}/10)")
                
                return {
                    "use_react": use_react,
                    "complexity": complexity,
                    "complexity_score": complexity_score,
                    "reasoning": f"LLM 분석: {complexity} 복잡도, 점수 {complexity_score}/10"
                }
            else:
                raise Exception("LLM 응답이 비어있음")
            
        except Exception as e:
            logger.error(f"LLM 복잡도 분석 실패: {e}")
            
            # LLM 실패 시 안전한 중간값으로 폴백
            logger.info("LLM 실패 시 중간 복잡도로 처리")
            return {
                "use_react": True,
                "complexity": "medium",
                "complexity_score": 5,
                "reasoning": "LLM 분석 실패, 중간 복잡도로 안전하게 처리"
            }
    
    def _update_stats(self, execution_time: float, success: bool) -> None:
        """통계 업데이트 - 안전한 처리"""
        try:
            logger.debug(f"통계 업데이트: 실행시간={execution_time:.2f}초, 성공={success}")
            
            # 기본 통계
            self.stats["total_requests"] += 1
            self.stats["total_execution_time"] += execution_time
            self.stats["average_execution_time"] = (
                self.stats["total_execution_time"] / self.stats["total_requests"]
            )
            
            # 성공/실패 통계
            if success:
                self.stats["successful_requests"] += 1
            else:
                self.stats["failed_requests"] += 1
            
            # 성공률 계산
            self.stats["success_rate"] = (
                self.stats["successful_requests"] / self.stats["total_requests"]
            )
            
            # 성능 통계 (안전한 처리)
            if self.stats.get("min_execution_time") is None or execution_time < self.stats.get("min_execution_time", float('inf')):
                self.stats["min_execution_time"] = execution_time
            if execution_time > self.stats.get("max_execution_time", 0):
                self.stats["max_execution_time"] = execution_time
            
            logger.debug(f"통계 업데이트 완료: 총요청={self.stats['total_requests']}, "
                        f"성공률={self.stats['success_rate']:.2f}, "
                        f"평균시간={self.stats['average_execution_time']:.2f}초")
            
        except Exception as e:
            logger.error(f"통계 업데이트 중 오류: {e}")
            # 통계 업데이트 실패해도 예외를 다시 발생시키지 않음
