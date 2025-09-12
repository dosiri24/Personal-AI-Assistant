"""
자연어 기반 계획 실행 모듈

ReAct 엔진의 자연어 기반 실행 - JSON 구조 강제 없이 LLM의 자연스러운 추론 활용
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from ..agent_state import (
    AgentScratchpad, AgentContext, AgentResult, ActionRecord, ObservationRecord, ActionType
)
from ..llm_provider import LLMProvider, ChatMessage
from ...utils.logger import get_logger

logger = get_logger(__name__)


class NaturalPlanningExecutor:
    """
    자연어 기반 계획 실행기
    
    JSON 구조를 강제하지 않고 LLM의 자연스러운 추론 과정을 활용하여
    목표를 달성하는 에이전틱 실행기
    """
    
    def __init__(self, llm_provider: LLMProvider, tool_executor):
        self.llm_provider = llm_provider
        self.tool_executor = tool_executor
        
    def _find_similar_tool(self, target_tool: str, available_tools: List[str]) -> Optional[str]:
        """유사한 도구 이름 찾기"""
        target_lower = target_tool.lower()
        
        # 정확한 매치 먼저 확인
        for tool in available_tools:
            if tool.lower() == target_lower:
                return tool
        
        # 부분 매치 확인
        for tool in available_tools:
            if target_lower in tool.lower() or tool.lower() in target_lower:
                return tool
        
        # 특별한 경우들
        mapping = {
            "notion_todo": ["notion_todo", "notion"],
            "notion": ["notion_todo", "notion_calendar"],
            "time": ["system_time"],
            "calculator": ["calculator", "calc"],
            "filesystem": ["filesystem", "file"],
            "apple_calendar": ["apple_calendar", "calendar"],
            "apple_contacts": ["apple_contacts", "contacts"],
            "apple_notes": ["apple_notes", "notes"],
            "apple_reminders": ["apple_reminders", "reminders"]
        }
        
        for key, candidates in mapping.items():
            if target_lower in key or key in target_lower:
                for candidate in candidates:
                    if candidate in available_tools:
                        return candidate
        
        return None
        
    async def execute_goal(
        self, 
        goal: str, 
        context: AgentContext,
        available_tools: Optional[List[str]] = None
    ) -> AgentResult:
        """
        자연어 목표를 받아서 ReAct 방식으로 실행
        
        Args:
            goal: 자연어로 표현된 목표
            context: 실행 컨텍스트
            available_tools: 사용 가능한 도구 목록
            
        Returns:
            AgentResult: 실행 결과
        """
        
        start_time = time.time()
        scratchpad = AgentScratchpad(goal=goal)
        
        # � 새로운 기능: 자동 작업 분해 및 추적 설정
        scratchpad.auto_detect_and_track_tasks(goal)
        
        # �🔍 실제 등록된 도구 목록 확인
        try:
            if hasattr(self.tool_executor, 'registry') and hasattr(self.tool_executor.registry, 'list_tools'):
                registered_tools = self.tool_executor.registry.list_tools()
                logger.info(f"🛠️ 등록된 도구 목록: {registered_tools}")
                available_tools = registered_tools
            elif available_tools is None:
                available_tools = ["system_time", "calculator"]  # 기본 도구
                logger.warning("⚠️ 도구 레지스트리에서 도구 목록을 가져올 수 없음. 기본 도구 사용")
        except Exception as e:
            logger.error(f"❌ 도구 목록 조회 실패: {e}")
            available_tools = available_tools or ["system_time", "calculator"]
        
        # 초기 상황 설정
        scratchpad.add_thought(f"목표: {goal}")
        scratchpad.add_thought(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if available_tools:
            scratchpad.add_thought(f"사용 가능한 도구: {', '.join(available_tools)}")
        
        iteration_count = 0
        max_iterations = context.max_iterations or 20
        
        # 🔄 반복 루프 추적 시스템
        action_history = []  # 실행된 액션들의 기록
        recent_actions = []  # 최근 몇 개 액션만 추적
        
        while iteration_count < max_iterations:
            iteration_count += 1
            
            # 🚨 무한 루프 감지 및 방지
            if len(recent_actions) >= 3:
                # 최근 3개 액션이 모두 같은 도구를 사용하는지 확인
                recent_tools = [action.get('tool_name') for action in recent_actions[-3:]]
                recent_params = [str(action.get('parameters', {})) for action in recent_actions[-3:]]
                
                if len(set(recent_tools)) == 1 and len(set(recent_params)) <= 2:
                    logger.warning(f"🚨 무한 루프 감지! 최근 3회 동일한 도구 사용: {recent_tools[0]}")
                    
                    # 루프 탈출을 위한 안내 메시지 추가
                    loop_escape_message = f"""
⚠️ 무한 루프가 감지되었습니다. 
최근 3회 연속 같은 도구({recent_tools[0]})를 사용하고 있습니다.
다른 접근 방식을 시도하거나 현재까지의 결과로 답변을 완료해주세요.

현재까지의 관찰사항:
{scratchpad.get_formatted_history()}

목표: {goal}
"""
                    scratchpad.add_thought(loop_escape_message)
            
            # LLM에게 현재 상황을 제시하고 다음 행동 결정 요청
            next_action = await self._get_next_action(goal, scratchpad, context, available_tools)
            
            # 🔄 액션 기록 추가
            current_action = {
                'iteration': iteration_count,
                'action_type': next_action.get("type"),
                'tool_name': next_action.get("tool_name"),
                'parameters': next_action.get("parameters"),
                'content': next_action.get('content', '')[:100]  # 처음 100자만 저장
            }
            action_history.append(current_action)
            recent_actions.append(current_action)
            
            # 최근 액션 기록은 최대 5개만 유지
            if len(recent_actions) > 5:
                recent_actions.pop(0)
            
            if next_action["type"] == "final_answer":
                # 목표 달성 완료
                final_result = next_action["content"]
                scratchpad.add_thought(f"최종 답변: {final_result}")
                scratchpad.finalize(final_result, success=True)
                
                return AgentResult.success_result(
                    answer=final_result,
                    scratchpad=scratchpad,
                    metadata={
                        "iterations": iteration_count,
                        "execution_time": time.time() - start_time,
                        "final_answer": final_result
                    }
                )
                
            elif next_action["type"] == "tool_call":
                # 도구 실행
                tool_name = next_action["tool_name"]
                tool_params = next_action["parameters"]
                reasoning = next_action.get("reasoning", "")
                
                # 🧠 전체 추론 과정을 상세하게 저장 (토큰 제한 없음)
                if reasoning:
                    # 추론이 있으면 상세 정보와 함께 저장
                    detailed_reasoning = f"추론: {reasoning}"
                    if tool_name and tool_params:
                        detailed_reasoning += f"\n선택한 도구: {tool_name}"
                        detailed_reasoning += f"\n매개변수: {json.dumps(tool_params, ensure_ascii=False, indent=2)}"
                    scratchpad.add_thought(detailed_reasoning)
                else:
                    # reasoning이 없으면 더 상세한 추론 정보 생성
                    full_thinking = f"도구 사용 결정: {tool_name} 도구를 선택했습니다."
                    if tool_params:
                        full_thinking += f"\n매개변수 설정: {json.dumps(tool_params, ensure_ascii=False, indent=2)}"
                    full_thinking += f"\n작업 목적: 현재 목표 '{scratchpad.goal}'를 달성하기 위한 단계입니다."
                    scratchpad.add_thought(full_thinking)
                
                # 🔍 도구 이름 검증 및 수정
                if available_tools and tool_name not in available_tools:
                    # 유사한 도구 찾기
                    similar_tool = self._find_similar_tool(tool_name, available_tools)
                    if similar_tool:
                        logger.info(f"🔄 도구 이름 수정: {tool_name} → {similar_tool}")
                        tool_name = similar_tool
                    else:
                        logger.warning(f"⚠️ 도구 '{tool_name}'을 찾을 수 없음. 사용 가능한 도구: {available_tools}")
                        scratchpad.add_thought(f"오류: 도구 '{tool_name}'을 찾을 수 없습니다. 사용 가능한 도구: {', '.join(available_tools)}")
                        continue
                
                # 도구 실행
                result = await self._execute_tool_safely(
                    tool_name, tool_params, scratchpad
                )
                
                # 결과 관찰 - 구체적인 데이터 포함
                if isinstance(result, dict) and 'todos' in result:
                    # Notion 할일 목록인 경우 구체적으로 기록
                    todos = result['todos']
                    if todos:
                        todo_details = []
                        for todo in todos:
                            detail = f"- {todo.get('title', '제목 없음')} ({todo.get('status', '상태 없음')})"
                            if todo.get('due_date'):
                                detail += f" [마감: {todo['due_date'][:10]}]"
                            if todo.get('priority'):
                                detail += f" [우선순위: {todo['priority']}]"
                            if todo.get('id'):
                                detail += f" [ID: {todo['id'][:8]}...]"  # ID 추가 (처음 8자만)
                            todo_details.append(detail)
                        
                        observation_content = f"도구 '{tool_name}' 실행 결과:\n총 {len(todos)}개의 할일이 있습니다:\n" + "\n".join(todo_details)
                        logger.info(f"🔍 구조화된 관찰 내용: {observation_content}")
                    else:
                        observation_content = f"도구 '{tool_name}' 실행 결과: 할일이 없습니다."
                else:
                    observation_content = f"도구 '{tool_name}' 실행 결과: {result}"
                
                scratchpad.add_observation(
                    content=observation_content,
                    success=True if "오류" not in str(result) else False,
                    data=result if isinstance(result, dict) else {"result": result}
                )
                
                logger.info(f"🔍 Scratchpad에 추가된 관찰: {observation_content}")
                
            elif next_action["type"] == "thinking":
                # 순수 추론 단계 - 🧠 전체 추론 과정 상세 저장
                thought = next_action["content"]
                
                # 🔥 사용자 요청: "토큰수 아끼지 말고 띵킹 과정 전체를 다음 띵킹에 넘겨주라"
                # 추론 과정을 상세하게 기록
                detailed_thought = f"추론 단계 {iteration_count}: {thought}"
                
                # 현재 상황과 맥락 정보도 함께 저장
                if scratchpad.steps:
                    last_step = scratchpad.steps[-1]
                    if last_step.observation:
                        detailed_thought += f"\n이전 단계 결과: {last_step.observation.content[:200]}..."
                
                # 현재 목표와의 연관성도 추가
                detailed_thought += f"\n목표 관련성: 현재 '{scratchpad.goal}' 달성을 위한 추론 과정"
                
                scratchpad.add_thought(detailed_thought)
                
                # 🧠 thinking 단계에서도 reasoning_history에 별도 저장
                scratchpad.reasoning_history.append(f"사고 과정: {thought}")
                scratchpad.add_thought(f"분석: {thought}")
                # 별도로 reasoning_history에도 직접 추가하여 맥락 강화
                if hasattr(scratchpad, 'reasoning_history'):
                    scratchpad.reasoning_history.append(f"[사고단계] {thought}")
                
            else:
                # 알 수 없는 행동 타입
                logger.warning(f"알 수 없는 행동 타입: {next_action['type']}")
                scratchpad.add_thought(f"경고: 알 수 없는 행동 - {next_action}")
        
        # 최대 반복 도달
        logger.warning(f"최대 반복 횟수 도달: {max_iterations}")
        partial_result = await self._generate_partial_result(scratchpad, goal)
        scratchpad.finalize(partial_result, success=False)
        
        return AgentResult.max_iterations_result(
            scratchpad=scratchpad,
            metadata={
                "iterations": max_iterations,
                "execution_time": time.time() - start_time,
                "partial_result": partial_result
            }
        )
    
    async def _get_next_action(
        self, 
        goal: str, 
        scratchpad: AgentScratchpad, 
        context: AgentContext,
        available_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        LLM에게 다음 행동을 결정하도록 요청
        
        Args:
            goal: 목표
            scratchpad: 현재까지의 기록
            context: 실행 컨텍스트
            available_tools: 사용 가능한 도구 목록
            
        Returns:
            Dict: 다음 행동 정보
        """
        
        # 현재 상황을 자연어로 구성
        situation_summary = scratchpad.get_formatted_history()
        
        # 이전 thinking 내용 별도 추출 및 요약
        thinking_history = []
        action_history = []
        
        for step in scratchpad.steps:
            if hasattr(step, 'action') and step.action:
                if getattr(step.action, 'action_type', None) == 'thinking':
                    thinking_content = getattr(step.action, 'content', '')
                    if thinking_content and thinking_content not in thinking_history:
                        thinking_history.append(thinking_content)
                elif getattr(step.action, 'action_type', None) == 'tool_call':
                    tool_name = getattr(step.action, 'tool_name', '')
                    action_history.append(tool_name)
        
        # thinking 히스토리가 있으면 상황 요약에 포함
        if thinking_history:
            thinking_summary = "\n".join([f"• {thought[:100]}..." if len(thought) > 100 else f"• {thought}" 
                                        for thought in thinking_history[-3:]])  # 최근 3개만
            situation_summary += f"\n\n📝 이전 추론 과정:\n{thinking_summary}"
        
        # 중복된 행동 패턴 감지
        if len(action_history) >= 3:
            recent_actions = action_history[-3:]
            if len(set(recent_actions)) <= 1:  # 같은 도구를 반복 사용
                situation_summary += f"\n\n⚠️ 주의: '{recent_actions[0]}' 도구를 반복 사용 중입니다. 다른 접근 방법을 고려하세요."
        
        # 🔍 디버깅: scratchpad 내용 확인
        logger.info(f"🔍 Scratchpad 내용 길이: {len(situation_summary)} 문자")
        logger.info(f"🔍 Scratchpad 전체 내용: {situation_summary}")
        
        # 사용 가능한 도구 목록 구성
        tools_info = ""
        if available_tools:
            tools_info = f"""
🛠️ 사용 가능한 도구들:
{chr(10).join([f"- {tool}" for tool in available_tools])}

주요 도구 설명:
- notion_todo: Notion 할일 관리
  * list: {{"action": "list"}} - 할일 목록 조회
  * complete: {{"action": "complete", "target_title": "할일제목"}} - 할일 완료 (제목으로 검색)
  * create: {{"action": "create", "title": "새할일"}} - 할일 추가
- system_time: 시간 정보 조회
  * current: {{"action": "current"}} - 현재 시간 전체 정보
  * date: {{"action": "date"}} - 날짜만
  * time: {{"action": "time"}} - 시간만
  * timezone: {{"action": "timezone"}} - 시간대 정보
- calculator: {{"expression": "계산식"}} - 계산 수행 (예: "2 + 3 * 4", "sqrt(16)")
- filesystem: 파일/디렉토리 작업
  * list: {{"action": "list", "path": "경로"}} - 디렉토리 내용 확인
  * create_dir: {{"action": "create_dir", "path": "경로"}} - 디렉토리 생성
  * copy: {{"action": "copy", "path": "원본", "destination": "대상"}} - 파일/디렉토리 복사
  * move: {{"action": "move", "path": "원본", "destination": "대상"}} - 파일/디렉토리 이동
  * delete: {{"action": "delete", "path": "경로"}} - 파일/디렉토리 삭제
  🚨 중요: filesystem 도구 사용 시 반드시 절대경로 사용!
  ❌ 금지: "Desktop/폴더명" (상대경로) → ✅ 필수: "/Users/taesooa/Desktop/폴더명" (절대경로)
  💡 사용자 바탕화면은 /Users/taesooa/Desktop 입니다
- smart_file_finder: LLM 기반 스마트 파일 검색 (⚠️ action과 description 필수!)
  * find_in_directory: {{"action": "find_in_directory", "description": "찾고자 하는 내용 설명", "directory": "검색할 디렉토리"}} - 특정 디렉토리에서 파일 검색
  * find_directory: {{"action": "find_directory", "description": "찾고자 하는 디렉토리 설명"}} - 디렉토리 검색
- apple_calendar: 애플 캘린더 관리
- apple_contacts: 연락처 관리
- apple_notes: 메모 관리
- apple_reminders: 알림 관리
"""
        
        prompt = f"""
당신은 간결하고 효율적인 AI 어시스턴트입니다. 핵심만 간단히 답변하세요.

**현재 상황:**
{situation_summary}

**중요:** 도구 실행 결과가 있다면 핵심 내용만 간단히 포함하세요.

**🧠 추론 연속성 유지 규칙:**
⚠️ 이전 thinking 단계에서 이미 수행한 추론이 있다면 반드시 참고하세요!
✅ 같은 생각을 반복하지 말고 다음 단계로 진행하세요
📋 추론 히스토리를 기반으로 현재 진행 상황을 파악하고 다음 행동을 결정하세요
🚫 무한루프 방지: 동일한 추론이나 동일한 도구 호출을 반복하지 마세요

{tools_info}

다음 중 하나를 선택하여 응답하세요:

1. 도구 사용이 필요한 경우:
ACTION_TYPE: tool_call
TOOL_NAME: [정확한 도구명]
PARAMETERS: [자연어 또는 JSON]
REASONING: [간단한 이유]

2. 더 생각이 필요한 경우:
ACTION_TYPE: thinking
CONTENT: [간단한 추론 - 이전 thinking과 다른 새로운 관점이나 다음 단계 추론]

**thinking 사용 가이드:**
- 이전에 이미 생각한 내용은 반복하지 마세요
- 새로운 정보나 관점이 필요한 경우에만 사용
- 구체적인 다음 행동 계획을 포함
- 2-3번 이상 연속 thinking은 피하고 실제 행동으로 전환

3. 최종 답변:
ACTION_TYPE: final_answer
CONTENT: [간결한 답변 - 2-3줄 이내]

**답변 가이드:**
- 간단명료하게 답변 (2-3줄 이내)
- 불필요한 인사말이나 설명 제거
- 할일 목록은 제목만 간단히 나열
- 완료/실패 여부만 명확히 전달
- 격식적 표현 최소화

**도구 사용 주의사항:**
⚠️ 절대 이런 실수하지 마세요:
- smart_file_finder에서 query, search_term, search_path 사용 금지! → action, description 필수
- smart_file_finder의 directory 경로: "Desktop/폴더명" 형식으로 사용 (예: "Desktop/논문", "Desktop/Documents")
- filesystem에서 create_directory 금지! → create_dir 사용  
- system_time은 매개변수 필요함! → action 매개변수 필수

🚨 filesystem 경로 필수 규칙 🚨
❌ 절대 금지: "Desktop/폴더명", "Documents/파일명" 같은 상대경로
✅ 반드시 사용: "/Users/taesooa/Desktop/폴더명", "/Users/taesooa/Documents/파일명" 같은 절대경로
⚠️ 상대경로 사용 시 파일이 프로젝트 폴더에 잘못 생성되어 사용자가 찾을 수 없습니다!

정확한 도구명을 사용하고 간결하게 처리하세요.
"""
        
        try:
            messages = [ChatMessage(role="user", content=prompt)]
            response = await self.llm_provider.generate_response(messages, temperature=0.7)
            parsed_response = self._parse_natural_response(response.content)
            
            # 🔍 디버깅: LLM 응답 확인
            logger.info(f"🔍 LLM 원본 응답: {response.content}")
            logger.info(f"🔍 파싱된 응답: {parsed_response}")
            
            return parsed_response
        except Exception as e:
            logger.error(f"LLM 응답 생성 실패: {e}")
            return {
                "type": "thinking",
                "content": f"오류 발생으로 인해 추론 중단: {str(e)}"
            }
    
    def _parse_natural_response(self, response: str) -> Dict[str, Any]:
        """
        LLM의 자연어 응답을 파싱하여 행동 정보 추출
        
        키워드 파싱을 최소화하고 자연어 이해 우선
        """
        
        lines = response.strip().split('\n')
        action_info = {}
        content_started = False
        parameters_started = False
        content_lines = []
        parameters_lines = []
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if line_stripped.startswith('ACTION_TYPE:'):
                action_info['type'] = line_stripped.split(':', 1)[1].strip()
            elif line_stripped.startswith('TOOL_NAME:'):
                action_info['tool_name'] = line_stripped.split(':', 1)[1].strip()
            elif line_stripped.startswith('PARAMETERS:'):
                # PARAMETERS: 이후의 모든 내용을 수집 (JSON 포함)
                first_param = line_stripped.split(':', 1)[1].strip()
                if first_param:
                    parameters_lines.append(first_param)
                parameters_started = True
                content_started = False  # PARAMETERS가 시작되면 CONTENT는 중단
            elif line_stripped.startswith('REASONING:'):
                action_info['reasoning'] = line_stripped.split(':', 1)[1].strip()
                parameters_started = False  # REASONING이 시작되면 PARAMETERS는 중단
                content_started = False
            elif line_stripped.startswith('CONTENT:'):
                # CONTENT: 이후의 모든 내용을 수집
                first_content = line_stripped.split(':', 1)[1].strip()
                if first_content:
                    content_lines.append(first_content)
                content_started = True
                parameters_started = False  # CONTENT가 시작되면 PARAMETERS는 중단
            elif parameters_started:
                # PARAMETERS 섹션의 여러 줄 수집 (JSON 등)
                parameters_lines.append(line.rstrip())
            elif content_started:
                # CONTENT: 이후의 모든 줄을 수집
                content_lines.append(line.rstrip())  # 원본 들여쓰기 보존
        
        # PARAMETERS 조합 및 JSON 파싱 시도
        if parameters_lines:
            params_text = '\n'.join(parameters_lines)
            try:
                # JSON 파싱 시도
                import json
                action_info['parameters'] = json.loads(params_text)
            except:
                # JSON이 아니면 문자열로 처리
                action_info['parameters'] = params_text
        
        # CONTENT 조합
        if content_lines:
            action_info['content'] = '\n'.join(content_lines)
        
        # 기본값 설정
        if 'type' not in action_info:
            # 키워드가 없으면 내용을 분석해서 추론
            if any(word in response.lower() for word in ['도구', 'tool', '실행', 'execute']):
                action_info['type'] = 'tool_call'
            elif any(word in response.lower() for word in ['완료', '답변', 'final', 'answer']):
                action_info['type'] = 'final_answer'
            else:
                action_info['type'] = 'thinking'
        
        if action_info['type'] == 'thinking' and 'content' not in action_info:
            action_info['content'] = response  # 전체 응답을 추론으로 간주
        
        if action_info['type'] == 'final_answer' and 'content' not in action_info:
            action_info['content'] = response  # 전체 응답을 최종 답변으로 간주
        
        return action_info
        
        if action_info['type'] == 'final_answer' and 'content' not in action_info:
            action_info['content'] = response  # 전체 응답을 최종 답변으로 간주
        
        return action_info
    
    async def _execute_tool_safely(
        self, 
        tool_name: str, 
        parameters: Any, 
        scratchpad: AgentScratchpad
    ) -> Any:
        """
        도구를 안전하게 실행하고 결과 반환
        """
        
        try:
            logger.info(f"🔧 도구 실행 시작: {tool_name}")
            logger.info(f"📝 원본 매개변수: {parameters}")
            
            # 매개변수가 자연어인 경우 LLM에게 구조화 요청
            if isinstance(parameters, str):
                structured_params = await self._structure_parameters(tool_name, parameters)
                logger.info(f"🔄 구조화된 매개변수: {structured_params}")
            else:
                structured_params = parameters
                logger.info(f"✅ 이미 구조화된 매개변수 사용")
            
            # 도구 실행
            logger.info(f"🚀 도구 실행 중: {tool_name}({structured_params})")
            result = await self.tool_executor.execute_tool(tool_name, structured_params)
            
            # 결과 로깅
            logger.info(f"📊 도구 실행 결과: 성공={result.result.is_success}")
            if result.result.is_success:
                logger.info(f"✅ 실행 성공: {str(result.result.data)}")
            else:
                logger.error(f"❌ 실행 실패: {result.result.error_message}")
            
            # Scratchpad에 기록
            scratchpad.add_action(
                action_type=ActionType.TOOL_CALL,
                tool_name=tool_name,
                parameters=structured_params
            )
            
            return result.result.data if result.result.is_success else f"오류: {result.result.error_message}"
            
        except Exception as e:
            logger.error(f"❌ 도구 실행 오류: {tool_name} - {e}")
            logger.error(f"📍 오류 상세: {type(e).__name__}: {str(e)}")
            return f"도구 실행 실패: {str(e)}"
    
    async def _structure_parameters(self, tool_name: str, natural_params: Any) -> Dict[str, Any]:
        """
        자연어 매개변수를 구조화된 형태로 변환
        """
        
        try:
            # 이미 딕셔너리 형태라면 그대로 반환
            if isinstance(natural_params, dict):
                return natural_params
                
            # 문자열인 경우 파싱
            if isinstance(natural_params, str):
                # 🎯 도구별 특화된 매개변수 구조화
                if tool_name == "notion_todo":
                    # Notion Todo 도구는 action 매개변수가 필요
                    if "목록" in natural_params or "리스트" in natural_params or "뭐 있어" in natural_params:
                        return {"action": "list"}
                    elif "추가" in natural_params or "만들" in natural_params:
                        return {"action": "create", "title": natural_params}
                    elif "완료" in natural_params or "체크" in natural_params:
                        # 완료 처리 - 먼저 목록에서 ID 찾기 필요
                        if "공지" in natural_params:
                            return {"action": "complete", "target_title": "현대오토에버 공지 재확인"}
                        elif "자료구조" in natural_params:
                            return {"action": "complete", "target_title": "공부노트 자료구조 파트 작업"}
                        elif "부산" in natural_params or "기행문" in natural_params:
                            return {"action": "complete", "target_title": "부산 기행문 작성"}
                        else:
                            # 일반적인 완료 처리 - 제목에서 추출
                            return {"action": "complete", "target_title": natural_params}
                    else:
                        return {"action": "list"}  # 기본값
                        
                elif tool_name == "system_time":
                    # 시간 도구는 매개변수가 필요 없음
                    return {}
                    
                elif tool_name == "filesystem":
                    if "파일" in natural_params or "file" in natural_params.lower():
                        if "생성" in natural_params or "만들" in natural_params:
                            return {"action": "create", "path": natural_params}
                        elif "삭제" in natural_params:
                            return {"action": "delete", "path": natural_params}
                        else:
                            return {"action": "read", "path": natural_params}
                    return {"action": "list", "path": "."}
                    
                elif tool_name == "calculator":
                    return {"expression": natural_params}
                    
                elif tool_name in ["apple_calendar", "apple_contacts", "apple_mail", "apple_messages", "apple_notes", "apple_reminders"]:
                    # Apple 도구들
                    if "목록" in natural_params or "리스트" in natural_params:
                        return {"action": "list"}
                    else:
                        return {"query": natural_params}
                        
                else:
                    # 일반적인 경우 - 자연어 그대로 전달
                    logger.info(f"도구 {tool_name}에 대한 특화된 매개변수 구조화 없음. 일반 형태로 전달")
                    
                    # 기본적인 추론 기반 구조화
                    if "파일" in natural_params or "file" in natural_params.lower():
                        return {"file_path": natural_params}
                    elif "디렉토리" in natural_params or "directory" in natural_params.lower():
                        return {"directory_path": natural_params}
                    elif "쿼리" in natural_params or "query" in natural_params.lower():
                        return {"query": natural_params}
                    else:
                        # 가장 일반적인 입력 필드명들 시도
                        return {"input": natural_params}
            
            # 기타 타입은 문자열로 변환 후 처리
            return {"input": str(natural_params)}
                    
        except Exception as e:
            logger.warning(f"매개변수 구조화 실패 ({tool_name}): {e}")
            return {"input": str(natural_params)}
    
    async def _generate_partial_result(self, scratchpad: AgentScratchpad, goal: str) -> str:
        """부분 결과 생성"""
        
        try:
            summary = scratchpad.get_formatted_history(include_metadata=True)
            
            prompt = f"""
다음은 목표 달성을 위한 진행 상황입니다:

{summary}

최대 반복 횟수에 도달했습니다. 지금까지의 진행 상황을 바탕으로 부분적 결과를 요약해주세요.
"""
            
            messages = [ChatMessage(role="user", content=prompt)]
            response = await self.llm_provider.generate_response(messages, temperature=0.3)
            return response.content
            
        except Exception as e:
            logger.error(f"부분 결과 생성 실패: {e}")
            return f"목표 '{goal}'에 대한 작업이 부분적으로 완료되었습니다."