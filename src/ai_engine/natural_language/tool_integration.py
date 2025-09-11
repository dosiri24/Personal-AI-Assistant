"""
도구 통합 모듈
MCP 도구 시스템과의 연계 및 실제 작업 실행을 담당
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from loguru import logger

from .types import ParsedCommand, IntentType, ExecutionResult, create_error_result, create_success_result
from ..llm_provider import LLMManager
from ...mcp.registry import ToolRegistry
from ...mcp.executor import ToolExecutor
from ...mcp.base_tool import ExecutionStatus


class ToolIntegrator:
    """도구 통합 관리자"""
    
    def __init__(self, llm_manager: LLMManager, tool_registry: ToolRegistry, tool_executor: ToolExecutor):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
    
    async def execute_command(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """파싱된 명령을 실제로 실행합니다"""
        try:
            # 신뢰도가 너무 낮으면 명확화 요청
            if parsed_command.confidence < 0.7:
                return ExecutionResult(
                    status="clarification_needed",
                    message=f"요청을 더 명확히 해주실 수 있나요? (신뢰도: {parsed_command.confidence:.2f})",
                    clarifications=parsed_command.clarification_needed
                )
            
            # 의도별 작업 실행
            if parsed_command.intent == IntentType.TASK_MANAGEMENT:
                return await self._execute_todo_task(parsed_command, user_id, context)
            elif parsed_command.intent == IntentType.INFORMATION_SEARCH:
                return await self._execute_search_task(parsed_command, user_id, context)
            elif parsed_command.intent == IntentType.FILE_MANAGEMENT:
                return await self._execute_file_task(parsed_command, user_id, context)
            elif parsed_command.intent == IntentType.WEB_SCRAPING:
                return await self._execute_web_scraping_task(parsed_command, user_id, context)
            else:
                return ExecutionResult(
                    status="not_implemented",
                    message=f"'{parsed_command.intent.value}' 타입의 작업은 아직 구현되지 않았습니다."
                )
                
        except Exception as e:
            logger.error(f"명령 실행 중 오류: {e}")
            return create_error_result(f"명령 실행 중 오류가 발생했습니다: {str(e)}")
    
    async def _execute_todo_task(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """Todo 관련 작업 실행"""
        try:
            # Notion Todo 도구 찾기
            todo_tool = await self.tool_registry.get_tool("notion_todo")
            if not todo_tool:
                return create_error_result("Notion Todo 도구를 찾을 수 없습니다.")
            
            # 자연어에서 Todo 파라미터 추출 (에이전틱 방식)
            todo_params = await self._extract_todo_params(parsed_command)
            
            # Todo 생성 실행 - 표준 BaseTool 인터페이스 사용
            try:
                result = await todo_tool.execute({
                    "action": "create",
                    **todo_params
                })
                
                if result.status == ExecutionStatus.SUCCESS:
                    return create_success_result(
                        f"✅ '{todo_params['title']}' 할일이 Notion에 추가되었습니다!",
                        result.data
                    )
                else:
                    return create_error_result(f"❌ Todo 생성 실패: {result.error_message or '알 수 없는 오류'}")
            except Exception as tool_error:
                logger.error(f"도구 실행 중 오류: {tool_error}")
                return create_error_result(f"❌ 도구 실행 실패: {str(tool_error)}")
                
        except Exception as e:
            logger.error(f"Todo 작업 실행 중 오류: {e}")
            return create_error_result(f"Todo 작업 실행 중 오류: {str(e)}")
    
    async def _extract_todo_params(self, parsed_command: ParsedCommand) -> Dict[str, Any]:
        """LLM을 사용하여 자연어에서 Todo 파라미터를 에이전틱하게 추출"""
        try:
            # 에이전틱 Todo 파라미터 추출 프롬프트
            extraction_prompt = f"""
당신은 자연어 텍스트에서 할일(Todo) 정보를 추출하는 전문가입니다.

사용자 요청: "{parsed_command.original_text}"

위 텍스트에서 다음 정보를 추출하여 JSON 형식으로 응답해주세요:

1. **title**: 실제 할일 내용 (명령어나 요청 표현 제거)
2. **priority**: 우선순위 (high/medium/low)
3. **due_date**: 마감일 (YYYY-MM-DD 형식, 상대적 표현을 절대 날짜로 변환)
4. **description**: 추가 설명이나 맥락
5. **tags**: 관련 태그들

**분석 규칙:**
- "할일을 추가해줘", "Notion에 넣어줘" 같은 명령어는 title에서 제외
- "높은 우선순위", "중요한" → priority: "high"
- "보통", "일반적인" → priority: "medium"  
- "낮은", "여유있는" → priority: "low"
- "내일", "tomorrow" → 내일 날짜로 변환
- "프로젝트", "문서" 같은 키워드는 tags에 포함

**현재 날짜**: {datetime.now().strftime("%Y-%m-%d")}

**응답 형식:**
```json
{{
    "title": "실제 할일 내용",
    "priority": "high|medium|low",
    "due_date": "YYYY-MM-DD 또는 null",
    "description": "추가 설명 또는 null",
    "tags": ["태그1", "태그2"]
}}
```
"""

            # LLM에게 파라미터 추출 요청
            messages = [{"role": "user", "content": extraction_prompt}]
            response = await self.llm_manager.generate_response(messages, temperature=0.3)
            
            # JSON 응답 파싱
            extracted_data = self._extract_json_from_response(response.content)
            
            # 안전한 기본값 설정
            params = {
                "title": extracted_data.get("title", "새로운 할일"),
                "priority": extracted_data.get("priority", "medium"),
                "due_date": extracted_data.get("due_date"),
                "description": extracted_data.get("description"),
                "tags": extracted_data.get("tags", [])
            }
            
            # due_date 처리
            if params["due_date"] and isinstance(params["due_date"], str):
                params["due_date"] = self._process_due_date(params["due_date"])
            
            logger.info(f"에이전틱 Todo 파라미터 추출 완료: {params}")
            return params
            
        except Exception as e:
            logger.error(f"에이전틱 Todo 파라미터 추출 실패: {e}")
            # 실패시 안전한 기본값 반환
            return {
                "title": "새로운 할일",
                "priority": "medium",
                "due_date": None,
                "description": None,
                "tags": []
            }
    
    def _process_due_date(self, due_date_str: str) -> str:
        """날짜 문자열 처리"""
        try:
            today = datetime.now()
            
            # 이미 YYYY-MM-DD 형식인 경우
            if len(due_date_str) == 10 and due_date_str.count('-') == 2:
                return due_date_str
            
            # 상대적 날짜 처리
            if "내일" in due_date_str or "tomorrow" in due_date_str.lower():
                tomorrow = today + timedelta(days=1)
                return tomorrow.strftime("%Y-%m-%d")
            elif "모레" in due_date_str:
                day_after_tomorrow = today + timedelta(days=2)
                return day_after_tomorrow.strftime("%Y-%m-%d")
            elif "다음주" in due_date_str:
                next_week = today + timedelta(days=7)
                return next_week.strftime("%Y-%m-%d")
            
            return due_date_str
        except Exception:
            return due_date_str
    
    async def _execute_search_task(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """검색 관련 작업 실행"""
        # 웹 검색 도구 찾기
        search_tool = await self.tool_registry.get_tool("web_search")
        if not search_tool:
            return create_error_result("웹 검색 도구를 찾을 수 없습니다.")
        
        return ExecutionResult(
            status="not_implemented",
            message="검색 기능은 아직 구현되지 않았습니다."
        )
    
    async def _execute_file_task(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """파일 관리 작업 실행"""
        # 파일 시스템 도구 찾기
        file_tool = await self.tool_registry.get_tool("filesystem")
        if not file_tool:
            return create_error_result("파일 시스템 도구를 찾을 수 없습니다.")
        
        return ExecutionResult(
            status="not_implemented",
            message="파일 관리 기능은 아직 구현되지 않았습니다."
        )
    
    async def _execute_web_scraping_task(
        self,
        parsed_command: ParsedCommand,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """웹 스크래핑 작업 실행"""
        # 웹 스크래핑 도구 찾기
        scraping_tool = await self.tool_registry.get_tool("web_scraper")
        if not scraping_tool:
            return create_error_result("웹 스크래핑 도구를 찾을 수 없습니다.")
        
        return ExecutionResult(
            status="not_implemented",
            message="웹 스크래핑 기능은 아직 구현되지 않았습니다."
        )
    
    def _extract_json_from_response(self, response_text: str) -> Dict[str, Any]:
        """응답에서 JSON 추출"""
        import re
        import json
        
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
    
    async def get_available_tools(self) -> List[str]:
        """사용 가능한 도구 목록 반환"""
        try:
            tools = await self.tool_registry.list_tools()
            return [tool.name for tool in tools]
        except Exception as e:
            logger.error(f"도구 목록 조회 중 오류: {e}")
            return []
    
    async def validate_tool_availability(self, required_tools: List[str]) -> Dict[str, bool]:
        """필요한 도구들의 사용 가능성 검증"""
        availability = {}
        
        for tool_name in required_tools:
            try:
                tool = await self.tool_registry.get_tool(tool_name)
                availability[tool_name] = tool is not None
            except Exception as e:
                logger.error(f"도구 {tool_name} 확인 중 오류: {e}")
                availability[tool_name] = False
        
        return availability
