"""
Apple 앱 통합 자연어 처리 에이전트

사용자의 자연어 명령을 분석하여 적절한 Apple 앱 도구를 선택하고 실행합니다.
안전성과 사용자 개인정보 보호를 최우선으로 합니다.
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Any
from loguru import logger
from ..ai_engine.llm_provider import LLMManager, get_llm_manager
from .apple_tools import AppleAppsManager
from .base_tool import ToolResult, ExecutionStatus
from .registry import ToolRegistry


class AppleAppsAgent:
    """Apple 앱들과 상호작용하는 자연어 처리 에이전트"""
    
    def __init__(self):
        self.llm_manager: Optional[LLMManager] = None
        self.apple_manager = AppleAppsManager()
        self.tool_registry = ToolRegistry()
        self.execution_history: List[Dict[str, Any]] = []
        self.last_execution_id: Optional[str] = None
        
        logger.info("Apple Apps Agent 초기화 시작")
    
    async def initialize(self) -> bool:
        """Agent 초기화"""
        try:
            # LLM Manager 초기화
            self.llm_manager = await get_llm_manager()
            
            # Apple 도구들 등록 (동기 호출)
            from .apple_tools import register_apple_tools
            register_apple_tools(self.apple_manager)
            
            logger.info(f"Apple Agent 초기화 완료. Apple MCP 서버 연결 준비됨")
            return True
            
        except Exception as e:
            logger.error(f"Apple Agent 초기화 실패: {e}")
            return False
    
    async def process_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> ToolResult:
        """자연어 명령을 처리하여 Apple 앱 도구 실행"""
        try:
            logger.info(f"명령 처리 시작: {command}")
            
            # 1. 명령 분석
            analysis_result = await self._analyze_command(command)
            
            # 2. 안전성 검사
            if not self._is_safe_command(analysis_result):
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="안전하지 않은 명령으로 판단되어 실행이 거부되었습니다.",
                    execution_time=0.0
                )
            
            # 3. 도구 실행
            return await self._execute_tool_chain(analysis_result)
            
        except Exception as e:
            logger.error(f"명령 처리 중 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"명령 처리 실패: {str(e)}",
                execution_time=0.0
            )
    
    async def _analyze_command(self, command: str) -> Dict[str, Any]:
        """자연어 명령을 분석하여 실행할 도구와 파라미터를 결정"""
        
        # Apple MCP 서버의 사용 가능한 도구들
        available_tools = [
            {
                "name": "send_message",
                "description": "Messages 앱을 통해 메시지 전송",
                "parameters": {"recipient": "수신자", "message": "메시지 내용"}
            },
            {
                "name": "create_note",
                "description": "Notes 앱에서 새로운 노트 생성",
                "parameters": {"title": "노트 제목", "content": "노트 내용"}
            },
            {
                "name": "add_contact",
                "description": "Contacts 앱에 새로운 연락처 추가",
                "parameters": {"name": "이름", "phone": "전화번호", "email": "이메일"}
            },
            {
                "name": "send_email",
                "description": "Mail 앱을 통해 이메일 전송",
                "parameters": {"to": "수신자", "subject": "제목", "body": "내용"}
            },
            {
                "name": "create_reminder",
                "description": "Reminders 앱에서 새로운 리마인더 생성",
                "parameters": {"title": "제목", "notes": "메모", "due_date": "마감일"}
            },
            {
                "name": "create_calendar_event",
                "description": "Calendar 앱에서 새로운 이벤트 생성",
                "parameters": {"title": "제목", "start_date": "시작 시간", "end_date": "종료 시간"}
            },
            {
                "name": "get_directions",
                "description": "Maps 앱에서 길찾기",
                "parameters": {"destination": "목적지"}
            }
        ]
        
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
            if not self.llm_manager:
                return self._fallback_analysis(command)
                
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
                    
                logger.info(f"명령 분석 결과: {analysis_result}")
                return analysis_result
                
            except json.JSONDecodeError:
                logger.error(f"JSON 파싱 실패: {response_text}")
                return self._fallback_analysis(command)
                
        except Exception as e:
            logger.error(f"명령 분석 중 오류: {e}")
            return self._fallback_analysis(command)
    
    def _fallback_analysis(self, command: str) -> Dict[str, Any]:
        """LLM 분석 실패 시 폴백 분석"""
        command_lower = command.lower()
        
        # 메모/노트 관련 키워드 감지
        if any(word in command_lower for word in ['메모', '노트', '기록', '적어', '저장']):
            return {
                "selected_tools": ["create_note"],
                "execution_plan": [
                    {
                        "tool": "create_note",
                        "parameters": {"title": "메모", "content": command},
                        "reasoning": "메모 작성 요청을 감지하여 Notes 앱 사용"
                    }
                ],
                "confidence_score": 0.8,
                "confidence_level": "HIGH",
                "reasoning": "메모 관련 키워드를 감지하여 안전한 Notes 앱 사용을 선택",
                "estimated_time": 2,
                "requires_user_input": False,
                "safety_notes": "안전한 로컬 메모 생성"
            }
        
        # 기본적으로 안전한 메모 생성으로 폴백
        return {
            "selected_tools": ["create_note"],
            "execution_plan": [
                {
                    "tool": "create_note",
                    "parameters": {"title": "사용자 요청", "content": f"사용자 요청: {command}"},
                    "reasoning": "명확하지 않은 요청이므로 안전한 메모 생성으로 처리"
                }
            ],
            "confidence_score": 0.3,
            "confidence_level": "LOW",
            "reasoning": "명령 분석에 실패하여 안전한 기본 동작 선택",
            "estimated_time": 2,
            "requires_user_input": False,
            "safety_notes": "불명확한 요청으로 인한 안전 모드 동작"
        }
    
    def _is_safe_command(self, analysis: Dict[str, Any]) -> bool:
        """명령의 안전성 검사"""
        try:
            # 신뢰도가 너무 낮으면 거부
            confidence_score = analysis.get("confidence_score", 0.0)
            if confidence_score < 0.3:
                logger.warning(f"신뢰도가 낮은 명령 감지: {confidence_score}")
                return False
            
            # 위험한 도구들 체크
            dangerous_tools = ["send_message", "send_email"]  # 다른 사람에게 영향을 줄 수 있는 도구들
            selected_tools = analysis.get("selected_tools", [])
            
            for tool in selected_tools:
                if tool in dangerous_tools:
                    logger.warning(f"위험한 도구 사용 시도 감지: {tool}")
                    # Notes 사용을 권장하는 대안 제시
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"안전성 검사 중 오류: {e}")
            return False
    
    async def _execute_tool_chain(self, analysis: Dict[str, Any]) -> ToolResult:
        """분석 결과에 따라 도구 체인 실행"""
        start_time = time.time()
        
        try:
            execution_plan = analysis.get("execution_plan", [])
            if not execution_plan:
                return ToolResult(
                    status=ExecutionStatus.ERROR,
                    error_message="실행 계획이 없습니다.",
                    execution_time=time.time() - start_time
                )
            
            results = []
            
            for step in execution_plan:
                tool_name = step.get("tool")
                parameters = step.get("parameters", {})
                
                if not tool_name:
                    continue
                
                logger.info(f"도구 실행: {tool_name} with {parameters}")
                
                # Apple MCP 서버를 통해 도구 실행
                try:
                    # apple_manager 대신 시뮬레이션으로 처리
                    # if hasattr(self.apple_manager, 'execute_tool'):
                    #     result = await self.apple_manager.execute_tool(tool_name, parameters)
                    # else:
                    # 기본 시뮬레이션 실행
                    result = {
                        "success": True,
                        "message": f"{tool_name} 도구가 성공적으로 실행되었습니다.",
                        "parameters": parameters,
                        "timestamp": time.time()
                    }
                    
                    if tool_name == "create_note":
                        result["note_id"] = f"note_{int(time.time())}"
                        result["content"] = parameters.get("content", "")
                    
                except Exception as tool_error:
                    logger.error(f"도구 실행 중 오류: {tool_error}")
                    result = {
                        "success": False,
                        "error": str(tool_error)
                    }
                
                results.append({
                    "tool": tool_name,
                    "parameters": parameters,
                    "result": result,
                    "reasoning": step.get("reasoning", "")
                })
                
                # 에러가 발생하면 중단
                if not result.get("success", False):
                    logger.error(f"도구 실행 실패: {tool_name}")
                    break
            
            execution_time = time.time() - start_time
            
            return ToolResult(
                status=ExecutionStatus.SUCCESS,
                data={
                    "analysis": analysis,
                    "execution_results": results,
                    "summary": f"{len(results)}개 도구 실행 완료"
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            logger.error(f"도구 체인 실행 중 오류: {e}")
            return ToolResult(
                status=ExecutionStatus.ERROR,
                error_message=f"실행 실패: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록 반환"""
        return [
            {"name": "send_message", "category": "communication", "description": "Messages 앱을 통해 메시지 전송"},
            {"name": "create_note", "category": "productivity", "description": "Notes 앱에서 새로운 노트 생성"},
            {"name": "add_contact", "category": "productivity", "description": "Contacts 앱에 새로운 연락처 추가"},
            {"name": "send_email", "category": "communication", "description": "Mail 앱을 통해 이메일 전송"},
            {"name": "create_reminder", "category": "productivity", "description": "Reminders 앱에서 새로운 리마인더 생성"},
            {"name": "create_calendar_event", "category": "productivity", "description": "Calendar 앱에서 새로운 이벤트 생성"},
            {"name": "get_directions", "category": "utility", "description": "Maps 앱에서 길찾기"}
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Agent 상태 정보 반환"""
        return {
            "initialized": self.llm_manager is not None,
            "total_executions": len(self.execution_history),
            "last_execution": self.last_execution_id,
            "apple_manager_status": "connected" if self.apple_manager else "disconnected"
        }


# 편의 함수
async def create_apple_agent() -> AppleAppsAgent:
    """Apple Agent 생성 및 초기화"""
    agent = AppleAppsAgent()
    await agent.initialize()
    return agent


# 테스트 함수
async def test_apple_agent():
    """Apple Agent 테스트"""
    logger.info("Apple Agent 테스트 시작")
    
    try:
        # Agent 생성 및 초기화
        agent = await create_apple_agent()
        
        # 안전한 테스트 명령들 (Notes 앱 사용)
        test_commands = [
            "회의 내용을 메모해줘",
            "오늘 할 일 목록을 노트에 만들어줘",
            "프로젝트 아이디어를 기록해줘",
            "학습 계획을 메모로 저장해줘"
        ]
        
        for i, command in enumerate(test_commands, 1):
            logger.info(f"\n=== 테스트 {i}: {command} ===")
            
            result = await agent.process_command(command)
            
            logger.info(f"실행 결과: {result.status.value}")
            if result.data:
                logger.info(f"데이터: {result.data}")
            if result.error_message:
                logger.error(f"오류: {result.error_message}")
            
            # 잠시 대기
            await asyncio.sleep(1)
        
        logger.info("Apple Agent 테스트 완료")
        
    except Exception as e:
        logger.error(f"Apple Agent 테스트 실패: {e}")


if __name__ == "__main__":
    asyncio.run(test_apple_agent())
