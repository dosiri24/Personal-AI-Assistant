"""
프롬프트 템플릿 기본 클래스

PromptType, PromptTemplate, PromptManager 기본 클래스 정의
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from string import Template

from loguru import logger


class PromptType(Enum):
    """프롬프트 템플릿 타입"""
    COMMAND_ANALYSIS = "command_analysis"
    TASK_PLANNING = "task_planning"
    TOOL_SELECTION = "tool_selection"
    MEMORY_SEARCH = "memory_search"
    RESULT_SUMMARY = "result_summary"
    ERROR_HANDLING = "error_handling"
    CLARIFICATION = "clarification"
    SYSTEM_NOTIFICATION = "system_notification"
    
    # 작업별 특화 템플릿
    SCHEDULE_MANAGEMENT = "schedule_management"
    FILE_OPERATIONS = "file_operations"
    WEB_SEARCH = "web_search"
    EMAIL_MANAGEMENT = "email_management"
    NOTE_TAKING = "note_taking"
    AUTOMATION_SETUP = "automation_setup"
    DATA_ANALYSIS = "data_analysis"
    CREATIVE_WRITING = "creative_writing"
    
    # 컨텍스트 인식 템플릿
    PERSONALIZED_RESPONSE = "personalized_response"
    CONTEXT_AWARE_PLANNING = "context_aware_planning"
    FEEDBACK_ANALYSIS = "feedback_analysis"
    PREFERENCE_LEARNING = "preference_learning"


@dataclass
class PromptTemplate:
    """프롬프트 템플릿 데이터 클래스"""
    name: str
    type: PromptType
    template: str
    description: str
    required_variables: List[str] = field(default_factory=list)
    optional_variables: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def render(self, variables: Dict[str, Any]) -> str:
        """변수를 사용하여 템플릿 렌더링"""
        try:
            # 필수 변수 확인
            missing_vars = [var for var in self.required_variables if var not in variables]
            if missing_vars:
                raise ValueError(f"필수 변수가 누락되었습니다: {missing_vars}")
                
            # 템플릿 렌더링
            template = Template(self.template)
            return template.safe_substitute(variables)
            
        except Exception as e:
            logger.error(f"템플릿 렌더링 중 오류 ({self.name}): {e}")
            raise


class BasePromptManager:
    """프롬프트 템플릿 기본 관리자"""
    
    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates: Dict[str, PromptTemplate] = {}
        self.templates_dir = templates_dir
        
    def add_template(self, template: PromptTemplate):
        """템플릿 추가"""
        self.templates[template.name] = template
        logger.debug(f"템플릿 추가됨: {template.name}")
        
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """템플릿 조회"""
        return self.templates.get(name)
        
    def render_template(self, name: str, variables: Dict[str, Any]) -> str:
        """템플릿 렌더링"""
        template = self.get_template(name)
        if not template:
            raise ValueError(f"템플릿을 찾을 수 없습니다: {name}")
        return template.render(variables)
        
    def list_templates(self) -> List[str]:
        """모든 템플릿 이름 목록"""
        return list(self.templates.keys())
        
    def get_templates_by_type(self, prompt_type: PromptType) -> List[PromptTemplate]:
        """타입별 템플릿 조회"""
        return [template for template in self.templates.values() 
                if template.type == prompt_type]
    
    def remove_template(self, name: str) -> bool:
        """템플릿 제거"""
        if name in self.templates:
            del self.templates[name]
            logger.debug(f"템플릿 제거됨: {name}")
            return True
        return False
    
    def load_from_file(self, file_path: Path):
        """파일에서 템플릿 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for template_data in data.get('templates', []):
                template = PromptTemplate(
                    name=template_data["name"],
                    type=PromptType(template_data["type"]),
                    template=template_data["template"],
                    description=template_data["description"],
                    required_variables=template_data.get("required_variables", []),
                    optional_variables=template_data.get("optional_variables", []),
                    examples=template_data.get("examples", []),
                    metadata=template_data.get("metadata", {})
                )
                self.add_template(template)
                
            logger.info(f"템플릿 파일 로드 완료: {file_path}")
            
        except Exception as e:
            logger.error(f"템플릿 파일 로드 실패 ({file_path}): {e}")
            raise
    
    def save_to_file(self, file_path: Path):
        """파일로 템플릿 저장"""
        try:
            templates_data = []
            for template in self.templates.values():
                templates_data.append({
                    "name": template.name,
                    "type": template.type.value,
                    "template": template.template,
                    "description": template.description,
                    "required_variables": template.required_variables,
                    "optional_variables": template.optional_variables,
                    "examples": template.examples,
                    "metadata": template.metadata
                })
            
            data = {"templates": templates_data}
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.info(f"템플릿 파일 저장 완료: {file_path}")
            
        except Exception as e:
            logger.error(f"템플릿 파일 저장 실패 ({file_path}): {e}")
            raise
