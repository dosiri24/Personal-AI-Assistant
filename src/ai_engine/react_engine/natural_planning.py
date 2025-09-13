"""
자연어 기반 계획 실행 모듈

ReAct 엔진의 자연어 기반 실행 - JSON 구조 강제 없이 LLM의 자연스러운 추론 활용
"""

import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from ..agent_state import (
    AgentScratchpad, AgentContext, AgentResult, ActionRecord, ObservationRecord, ActionType
)
from ..llm_provider import LLMProvider, ChatMessage
from ..task_canvas import ExternalTaskCanvas, TaskStatus, TaskStep, TaskCanvas
from ...utils.logger import get_logger

logger = get_logger(__name__)


class TaskCheckpoint:
    """작업 체크포인트 관리"""
    
    def __init__(self, goal: str):
        self.goal = goal
        self.checkpoints = []
        self.completed_tasks = []
        self.current_status = "시작"
        
    def add_checkpoint(self, description: str, status: str = "대기중"):
        """체크포인트 추가"""
        checkpoint = {
            "id": len(self.checkpoints) + 1,
            "description": description,
            "status": status,  # 대기중, 진행중, 완료, 실패
            "timestamp": datetime.now().isoformat()
        }
        self.checkpoints.append(checkpoint)
        return checkpoint["id"]
    
    def update_checkpoint(self, checkpoint_id: int, status: str, details: str = ""):
        """체크포인트 상태 업데이트"""
        for checkpoint in self.checkpoints:
            if checkpoint["id"] == checkpoint_id:
                checkpoint["status"] = status
                checkpoint["updated"] = datetime.now().isoformat()
                if details:
                    checkpoint["details"] = details
                
                if status == "완료":
                    self.completed_tasks.append(checkpoint["description"])
                break
    
    def get_progress_summary(self) -> str:
        """진행 상황 요약"""
        total = len(self.checkpoints)
        completed = len([c for c in self.checkpoints if c["status"] == "완료"])
        in_progress = len([c for c in self.checkpoints if c["status"] == "진행중"])
        
        summary = f"📋 **작업 진행 상황** ({completed}/{total} 완료)\n\n"
        
        for checkpoint in self.checkpoints:
            status_icon = {
                "대기중": "⏳",
                "진행중": "🔄", 
                "완료": "✅",
                "실패": "❌"
            }.get(checkpoint["status"], "❓")
            
            summary += f"{status_icon} {checkpoint['description']}\n"
            if checkpoint.get("details"):
                summary += f"   └─ {checkpoint['details']}\n"
        
        return summary
    
    def get_next_task(self) -> Optional[Dict]:
        """다음 수행할 작업 반환"""
        for checkpoint in self.checkpoints:
            if checkpoint["status"] in ["대기중", "진행중"]:
                return checkpoint
        return None
    
    def is_complete(self) -> bool:
        """모든 작업이 완료되었는지 확인"""
        return all(c["status"] in ["완료", "건너뜀"] for c in self.checkpoints)


class NaturalPlanningExecutor:
    """
    자연어 기반 계획 실행기
    
    JSON 구조를 강제하지 않고 LLM의 자연스러운 추론 과정을 활용하여
    목표를 달성하는 에이전틱 실행기
    """
    
    def __init__(self, llm_provider: LLMProvider, tool_executor):
        self.llm_provider = llm_provider
        self.tool_executor = tool_executor
        self.canvas_manager = ExternalTaskCanvas()  # 외부 캔버스 관리자 추가
        
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
        
        # 🎯 외부 캔버스 시스템 연동
        existing_canvas = self.canvas_manager.find_existing_canvas(goal)
        
        if existing_canvas:
            logger.info(f"📋 기존 캔버스 발견: {existing_canvas.canvas_id}")
            logger.info(f"📊 진행률: {existing_canvas.completion_percentage:.1f}%")
            canvas = existing_canvas
            
            # 이미 완료된 작업인지 확인
            if canvas.status == TaskStatus.COMPLETED:
                summary = self.canvas_manager.generate_progress_summary(canvas)
                return AgentResult(
                    success=True,
                    result=f"✅ 이미 완료된 작업입니다.\n\n{summary}",
                    execution_time=time.time() - start_time,
                    iterations=0,
                    tool_calls=0
                )
        else:
            # 새로운 캔버스 생성
            logger.info(f"📋 새로운 작업 캔버스 생성")
            
            # 초기 계획 수립
            initial_steps = await self._create_initial_plan_for_canvas(goal, available_tools)
            canvas = self.canvas_manager.create_canvas(goal, initial_steps)
            logger.info(f"📋 캔버스 생성 완료: {canvas.canvas_id}")
        
        # 🎯 체크포인트 기반 작업 관리 (기존 캔버스와 연동)
        checkpoints = TaskCheckpoint(goal)
        if existing_canvas:
            checkpoints.checkpoints = self._convert_canvas_to_checkpoints(canvas)
        
        # �️ 실제 등록된 도구 목록 확인
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
            available_tools = available_tools or ["system_time", "calculator", "filesystem", "system_explorer"]

        # 📋 캔버스가 새로 생성된 경우에만 초기 계획 수립
        if not existing_canvas:
            initial_plan = await self._create_initial_plan(goal, available_tools, checkpoints)
        
        # 초기 상황 설정  
        scratchpad.add_thought(f"목표: {goal}")
        scratchpad.add_thought(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if available_tools:
            scratchpad.add_thought(f"사용 가능한 도구: {', '.join(available_tools)}")
        
        # 📋 계획과 체크포인트 정보 추가
        scratchpad.add_thought(f"수립된 계획:\n{checkpoints.get_progress_summary()}")
        
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
                    
                    # 현재 체크포인트 상태 확인 후 요약 생성
                    final_summary = self._generate_checkpoint_summary(checkpoints)
                    from src.ai_engine.goal_manager import GoalResult
                    return GoalResult(success=True, result=final_summary)
                    return GoalResult(success=True, result=final_summary)
            
            # Scratchpad 크기 제한 (토큰 절약)
            if scratchpad.get_total_length() > 15000:  # 15KB 제한
                logger.warning("Scratchpad 크기 제한 초과, 이전 내용 압축")
                scratchpad.compress_history()
            
            # LLM에게 현재 상황을 제시하고 다음 행동 결정 요청
            next_action = await self._get_next_action(goal, scratchpad, context, available_tools, checkpoints)
            
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
                
                # 🎯 캔버스와 체크포인트 기반 최종 답변 생성
                self._sync_checkpoints_to_canvas(checkpoints, canvas)
                canvas_summary = self.canvas_manager.generate_progress_summary(canvas)
                checkpoint_summary = checkpoints.get_progress_summary()
                
                # 캔버스 요약을 우선적으로 사용하고, 체크포인트는 백업으로 활용
                enhanced_result = f"{final_result}\n\n{canvas_summary}"
                
                # 캔버스를 완료 상태로 마킹
                canvas.status = TaskStatus.COMPLETED
                self.canvas_manager._save_canvas(canvas)
                
                scratchpad.add_thought(f"최종 답변: {enhanced_result}")
                scratchpad.finalize(enhanced_result, success=True)
                
                return AgentResult.success_result(
                    answer=enhanced_result,
                    scratchpad=scratchpad,
                    metadata={
                        "iterations": iteration_count,
                        "execution_time": time.time() - start_time,
                        "final_answer": enhanced_result,
                        "checkpoints": checkpoints.checkpoints,
                        "canvas_id": canvas.canvas_id,
                        "canvas_progress": canvas.completion_percentage
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
                
                # 🎯 캔버스 시스템에 도구 실행 결과 반영
                action_type = tool_params.get('action', 'unknown') if isinstance(tool_params, dict) else 'unknown'
                success = "오류" not in str(result)
                self._update_canvas_on_tool_execution(canvas, tool_name, action_type, result, success)
                
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
                
                # 🎯 체크포인트와 캔버스 동기화: 성공한 작업을 반영
                if "오류" not in str(result) and result:
                    await self._update_checkpoints_on_success(checkpoints, next_action, result)
                    self._sync_checkpoints_to_canvas(checkpoints, canvas)
                
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
        available_tools: Optional[List[str]] = None,
        checkpoints: Optional[TaskCheckpoint] = None
    ) -> Dict[str, Any]:
        """
        LLM에게 다음 행동을 결정하도록 요청
        
        Args:
            goal: 목표
            scratchpad: 현재까지의 기록
            context: 실행 컨텍스트
            available_tools: 사용 가능한 도구 목록
            checkpoints: 작업 체크포인트
            
        Returns:
            Dict: 다음 행동 정보
        """
        
        # 현재 상황을 자연어로 구성
        situation_summary = scratchpad.get_formatted_history()
        
        # 체크포인트 진행 상황 추가
        checkpoint_info = ""
        if checkpoints:
            checkpoint_info = f"\n\n📋 **현재 작업 진행 상황:**\n{checkpoints.get_progress_summary()}"
            
            # 다음 수행할 작업 확인
            next_task = checkpoints.get_next_task()
            if next_task:
                checkpoint_info += f"\n🎯 **다음 수행할 작업:** {next_task['description']}"
        
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
        
        # 간단한 도구 목록 (토큰 절약)
        available_tools_list = ", ".join(available_tools) if available_tools else "없음"
        
        prompt = f"""목표: {goal}

현재 상황:
{situation_summary}{checkpoint_info}

사용 가능한 도구: {available_tools_list}

다음 행동을 선택하세요:
- tool_call: 도구 사용
- final_answer: 최종 답변

응답 형식:
ACTION_TYPE: tool_call 또는 final_answer
TOOL_NAME: 도구명 (tool_call인 경우)
PARAMETERS: {{"key": "value"}} (tool_call인 경우)  
CONTENT: 답변 내용 (final_answer인 경우)
REASONING: 간단한 이유"""

        try:
            messages = [ChatMessage(role="user", content=prompt)]
            response = await self.llm_provider.generate_response(messages, temperature=0.7)
            parsed_response = self._parse_llm_response(response.content)
            
            # 응답 로깅
            logger.info(f"🔍 LLM 원본 응답: {response.content}")
            logger.info(f"🔍 파싱된 응답: {parsed_response}")
            
            return parsed_response
        except Exception as e:
            logger.error(f"LLM 응답 생성 실패: {e}")
            return {
                "type": "thinking",
                "content": f"오류 발생으로 인해 추론 중단: {str(e)}"
            }
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
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
    
    def _generate_loop_escape_summary(self, goal: str, scratchpad: AgentScratchpad) -> str:
        """무한 루프 탈출을 위한 요약 생성"""
        try:
            # 최근 성공한 작업들 추출
            history = scratchpad.get_formatted_history()
            successful_actions = []
            
            for line in history.split('\n'):
                if '✅' in line and ('성공' in line or '완료' in line):
                    successful_actions.append(line.strip())
            
            if successful_actions:
                summary = f"목표 '{goal}'에 대해 다음 작업들이 성공적으로 완료되었습니다:\n"
                for action in successful_actions[-3:]:  # 최근 3개만
                    summary += f"• {action}\n"
                summary += "\n요청하신 작업이 완료되었습니다."
            else:
                summary = f"목표 '{goal}'에 대한 작업을 시도했으나, 일부 제약사항으로 인해 완전히 완료하지 못했습니다."
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"루프 탈출 요약 생성 실패: {e}")
            return f"목표 '{goal}'에 대한 작업이 처리되었습니다."
    
    async def _create_initial_plan(self, goal: str, available_tools: List[str], checkpoints: TaskCheckpoint) -> str:
        """목표를 분석하여 초기 계획 및 체크포인트 생성"""
        try:
            # LLM에게 목표 분석 및 계획 수립 요청
            analysis_prompt = f"""
목표: {goal}

사용 가능한 도구: {', '.join(available_tools)}

이 목표를 달성하기 위한 세부 단계들을 분석하고 나열해주세요.
각 단계는 구체적이고 실행 가능해야 합니다.

응답 형식:
1. [단계 설명]
2. [단계 설명]
3. [단계 설명]
...

예시 응답:
1. 바탕화면 파일 목록 확인
2. 스크린샷 파일 식별
3. 식별된 스크린샷 파일들 삭제
4. 삭제 완료 확인
"""
            
            messages = [ChatMessage(
                role="user",
                content=analysis_prompt
            )]
            
            response = await self.llm_provider.generate_response(
                messages=messages,
                max_tokens=1024,
                temperature=0.3
            )
            
            plan_text = response.content.strip()
            
            # 계획에서 각 단계를 추출하여 체크포인트로 생성
            steps = []
            for line in plan_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # 번호나 불릿 포인트 제거
                    step_text = line
                    for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '-', '•', '*']:
                        if step_text.startswith(prefix):
                            step_text = step_text[len(prefix):].strip()
                            break
                    
                    if step_text:
                        steps.append(step_text)
                        checkpoints.add_checkpoint(step_text, "대기중")
            
            logger.info(f"📋 계획 수립 완료: {len(steps)}개 단계 생성")
            return plan_text
            
        except Exception as e:
            logger.error(f"초기 계획 수립 실패: {e}")
            # 기본 계획 생성
            default_steps = [
                "목표 상황 파악",
                "필요한 도구 선택", 
                "작업 실행",
                "결과 확인"
            ]
            for step in default_steps:
                checkpoints.add_checkpoint(step, "대기중")
            return "기본 작업 계획이 수립되었습니다."
    
    def _generate_checkpoint_summary(self, checkpoints: TaskCheckpoint) -> str:
        """체크포인트 기반 최종 요약 생성"""
        try:
            completed_tasks = [c for c in checkpoints.checkpoints if c["status"] == "완료"]
            
            if completed_tasks:
                summary = f"목표 '{checkpoints.goal}'에 대해 다음 작업들이 완료되었습니다:\n\n"
                summary += checkpoints.get_progress_summary()
                summary += "\n\n요청하신 작업이 처리되었습니다."
            else:
                summary = f"목표 '{checkpoints.goal}'에 대한 작업을 시도했으나, 완료되지 못한 단계들이 있습니다:\n\n"
                summary += checkpoints.get_progress_summary()
                
            return summary
            
        except Exception as e:
            logger.error(f"체크포인트 요약 생성 실패: {e}")
            return f"목표 '{checkpoints.goal}'에 대한 작업이 처리되었습니다."
    
    async def _update_checkpoints_on_success(self, checkpoints: TaskCheckpoint, action: Dict, result: Any):
        """성공한 도구 실행에 따른 체크포인트 상태 업데이트"""
        try:
            tool_name = action.get("tool_name", "")
            action_type = action.get("parameters", {}).get("action", "")
            
            # 도구별 성공 패턴에 따른 체크포인트 업데이트
            if tool_name == "filesystem":
                if action_type == "list":
                    # 파일 목록 조회 성공
                    for checkpoint in checkpoints.checkpoints:
                        if any(keyword in checkpoint["description"].lower() for keyword in ["목록", "확인", "파악"]):
                            if checkpoint["status"] == "대기중":
                                checkpoints.update_checkpoint(checkpoint["id"], "완료", "파일 목록 조회 완료")
                                break
                
                elif action_type == "delete":
                    # 파일 삭제 성공
                    if isinstance(result, dict) and "삭제 완료" in str(result):
                        for checkpoint in checkpoints.checkpoints:
                            if any(keyword in checkpoint["description"].lower() for keyword in ["삭제", "제거"]):
                                if checkpoint["status"] in ["대기중", "진행중"]:
                                    checkpoints.update_checkpoint(checkpoint["id"], "완료", f"파일 삭제 완료")
                                    break
            
            # 스크린샷 관련 특별 처리
            if "스크린샷" in checkpoints.goal:
                if tool_name == "filesystem" and action_type == "list":
                    # 스크린샷 파일 식별
                    if isinstance(result, dict) and "items" in result:
                        screenshot_files = [item for item in result["items"] if "스크린샷" in item.get("name", "")]
                        if screenshot_files:
                            for checkpoint in checkpoints.checkpoints:
                                if "식별" in checkpoint["description"]:
                                    checkpoints.update_checkpoint(checkpoint["id"], "완료", f"{len(screenshot_files)}개 스크린샷 파일 발견")
                                    break
                        else:
                            for checkpoint in checkpoints.checkpoints:
                                if "식별" in checkpoint["description"]:
                                    checkpoints.update_checkpoint(checkpoint["id"], "완료", "스크린샷 파일이 없음을 확인")
                                    break
            
            # 로그에 체크포인트 업데이트 상황 출력
            logger.info(f"📋 체크포인트 업데이트 완료:\n{checkpoints.get_progress_summary()}")
            
        except Exception as e:
            logger.error(f"체크포인트 업데이트 실패: {e}")
    
    # ========== 외부 캔버스 시스템 관련 메서드들 ==========
    
    async def _create_initial_plan_for_canvas(self, goal: str, available_tools: List[str]) -> List[Dict]:
        """외부 캔버스용 초기 계획 수립"""
        try:
            # 도구가 없으면 기본 도구 목록 사용
            if not available_tools:
                available_tools = ["system_time", "calculator", "filesystem", "system_explorer"]
                
            tools_text = ', '.join(available_tools) if available_tools else "기본 도구"
            
            messages = [
                ChatMessage(role="system", content=f"""
당신은 작업 계획 전문가입니다. 사용자의 목표를 분석하여 실행 가능한 단계별 계획을 세워주세요.

사용 가능한 도구: {tools_text}

각 단계는 다음과 같은 형태로 작성해주세요:
1. 단계 제목: 간단명료한 작업명
2. 단계 설명: 구체적인 실행 내용

최대 6단계 이내로 계획을 세워주세요.
"""),
                ChatMessage(role="user", content=f"목표: {goal}")
            ]
            
            response = await self.llm_provider.generate_response(
                messages=messages,
                temperature=0.3,
                max_tokens=1024
            )
            
            plan_text = response.content.strip()
            steps = []
            
            # 계획에서 각 단계를 추출
            for line in plan_text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # 번호나 불릿 포인트 제거
                    step_text = line
                    for prefix in ['1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '-', '•', '*']:
                        if step_text.startswith(prefix):
                            step_text = step_text[len(prefix):].strip()
                            break
                    
                    if step_text and ':' in step_text:
                        title, description = step_text.split(':', 1)
                        steps.append({
                            'title': title.strip(),
                            'description': description.strip()
                        })
                    elif step_text:
                        steps.append({
                            'title': step_text,
                            'description': ''
                        })
            
            if not steps:
                # 기본 단계 생성
                steps = [
                    {'title': '상황 파악', 'description': '현재 상태 확인'},
                    {'title': '작업 실행', 'description': '목표 달성을 위한 작업 수행'},
                    {'title': '결과 확인', 'description': '작업 완료 상태 검증'}
                ]
            
            logger.info(f"📋 캔버스용 계획 수립 완료: {len(steps)}개 단계")
            return steps
            
        except Exception as e:
            logger.error(f"캔버스 계획 수립 실패: {e}")
            return [
                {'title': '상황 파악', 'description': '현재 상태 확인'},
                {'title': '작업 실행', 'description': '목표 달성을 위한 작업 수행'},
                {'title': '결과 확인', 'description': '작업 완료 상태 검증'}
            ]
    
    def _convert_canvas_to_checkpoints(self, canvas: TaskCanvas) -> List[Dict]:
        """캔버스의 단계를 체크포인트 형식으로 변환"""
        checkpoints = []
        
        for step in canvas.steps:
            # TaskStatus를 기존 체크포인트 상태로 변환
            status_mapping = {
                TaskStatus.PENDING: "대기중",
                TaskStatus.IN_PROGRESS: "진행중", 
                TaskStatus.COMPLETED: "완료",
                TaskStatus.FAILED: "실패",
                TaskStatus.SKIPPED: "건너뜀"
            }
            
            checkpoint = {
                "id": step.id,
                "description": f"{step.title}: {step.description}",
                "status": status_mapping.get(step.status, "대기중"),
                "details": step.result or ""
            }
            checkpoints.append(checkpoint)
        
        return checkpoints
    
    def _sync_checkpoints_to_canvas(self, checkpoints: TaskCheckpoint, canvas: TaskCanvas):
        """체크포인트 상태를 캔버스에 동기화"""
        status_mapping = {
            "대기중": TaskStatus.PENDING,
            "진행중": TaskStatus.IN_PROGRESS,
            "완료": TaskStatus.COMPLETED,
            "실패": TaskStatus.FAILED,
            "건너뜀": TaskStatus.SKIPPED
        }
        
        for checkpoint in checkpoints.checkpoints:
            step_id = checkpoint["id"]
            new_status = status_mapping.get(checkpoint["status"], TaskStatus.PENDING)
            result = checkpoint.get("details", "")
            
            self.canvas_manager.update_step_status(
                canvas=canvas,
                step_id=step_id,
                status=new_status,
                result=result
            )
    
    def _update_canvas_on_tool_execution(self, canvas: TaskCanvas, tool_name: str, 
                                       action_type: str, result: Any, success: bool):
        """도구 실행 결과를 캔버스에 반영"""
        try:
            # 현재 진행 중인 단계 찾기
            current_step = self.canvas_manager.get_next_pending_step(canvas)
            if not current_step:
                return
            
            if success:
                # 성공적인 도구 실행을 단계에 기록
                tool_call = {
                    'tool': tool_name,
                    'action': action_type,
                    'timestamp': datetime.now().isoformat(),
                    'success': True
                }
                
                # 특정 조건에서 단계 완료 처리
                should_complete = False
                completion_result = ""
                
                if "파일 목록" in current_step.title or "조회" in current_step.title:
                    if tool_name == "filesystem" and action_type == "list":
                        should_complete = True
                        completion_result = "파일 목록 조회 완료"
                
                elif "삭제" in current_step.title:
                    if tool_name == "filesystem" and action_type == "delete":
                        should_complete = True
                        completion_result = "파일 삭제 완료"
                
                elif "식별" in current_step.title or "확인" in current_step.title:
                    if isinstance(result, dict) and "items" in result:
                        # 파일 목록에서 특정 파일 식별
                        should_complete = True
                        completion_result = "파일 식별 완료"
                
                # 단계 상태 업데이트
                if should_complete:
                    self.canvas_manager.update_step_status(
                        canvas=canvas,
                        step_id=current_step.id,
                        status=TaskStatus.COMPLETED,
                        result=completion_result,
                        tool_call=tool_call
                    )
                else:
                    # 진행 중 상태로 업데이트
                    self.canvas_manager.update_step_status(
                        canvas=canvas,
                        step_id=current_step.id,
                        status=TaskStatus.IN_PROGRESS,
                        tool_call=tool_call
                    )
            else:
                # 실패한 경우 오류 기록
                self.canvas_manager.update_step_status(
                    canvas=canvas,
                    step_id=current_step.id,
                    status=TaskStatus.FAILED,
                    error=str(result)
                )
                
        except Exception as e:
            logger.error(f"캔버스 업데이트 실패: {e}")