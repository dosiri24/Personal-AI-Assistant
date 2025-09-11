"""
실행 모듈 (ActionExecutor)

ReAct 엔진의 실행(Action) 부분을 담당하는 모듈
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from ..agent_state import (
    AgentScratchpad, AgentContext, ActionRecord, ObservationRecord, StepStatus
)
from ...mcp.registry import ToolRegistry
from ...mcp.executor import ToolExecutor
from ...utils.logger import get_logger

logger = get_logger(__name__)


class ActionExecutor:
    """행동 실행기 - ReAct의 Action 부분"""
    
    def __init__(self, tool_registry: ToolRegistry, tool_executor: ToolExecutor):
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
    
    async def execute_and_observe(self, action: ActionRecord, scratchpad: AgentScratchpad,
                                 context: AgentContext) -> ObservationRecord:
        """행동을 실행하고 결과를 관찰"""
        logger.debug(f"행동 실행 중: 도구='{action.tool_name}', 파라미터={list(action.parameters.keys()) if action.parameters else 'None'}")
        
        start_time = time.time()
        
        try:
            scratchpad.update_action_status(StepStatus.EXECUTING)
            
            # 도구 실행
            if action.tool_name:
                logger.debug(f"도구 '{action.tool_name}' 실행 시작")
                execution_result = await self.tool_executor.execute_tool(
                    tool_name=action.tool_name,
                    parameters=action.parameters
                )
            else:
                # tool_name이 None인 경우 처리
                logger.error("도구 이름이 지정되지 않음")
                scratchpad.update_action_status(
                    StepStatus.FAILED,
                    execution_time=0.0,
                    error_message="도구 이름이 지정되지 않았습니다."
                )
                observation = scratchpad.add_observation(
                    content="도구 이름이 지정되지 않아 실행할 수 없습니다.",
                    success=False,
                    analysis="행동 결정 과정에서 도구 이름이 누락됨"
                )
                return observation
            
            execution_time = time.time() - start_time
            
            if execution_result.result.is_success:
                scratchpad.update_action_status(
                    StepStatus.COMPLETED,
                    execution_time=execution_time
                )
                
                # 성공적인 관찰
                observation = scratchpad.add_observation(
                    content=f"도구 '{action.tool_name}' 실행 성공: {execution_result.result.data}",
                    success=True,
                    data=execution_result.result.data,
                    analysis=await self._analyze_execution_result(execution_result, context)
                )
                
                logger.info(f"도구 실행 성공: '{action.tool_name}' (실행시간={execution_time:.2f}초)")
                
            else:
                scratchpad.update_action_status(
                    StepStatus.FAILED,
                    execution_time=execution_time,
                    error_message=execution_result.result.error_message
                )
                
                # 실패 관찰 및 교훈 도출
                error_msg = execution_result.result.error_message or "알 수 없는 오류"
                lessons = await self._extract_lessons_from_failure(
                    action, error_msg, context
                )
                
                observation = scratchpad.add_observation(
                    content=f"도구 '{action.tool_name}' 실행 실패: {execution_result.result.error_message}",
                    success=False,
                    analysis=f"실패 원인 분석: {execution_result.result.error_message}",
                    lessons_learned=lessons
                )
                
                logger.warning(f"도구 실행 실패: '{action.tool_name}' - {execution_result.result.error_message} (실행시간={execution_time:.2f}초)")
            
            return observation
            
        except Exception as e:
            execution_time = time.time() - start_time
            scratchpad.update_action_status(
                StepStatus.FAILED,
                execution_time=execution_time,
                error_message=str(e)
            )
            
            observation = scratchpad.add_observation(
                content=f"도구 실행 중 예외 발생: {str(e)}",
                success=False,
                analysis=f"예외 상황 분석: {str(e)}"
            )
            
            logger.error(f"도구 실행 중 예외: {e} (실행시간={execution_time:.2f}초)")
            return observation
    
    async def _analyze_execution_result(self, execution_result, context: AgentContext) -> str:
        """실행 결과 분석"""
        try:
            result_data = execution_result.result.data
            
            # 기본 분석
            analysis_parts = ["실행이 성공적으로 완료되었습니다."]
            
            # 결과 데이터 기반 분석
            if isinstance(result_data, dict):
                if "success" in result_data:
                    analysis_parts.append(f"작업 결과: {result_data.get('success', '알 수 없음')}")
                if "message" in result_data:
                    analysis_parts.append(f"메시지: {result_data.get('message', '')}")
            elif isinstance(result_data, str):
                analysis_parts.append(f"결과: {result_data[:100]}...")
            
            return " ".join(analysis_parts)
            
        except Exception as e:
            logger.warning(f"실행 결과 분석 실패: {e}")
            return "실행이 완료되었지만 결과 분석 중 오류가 발생했습니다."
    
    async def _extract_lessons_from_failure(self, action: ActionRecord, error_msg: str, 
                                          context: AgentContext) -> List[str]:
        """실패로부터 교훈 도출"""
        lessons = []
        
        try:
            # 일반적인 교훈
            if "권한" in error_msg:
                lessons.append("권한 설정을 확인해야 합니다")
            elif "연결" in error_msg or "네트워크" in error_msg:
                lessons.append("네트워크 연결 상태를 확인해야 합니다")
            elif "형식" in error_msg or "포맷" in error_msg:
                lessons.append("입력 데이터 형식을 다시 확인해야 합니다")
            elif "not found" in error_msg.lower():
                lessons.append("리소스가 존재하는지 확인해야 합니다")
            
            # 도구별 특화 교훈
            if action.tool_name:
                if action.tool_name == "notion_todo":
                    lessons.append("Notion 데이터베이스 설정을 확인해야 합니다")
                elif action.tool_name == "apple_calendar":
                    lessons.append("캘린더 접근 권한을 확인해야 합니다")
            
            return lessons if lessons else ["다른 접근 방법을 시도해야 합니다"]
            
        except Exception as e:
            logger.warning(f"교훈 도출 실패: {e}")
            return ["실패 원인을 분석하고 다른 방법을 시도해야 합니다"]
