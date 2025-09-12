"""
계획 검증 및 교정 시스템

AI가 생성한 계획에서 문제점을 감지하고 자동으로 교정하는 시스템입니다.
특히 추상적인 플레이스홀더나 비실행 가능한 단계들을 감지하여 구체적인 단계로 교정합니다.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ValidationError(Enum):
    """검증 오류 유형"""
    ABSTRACT_PLACEHOLDER = "abstract_placeholder"
    MISSING_EXPLORATION = "missing_exploration"
    INVALID_TOOL_PARAMS = "invalid_tool_params"
    INCOMPLETE_WORKFLOW = "incomplete_workflow"
    NON_EXECUTABLE_STEP = "non_executable_step"


@dataclass
class ValidationIssue:
    """검증 문제"""
    error_type: ValidationError
    step_id: str
    description: str
    suggested_fix: Optional[str] = None
    severity: str = "medium"  # low, medium, high, critical


class PlanValidator:
    """계획 검증기"""
    
    def __init__(self):
        # 추상적 플레이스홀더 패턴
        self.abstract_patterns = [
            r"<[^>]*파일[^>]*경로[^>]*>",  # <식별된_스크린샷_파일_전체_경로>
            r"<[^>]*식별된[^>]*>",        # <식별된_무언가>
            r"<[^>]*찾아진[^>]*>",        # <찾아진_파일들>
            r"<[^>]*결과[^>]*>",          # <결과_경로>
            r"<[^>]*목록[^>]*>",          # <파일_목록>
        ]
        
        # 파일 관련 키워드
        self.file_keywords = [
            "스크린샷", "screenshot", "이미지", "사진", "파일", "문서",
            "PDF", "삭제", "정리", "찾기", "검색"
        ]
    
    def validate_plan(self, plan_data: Dict[str, Any], goal: str) -> Tuple[bool, List[ValidationIssue]]:
        """
        계획 검증
        
        Args:
            plan_data: 계획 데이터
            goal: 원본 목표
            
        Returns:
            Tuple[bool, List[ValidationIssue]]: (검증 통과 여부, 발견된 문제들)
        """
        issues = []
        
        # 1. 추상적 플레이스홀더 검증
        issues.extend(self._check_abstract_placeholders(plan_data))
        
        # 2. 파일 작업 워크플로우 검증
        if self._is_file_related_goal(goal):
            issues.extend(self._check_file_workflow(plan_data, goal))
        
        # 3. 도구 매개변수 검증
        issues.extend(self._check_tool_parameters(plan_data))
        
        # 4. 실행 가능성 검증
        issues.extend(self._check_executability(plan_data))
        
        # 심각한 문제가 있는지 확인
        critical_issues = [issue for issue in issues if issue.severity == "critical"]
        is_valid = len(critical_issues) == 0
        
        return is_valid, issues
    
    def _check_abstract_placeholders(self, plan_data: Dict[str, Any]) -> List[ValidationIssue]:
        """추상적 플레이스홀더 검증"""
        issues = []
        
        for step in plan_data.get("steps", []):
            step_id = step.get("step_id", "unknown")
            
            # tool_params에서 추상적 플레이스홀더 검색
            tool_params = step.get("tool_params", {})
            step_text = json.dumps(tool_params, ensure_ascii=False)
            
            for pattern in self.abstract_patterns:
                matches = re.findall(pattern, step_text)
                if matches:
                    issues.append(ValidationIssue(
                        error_type=ValidationError.ABSTRACT_PLACEHOLDER,
                        step_id=step_id,
                        description=f"추상적 플레이스홀더 발견: {matches}",
                        suggested_fix="먼저 파일 탐색 단계를 추가하여 실제 파일들을 찾아야 함",
                        severity="critical"
                    ))
        
        return issues
    
    def _is_file_related_goal(self, goal: str) -> bool:
        """파일 관련 목표인지 확인"""
        goal_lower = goal.lower()
        return any(keyword in goal_lower for keyword in self.file_keywords)
    
    def _check_file_workflow(self, plan_data: Dict[str, Any], goal: str) -> List[ValidationIssue]:
        """파일 작업 워크플로우 검증"""
        issues = []
        steps = plan_data.get("steps", [])
        
        has_exploration = False
        has_file_action = False
        
        for step in steps:
            tool_name = step.get("tool_name")
            action_type = step.get("action_type")
            
            # 탐색 단계 확인
            if tool_name in ["system_explorer", "filesystem"] and action_type == "tool_call":
                tool_params = step.get("tool_params", {})
                action = tool_params.get("action")
                if action in ["tree", "list", "find", "search_files", "get_structure"]:
                    has_exploration = True
            
            # 파일 작업 확인
            if tool_name == "filesystem" and action_type == "tool_call":
                tool_params = step.get("tool_params", {})
                action = tool_params.get("action")
                if action in ["delete", "move", "copy"]:
                    has_file_action = True
        
        # 파일 작업이 있는데 탐색이 없는 경우
        if has_file_action and not has_exploration:
            issues.append(ValidationIssue(
                error_type=ValidationError.MISSING_EXPLORATION,
                step_id="workflow",
                description="파일 작업 전 탐색 단계가 누락됨",
                suggested_fix="filesystem 또는 system_explorer 도구로 먼저 대상 파일들을 탐색해야 함",
                severity="critical"
            ))
        
        return issues
    
    def _check_tool_parameters(self, plan_data: Dict[str, Any]) -> List[ValidationIssue]:
        """도구 매개변수 검증"""
        issues = []
        
        # 알려진 도구별 유효한 액션들
        valid_actions = {
            "filesystem": ["list", "create_dir", "copy", "move", "delete"],
            "system_explorer": ["tree", "find", "locate", "explore_common", "get_structure", "search_files"]
        }
        
        for step in plan_data.get("steps", []):
            step_id = step.get("step_id", "unknown")
            tool_name = step.get("tool_name")
            tool_params = step.get("tool_params", {})
            
            if tool_name in valid_actions:
                action = tool_params.get("action")
                if action and action not in valid_actions[tool_name]:
                    issues.append(ValidationIssue(
                        error_type=ValidationError.INVALID_TOOL_PARAMS,
                        step_id=step_id,
                        description=f"{tool_name} 도구의 잘못된 action: {action}",
                        suggested_fix=f"유효한 action: {valid_actions[tool_name]}",
                        severity="high"
                    ))
        
        return issues
    
    def _check_executability(self, plan_data: Dict[str, Any]) -> List[ValidationIssue]:
        """실행 가능성 검증"""
        issues = []
        
        for step in plan_data.get("steps", []):
            step_id = step.get("step_id", "unknown")
            action_type = step.get("action_type")
            tool_name = step.get("tool_name")
            
            # tool_call인데 도구가 없는 경우
            if action_type == "tool_call" and not tool_name:
                issues.append(ValidationIssue(
                    error_type=ValidationError.NON_EXECUTABLE_STEP,
                    step_id=step_id,
                    description="tool_call 단계인데 tool_name이 없음",
                    suggested_fix="tool_name을 지정하거나 action_type을 수정해야 함",
                    severity="high"
                ))
        
        return issues


class PlanCorrector:
    """계획 교정기"""
    
    def __init__(self):
        self.validator = PlanValidator()
    
    def correct_plan(self, plan_data: Dict[str, Any], goal: str) -> Dict[str, Any]:
        """
        계획 교정
        
        Args:
            plan_data: 원본 계획 데이터
            goal: 목표
            
        Returns:
            Dict[str, Any]: 교정된 계획 데이터
        """
        is_valid, issues = self.validator.validate_plan(plan_data, goal)
        
        if is_valid:
            logger.info("계획 검증 통과, 교정 불필요")
            return plan_data
        
        logger.warning(f"계획 검증 실패, {len(issues)}개 문제 발견")
        for issue in issues:
            logger.warning(f"  - {issue.step_id}: {issue.description}")
        
        # 교정 수행
        corrected_plan = plan_data.copy()
        
        # 1. 추상적 플레이스홀더 문제 교정
        corrected_plan = self._fix_abstract_placeholders(corrected_plan, issues, goal)
        
        # 2. 파일 워크플로우 문제 교정
        corrected_plan = self._fix_file_workflow(corrected_plan, issues, goal)
        
        # 3. 도구 매개변수 문제 교정
        corrected_plan = self._fix_tool_parameters(corrected_plan, issues)
        
        logger.info("계획 교정 완료")
        return corrected_plan
    
    def _fix_abstract_placeholders(self, plan_data: Dict[str, Any], issues: List[ValidationIssue], goal: str) -> Dict[str, Any]:
        """추상적 플레이스홀더 문제 교정"""
        # 추상적 플레이스홀더가 있는 경우 파일 탐색 단계를 추가
        abstract_issues = [issue for issue in issues if issue.error_type == ValidationError.ABSTRACT_PLACEHOLDER]
        
        if not abstract_issues:
            return plan_data
        
        steps = plan_data.get("steps", [])
        
        # 목표에서 경로 추출 (바탕화면, 문서 등)
        goal_lower = goal.lower()
        target_path = "~/Desktop"  # 기본값
        
        if "바탕화면" in goal_lower or "desktop" in goal_lower:
            target_path = "~/Desktop"
        elif "문서" in goal_lower or "documents" in goal_lower:
            target_path = "~/Documents"
        elif "다운로드" in goal_lower or "downloads" in goal_lower:
            target_path = "~/Downloads"
        
        # 파일 탐색 단계 추가
        exploration_step = {
            "step_id": "step_exploration",
            "description": f"대상 디렉토리 탐색 및 파일 목록 수집",
            "action_type": "tool_call",
            "tool_name": "filesystem",
            "tool_params": {
                "action": "list",
                "path": target_path
            },
            "dependencies": [],
            "priority": 4,
            "estimated_duration": 10.0,
            "success_criteria": "디렉토리 내 파일 목록 성공적으로 수집",
            "failure_recovery": "경로 확인 후 재시도"
        }
        
        # 첫 번째 위치에 삽입 (경로 확인 다음)
        insert_position = 1 if len(steps) > 0 else 0
        steps.insert(insert_position, exploration_step)
        
        # 기존 단계들의 의존성 업데이트
        for step in steps[insert_position + 1:]:
            if step.get("action_type") == "tool_call" and step.get("tool_name") == "filesystem":
                tool_params = step.get("tool_params", {})
                if tool_params.get("action") in ["delete", "move", "copy"]:
                    # 탐색 단계에 의존성 추가
                    dependencies = step.get("dependencies", [])
                    if "step_exploration" not in dependencies:
                        dependencies.append("step_exploration")
                        step["dependencies"] = dependencies
        
        plan_data["steps"] = steps
        return plan_data
    
    def _fix_file_workflow(self, plan_data: Dict[str, Any], issues: List[ValidationIssue], goal: str) -> Dict[str, Any]:
        """파일 워크플로우 문제 교정"""
        workflow_issues = [issue for issue in issues if issue.error_type == ValidationError.MISSING_EXPLORATION]
        
        if not workflow_issues:
            return plan_data
        
        # 이미 _fix_abstract_placeholders에서 처리됨
        return plan_data
    
    def _fix_tool_parameters(self, plan_data: Dict[str, Any], issues: List[ValidationIssue]) -> Dict[str, Any]:
        """도구 매개변수 문제 교정"""
        param_issues = [issue for issue in issues if issue.error_type == ValidationError.INVALID_TOOL_PARAMS]
        
        # 자동 교정 가능한 매개변수들
        action_corrections = {
            "filesystem": {
                "delete_file": "delete",
                "remove": "delete",
                "list_files": "list",
                "find": "list"  # filesystem에서 find는 지원하지 않으므로 list로 변경
            },
            "system_explorer": {
                "list": "tree",
                "search": "search_files",
                "find_files": "find"
            }
        }
        
        for issue in param_issues:
            for step in plan_data.get("steps", []):
                if step.get("step_id") == issue.step_id:
                    tool_name = step.get("tool_name")
                    tool_params = step.get("tool_params", {})
                    action = tool_params.get("action")
                    
                    if tool_name in action_corrections and action in action_corrections[tool_name]:
                        new_action = action_corrections[tool_name][action]
                        tool_params["action"] = new_action
                        logger.info(f"도구 매개변수 자동 교정: {tool_name}.{action} → {new_action}")
        
        return plan_data


# 전역 인스턴스
plan_corrector = PlanCorrector()


def validate_and_correct_plan(plan_data: Dict[str, Any], goal: str) -> Dict[str, Any]:
    """계획 검증 및 교정 (편의 함수)"""
    return plan_corrector.correct_plan(plan_data, goal)
