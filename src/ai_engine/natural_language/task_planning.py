"""
작업 계획 모듈
파싱된 명령을 바탕으로 실행 가능한 단계별 작업 계획을 생성하고 관리
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from loguru import logger

from .types import ParsedCommand, TaskPlan
from ..llm_provider import LLMManager
from ..prompt_templates import PromptTemplateManager


class TaskPlanner:
    """작업 계획 생성기"""
    
    def __init__(self, llm_manager: LLMManager, prompt_manager: PromptTemplateManager):
        self.llm_manager = llm_manager
        self.prompt_manager = prompt_manager
    
    async def create_task_plan(
        self,
        parsed_command: ParsedCommand,
        available_tools: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """기본 작업 계획 생성"""
        try:
            # 기본 계획에서 상세 계획 생성
            action_plan = parsed_command.metadata.get("action_plan", [])
            
            return TaskPlan(
                goal=parsed_command.metadata.get("goal", parsed_command.original_text),
                steps=action_plan,
                required_tools=parsed_command.requires_tools,
                estimated_duration=self._estimate_duration(parsed_command.metadata.get("difficulty", "medium")),
                difficulty=parsed_command.metadata.get("difficulty", "medium"),
                confidence=parsed_command.confidence,
                dependencies=[]
            )
            
        except Exception as e:
            logger.error(f"작업 계획 생성 중 오류: {e}")
            # 기본 계획 반환
            return TaskPlan(
                goal=parsed_command.original_text,
                steps=[{"step": 1, "action": "사용자 명령 실행", "tool": "manual"}],
                required_tools=parsed_command.requires_tools,
                estimated_duration="알 수 없음",
                difficulty="medium",
                confidence=0.5,
                dependencies=[]
            )
    
    async def create_context_aware_task_plan(
        self,
        user_command: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskPlan:
        """컨텍스트 인식 작업 계획 생성"""
        try:
            # 컨텍스트 인식 계획 수립 프롬프트 사용
            variables = {
                "user_command": user_command,
                "current_time": datetime.now().isoformat(),
                "user_context": context or {},
                "system_capabilities": ["일정관리", "파일조작", "정보검색", "자동화"]
            }
            
            prompt_text = self.prompt_manager.render_template(
                "context_aware_planning", 
                variables
            )
            
            # AI 응답 생성
            messages = [{"role": "user", "content": prompt_text}]
            response = await self.llm_manager.generate_response(messages, temperature=0.4)
            
            # 응답 파싱
            plan_data = self._extract_json_from_response(response.content)
            
            return TaskPlan(
                goal=plan_data.get("goal", ""),
                steps=plan_data.get("steps", []),
                required_tools=plan_data.get("required_tools", []),
                estimated_duration=plan_data.get("estimated_duration"),
                difficulty=plan_data.get("difficulty", "medium"),
                confidence=plan_data.get("confidence", 0.5),
                dependencies=plan_data.get("dependencies", [])
            )
            
        except Exception as e:
            logger.error(f"컨텍스트 인식 작업 계획 생성 중 오류: {e}")
            return TaskPlan(
                goal="작업 계획 생성 실패",
                steps=[],
                required_tools=[],
                estimated_duration=None,
                difficulty="unknown",
                confidence=0.0,
                dependencies=[]
            )
    
    def _estimate_duration(self, difficulty: str) -> str:
        """작업 소요 시간 추정"""
        duration_map = {
            "easy": "1-2분",
            "medium": "3-5분", 
            "hard": "5-10분"
        }
        return duration_map.get(difficulty, "알 수 없음")
    
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
    
    def optimize_task_plan(self, task_plan: TaskPlan, constraints: Optional[Dict[str, Any]] = None) -> TaskPlan:
        """작업 계획 최적화"""
        if not constraints:
            return task_plan
        
        optimized_plan = TaskPlan(
            goal=task_plan.goal,
            steps=task_plan.steps.copy(),
            required_tools=task_plan.required_tools.copy(),
            estimated_duration=task_plan.estimated_duration,
            difficulty=task_plan.difficulty,
            confidence=task_plan.confidence,
            dependencies=task_plan.dependencies.copy()
        )
        
        # 시간 제약이 있는 경우
        if "max_duration" in constraints:
            max_duration = constraints["max_duration"]
            current_duration = self._parse_duration(task_plan.estimated_duration)
            
            if current_duration and current_duration > max_duration:
                # 단계 수 줄이기 또는 병렬 처리 제안
                optimized_plan.steps = self._optimize_steps_for_time(task_plan.steps, max_duration)
                optimized_plan.estimated_duration = f"{max_duration}분 이내"
        
        # 도구 제약이 있는 경우
        if "available_tools" in constraints:
            available_tools = set(constraints["available_tools"])
            required_tools = set(task_plan.required_tools)
            
            if not required_tools.issubset(available_tools):
                # 사용 불가능한 도구 대체
                missing_tools = required_tools - available_tools
                logger.warning(f"사용 불가능한 도구: {missing_tools}")
                optimized_plan.required_tools = list(required_tools & available_tools)
        
        return optimized_plan
    
    def _parse_duration(self, duration_str: Optional[str]) -> Optional[int]:
        """시간 문자열에서 분 단위 숫자 추출"""
        if not duration_str:
            return None
        
        import re
        
        # "3-5분" 형태에서 최대값 추출
        match = re.search(r'(\d+)-(\d+)분', duration_str)
        if match:
            return int(match.group(2))
        
        # "5분" 형태
        match = re.search(r'(\d+)분', duration_str)
        if match:
            return int(match.group(1))
        
        return None
    
    def _optimize_steps_for_time(self, steps: List[Dict[str, Any]], max_duration: int) -> List[Dict[str, Any]]:
        """시간 제약에 맞게 단계 최적화"""
        if not steps:
            return steps
        
        # 단순히 중요도가 높은 단계들만 선택
        if len(steps) > 3:  # 너무 많은 단계가 있으면 축약
            essential_steps = steps[:2]  # 처음 2단계
            essential_steps.append({
                "step": len(essential_steps) + 1,
                "action": "나머지 작업 완료",
                "tool": "manual",
                "expected_time": f"{max_duration // 2}분"
            })
            return essential_steps
        
        return steps
    
    def validate_task_plan(self, task_plan: TaskPlan) -> Dict[str, Any]:
        """작업 계획 유효성 검증"""
        validation_result = {
            "is_valid": True,
            "issues": [],
            "warnings": []
        }
        
        # 기본 필드 검증
        if not task_plan.goal:
            validation_result["issues"].append("작업 목표가 명시되지 않았습니다")
            validation_result["is_valid"] = False
        
        if not task_plan.steps:
            validation_result["issues"].append("실행 단계가 정의되지 않았습니다")
            validation_result["is_valid"] = False
        
        # 신뢰도 검증
        if task_plan.confidence < 0.5:
            validation_result["warnings"].append(f"낮은 신뢰도: {task_plan.confidence:.2f}")
        
        # 단계별 검증
        for i, step in enumerate(task_plan.steps):
            if "action" not in step:
                validation_result["issues"].append(f"단계 {i+1}에 액션이 정의되지 않았습니다")
                validation_result["is_valid"] = False
        
        return validation_result
