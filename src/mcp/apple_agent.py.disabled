#!/usr/bin/env python3
"""
Apple Apps Agent
자연어 명령을 받아 AI가 스스로 적절한 Apple 앱 도구를 선택하고 실행하는 에이전트
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import re

from ..ai_engine.llm_provider import LLMManager
from .apple_tools import register_apple_tools, AppleAppsManager
from .base_tool import BaseTool, ToolResult, ExecutionStatus

logger = logging.getLogger(__name__)


class AppleAppsAgent:
    """Apple 앱들과 상호작용하는 자연어 처리 에이전트
    
    사용자의 자연어 명령을 분석하여 적절한 Apple 앱 도구를 선택하고 실행합니다.
    안전성과 사용자 개인정보 보호를 최우선으로 합니다.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        # LLM 및 로거 초기화
        self.llm_manager = None
        self.logger = logger  # loguru logger 사용
        
        # Apple 도구 관리자 초기화
        self.apple_manager = AppleAppsManager()
        self.available_tools: List[BaseTool] = []
        
        # 실행 이력 및 상태 관리
        self.execution_history: List[Dict[str, Any]] = []
        self.last_execution_id: Optional[str] = None
        
        self.logger.info("Apple Apps Agent 초기화 시작")
    
    async def initialize(self) -> bool:
        """Agent 초기화 - LLM과 Apple 도구들 설정"""
        try:
            # LLM Manager 초기화
            from ..ai_engine.llm_provider import get_llm_manager
            self.llm_manager = await get_llm_manager()
            
            # Apple 도구들 등록
            register_apple_tools(self.apple_manager)
            # self.available_tools = list(self.apple_manager.get_all_tools().values())
            self.available_tools = []  # 임시로 빈 리스트
            
            self.logger.info(f"Apple Agent 초기화 완료. 사용 가능한 도구: {len(self.available_tools)}개")
            return True
            
        except Exception as e:
            self.logger.error(f"Apple Agent 초기화 실패: {e}")
            return False
    
    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """자연어 명령을 처리하여 Apple 앱 도구 실행"""
        try:
            self.logger.info(f"명령 처리 시작: {command}")
            
            # 1. 명령 분석
            analysis_result = await self._analyze_command(command)
            
            # 2. 안전성 검사
            if not self._is_safe_command(analysis_result):
                return ToolResult(
                    success=False,
                    data={"error": "안전하지 않은 명령으로 판단되어 실행이 거부되었습니다."},
                    execution_time=0.0,
                    status=ExecutionStatus.FAILED
                )
            
            # 3. 도구 체인 실행
            return await self._execute_tool_chain(analysis_result, context or {})
            
        except Exception as e:
            self.logger.error(f"명령 처리 중 오류: {e}")
            return ToolResult(
                success=False,
                data={"error": f"명령 처리 실패: {str(e)}"},
                execution_time=0.0,
                status=ExecutionStatus.FAILED
            )
    
    async def process_natural_language_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """자연어 명령을 처리하여 적절한 Apple 앱 도구를 실행"""
        logger.info(f"자연어 명령 처리 시작: {command}")
        
        try:
            # 1. 명령 분석 및 도구 선택
            analysis_result = await self._analyze_command(command, context)
            
            if not analysis_result.get("success"):
                return {
                    "success": False,
                    "error": analysis_result.get("error", "명령 분석 실패"),
                    "command": command
                }
            
            # 2. 선택된 도구 실행
            execution_result = await self._execute_tool_chain(analysis_result["plan"])
            
            # 3. 결과 종합
            return {
                "success": execution_result.get("success", False),
                "command": command,
                "analysis": analysis_result,
                "execution": execution_result,
                "final_message": execution_result.get("final_message", "작업 완료")
            }
            
        except Exception as e:
            logger.error(f"자연어 명령 처리 오류: {e}")
            return {
                "success": False,
                "error": f"처리 중 오류 발생: {str(e)}",
                "command": command
            }
    
    async def _analyze_command(self, command: str) -> Dict[str, Any]:
        """자연어 명령을 분석하여 실행할 도구와 파라미터를 결정"""
        
        # Apple 앱별 도구 목록 생성
        available_tools = []
        for tool in self.available_tools:
            if hasattr(tool, 'name') and hasattr(tool, 'description'):
                available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": getattr(tool, 'parameters', {})
                })
        
        # 분석 프롬프트 준비
        analysis_prompt = f"""
사용자의 자연어 명령을 분석하여 Apple 앱 도구를 선택하고 실행 계획을 세워주세요.

사용자 명령: "{command}"

사용 가능한 Apple 앱 도구들:
{json.dumps(available_tools, ensure_ascii=False, indent=2)}

다음 JSON 형식으로 응답해주세요:
{{
    "selected_tools": ["도구명1", "도구명2"],
    "execution_plan": [
        {{
            "tool": "도구명",
            "parameters": {{"param1": "value1"}},
            "reasoning": "이 도구를 선택한 이유"
        }}
    ],
    "confidence_score": 0.0-1.0,
    "confidence_level": "LOW|MEDIUM|HIGH|VERY_HIGH",
    "reasoning": "전체적인 분석 및 도구 선택 이유",
    "estimated_time": 예상소요시간(초),
    "requires_user_input": false,
    "safety_notes": "안전성 관련 주의사항 (있다면)"
}}

특별히 다음 사항을 고려해주세요:
1. 메시지 보내기나 연락처 관련 작업은 신중하게 판단
2. Notes 앱을 사용한 메모 작성을 우선 권장
3. 사용자가 명시적으로 다른 사람에게 피해를 줄 수 있는 작업을 요청하지 않았는지 확인
"""

        try:
            # LLM에 메시지 형식으로 전달
            messages = [
                {"role": "system", "content": "당신은 Apple 앱 도구 선택을 도와주는 AI 어시스턴트입니다."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = await self.llm_manager.generate_response(messages)
            
            # 응답에서 JSON 부분 추출
            if hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)
                
            try:
                json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
                if json_match:
                    analysis_result = json.loads(json_match.group(1))
                else:
                    analysis_result = json.loads(response_text)
                    
                self.logger.info(f"명령 분석 결과: {analysis_result}")
                return analysis_result
                
            except json.JSONDecodeError:
                self.logger.error(f"JSON 파싱 실패: {response_text}")
                return self._fallback_analysis(command)
                
        except Exception as e:
            self.logger.error(f"명령 분석 중 오류: {e}")
            return self._fallback_analysis(command)
    
    async def _execute_tool_chain(self, plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        """단계별 도구 실행 계획을 수행"""
        results = []
        final_message_parts = []
        
        try:
            for step_info in plan:
                step_num = step_info.get("step", 0)
                tool_name = step_info.get("tool")
                action = step_info.get("action")
                parameters = step_info.get("parameters", {})
                reason = step_info.get("reason", "")
                
                logger.info(f"Step {step_num} 실행: {tool_name} - {action}")
                
                # 도구 찾기
                tool = self._find_tool_by_name(tool_name)
                if not tool:
                    error_msg = f"도구를 찾을 수 없습니다: {tool_name}"
                    logger.error(error_msg)
                    results.append({
                        "step": step_num,
                        "success": False,
                        "error": error_msg
                    })
                    continue
                
                # 매개변수에 action 추가
                if action and "action" not in parameters:
                    parameters["action"] = action
                
                # 도구 실행
                try:
                    result = await tool.execute(parameters)
                    
                    if result.is_success:
                        logger.info(f"Step {step_num} 성공")
                        results.append({
                            "step": step_num,
                            "success": True,
                            "tool": tool_name,
                            "action": action,
                            "result": result.data,
                            "reason": reason
                        })
                        
                        # 결과 메시지 수집
                        if result.data and isinstance(result.data, dict):
                            message = result.data.get("message", "")
                            if message:
                                final_message_parts.append(f"Step {step_num}: {message}")
                    else:
                        error_msg = f"Step {step_num} 실패: {result.error_message}"
                        logger.error(error_msg)
                        results.append({
                            "step": step_num,
                            "success": False,
                            "error": error_msg,
                            "tool": tool_name,
                            "action": action
                        })
                
                except Exception as e:
                    error_msg = f"Step {step_num} 실행 중 오류: {str(e)}"
                    logger.error(error_msg)
                    results.append({
                        "step": step_num,
                        "success": False,
                        "error": error_msg,
                        "tool": tool_name,
                        "action": action
                    })
            
            # 전체 결과 평가
            successful_steps = [r for r in results if r.get("success", False)]
            failed_steps = [r for r in results if not r.get("success", False)]
            
            overall_success = len(successful_steps) > 0 and len(failed_steps) == 0
            
            # 최종 메시지 생성
            if overall_success:
                final_message = "✅ 모든 작업이 성공적으로 완료되었습니다.\n" + "\n".join(final_message_parts)
            else:
                final_message = f"⚠️ {len(successful_steps)}/{len(results)}개 작업 완료"
                if failed_steps:
                    failed_msgs = [f"- {r.get('error', '알 수 없는 오류')}" for r in failed_steps]
                    final_message += "\n실패한 작업:\n" + "\n".join(failed_msgs)
            
            return {
                "success": overall_success,
                "results": results,
                "summary": {
                    "total_steps": len(results),
                    "successful_steps": len(successful_steps),
                    "failed_steps": len(failed_steps)
                },
                "final_message": final_message
            }
            
        except Exception as e:
            logger.error(f"도구 체인 실행 중 오류: {e}")
            return {
                "success": False,
                "error": f"실행 중 오류 발생: {str(e)}",
                "results": results,
                "final_message": f"❌ 작업 실행 중 오류가 발생했습니다: {str(e)}"
            }
    
    def _find_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        """이름으로 도구 찾기"""
        for tool in self.apple_tools:
            if tool.metadata.name == tool_name:
                return tool
        return None
    
    async def get_available_capabilities(self) -> Dict[str, Any]:
        """에이전트가 수행할 수 있는 작업들 반환"""
        capabilities = {
            "apple_apps": {},
            "total_tools": len(self.apple_tools)
        }
        
        for tool in self.apple_tools:
            app_name = tool.metadata.name.replace("apple_", "")
            capabilities["apple_apps"][app_name] = {
                "name": tool.metadata.name,
                "description": tool.metadata.description,
                "category": tool.metadata.category.value,
                "tags": tool.metadata.tags
            }
        
        return capabilities
    
    async def suggest_commands(self, user_input: str = "") -> List[str]:
        """사용자 입력을 바탕으로 명령어 제안"""
        suggestions = [
            "회의 내용을 메모해줘",
            "오늘 할 일 목록을 노트에 만들어줘", 
            "프로젝트 아이디어를 정리해서 노트 만들어줘",
            "내일 일정을 확인하고 메모해줘",
            "Apple 앱 연동 테스트 결과를 정리해줘",
            "노트 검색해서 관련 내용 찾아줘",
            "캘린더에서 이번 주 일정 확인해줘",
            "미리 알림에 새로운 할 일 추가해줘"
        ]
        
        if user_input:
            # 사용자 입력과 관련된 제안 우선
            related_suggestions = []
            for suggestion in suggestions:
                if any(word in suggestion for word in user_input.split()):
                    related_suggestions.append(suggestion)
            
            return related_suggestions + [s for s in suggestions if s not in related_suggestions]
        
        return suggestions


# 편의를 위한 팩토리 함수
def create_apple_apps_agent(llm_manager: LLMManager, server_path: str = "external/apple-mcp") -> AppleAppsAgent:
    """Apple Apps Agent 인스턴스 생성"""
    apple_manager = AppleAppsManager(server_path)
    return AppleAppsAgent(apple_manager, llm_manager)
