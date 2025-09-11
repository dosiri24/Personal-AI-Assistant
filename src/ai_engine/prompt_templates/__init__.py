"""
프롬프트 템플릿 모듈화 시스템
원본 prompt_templates.py (844줄)을 기능별로 분리하여 관리성 향상

모듈 구조:
- base.py: 기본 클래스와 타입 정의
- command.py: 명령 분석 및 처리
- memory.py: 메모리 및 검색 기능
- results.py: 결과 처리 및 오류 관리
- tools.py: 도구 및 전문 기능

통합 관리자를 통해 모든 템플릿에 일관된 접근 제공
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import logging

from .base import BasePromptManager, PromptTemplate, PromptType
from .command import CommandPromptManager
from .memory import MemoryPromptManager
from .results import ResultsPromptManager
from .tools import ToolsPromptManager

logger = logging.getLogger(__name__)


class PromptTemplateManager:
    """
    통합 프롬프트 템플릿 관리자
    모든 모듈화된 템플릿 매니저를 통합 관리
    """
    
    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Args:
            templates_dir: 템플릿 저장 디렉토리 (선택사항)
        """
        self.templates_dir = templates_dir
        
        # 각 카테고리별 매니저 초기화
        self.command_manager = CommandPromptManager()
        self.memory_manager = MemoryPromptManager()
        self.results_manager = ResultsPromptManager()
        self.tools_manager = ToolsPromptManager()
        
        # 전체 템플릿 통합 관리
        self._all_templates: Dict[str, PromptTemplate] = {}
        self._template_managers: Dict[str, BasePromptManager] = {
            "command": self.command_manager,
            "memory": self.memory_manager,
            "results": self.results_manager,
            "tools": self.tools_manager
        }
        
        self._consolidate_templates()
        logger.info(f"프롬프트 템플릿 매니저 초기화 완료 - 총 {len(self._all_templates)}개 템플릿")
    
    def _consolidate_templates(self):
        """모든 매니저의 템플릿을 통합"""
        for manager_name, manager in self._template_managers.items():
            for template_name, template in manager.templates.items():
                if template_name in self._all_templates:
                    logger.warning(f"중복 템플릿명 발견: {template_name} (매니저: {manager_name})")
                self._all_templates[template_name] = template
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """템플릿 가져오기"""
        return self._all_templates.get(name)
    
    def list_templates(self, template_type: Optional[PromptType] = None, category: Optional[str] = None) -> List[str]:
        """
        템플릿 목록 반환
        
        Args:
            template_type: 특정 타입의 템플릿만 필터링
            category: 특정 카테고리(command, memory, results, tools)만 필터링
        """
        if category and category in self._template_managers:
            # 특정 카테고리만 반환
            return self._template_managers[category].list_templates(template_type)
        
        # 전체 또는 타입별 반환
        if template_type:
            return [
                name for name, template in self._all_templates.items()
                if template.type == template_type
            ]
        return list(self._all_templates.keys())
    
    def render_template(self, name: str, variables: Dict[str, Any]) -> str:
        """템플릿 렌더링"""
        template = self.get_template(name)
        if not template:
            raise ValueError(f"템플릿을 찾을 수 없습니다: {name}")
        
        return template.render(variables)
    
    def add_template(self, template: PromptTemplate, category: str = "tools"):
        """
        새 템플릿 추가
        
        Args:
            template: 추가할 템플릿
            category: 카테고리 (command, memory, results, tools)
        """
        if category not in self._template_managers:
            raise ValueError(f"지원하지 않는 카테고리: {category}")
        
        manager = self._template_managers[category]
        manager.add_template(template)
        self._all_templates[template.name] = template
        
        logger.info(f"새 템플릿 추가: {template.name} ({category})")
    
    def get_templates_by_type(self, template_type: PromptType) -> Dict[str, PromptTemplate]:
        """특정 타입의 모든 템플릿 반환"""
        return {
            name: template for name, template in self._all_templates.items()
            if template.type == template_type
        }
    
    def get_templates_by_category(self, category: str) -> Dict[str, PromptTemplate]:
        """특정 카테고리의 모든 템플릿 반환"""
        if category not in self._template_managers:
            raise ValueError(f"지원하지 않는 카테고리: {category}")
        
        return self._template_managers[category].templates.copy()
    
    def validate_template(self, name: str, variables: Dict[str, Any]) -> bool:
        """템플릿 변수 유효성 검사"""
        template = self.get_template(name)
        if not template:
            return False
        
        # 필수 변수 확인
        missing_vars = set(template.required_variables) - set(variables.keys())
        if missing_vars:
            logger.warning(f"템플릿 {name}에서 누락된 필수 변수: {missing_vars}")
            return False
        
        return True
    
    def save_all_templates(self, base_dir: Path):
        """모든 템플릿을 카테고리별 파일로 저장"""
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            
            for category, manager in self._template_managers.items():
                file_path = base_dir / f"{category}_templates.json"
                manager.save_templates(file_path)
            
            logger.info(f"모든 템플릿 저장 완료: {base_dir}")
            
        except Exception as e:
            logger.error(f"템플릿 저장 중 오류: {e}")
            raise
    
    def load_all_templates(self, base_dir: Path):
        """카테고리별 파일에서 템플릿 로드"""
        try:
            for category, manager in self._template_managers.items():
                file_path = base_dir / f"{category}_templates.json"
                if file_path.exists():
                    manager.load_templates(file_path)
            
            # 통합 템플릿 딕셔너리 재구성
            self._consolidate_templates()
            logger.info(f"모든 템플릿 로드 완료: {len(self._all_templates)}개")
            
        except Exception as e:
            logger.error(f"템플릿 로드 중 오류: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """템플릿 통계 정보 반환"""
        stats = {
            "total_templates": len(self._all_templates),
            "by_category": {},
            "by_type": {}
        }
        
        # 카테고리별 통계
        for category, manager in self._template_managers.items():
            stats["by_category"][category] = len(manager.templates)
        
        # 타입별 통계
        type_counts = {}
        for template in self._all_templates.values():
            type_name = template.type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        stats["by_type"] = type_counts
        
        return stats


# 편의를 위한 전역 인스턴스
_global_manager: Optional[PromptTemplateManager] = None


def get_prompt_manager() -> PromptTemplateManager:
    """전역 프롬프트 템플릿 매니저 인스턴스 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = PromptTemplateManager()
    return _global_manager


def render_prompt(template_name: str, variables: Dict[str, Any]) -> str:
    """편의 함수: 템플릿 렌더링"""
    return get_prompt_manager().render_template(template_name, variables)


def list_available_templates(category: Optional[str] = None) -> List[str]:
    """편의 함수: 사용 가능한 템플릿 목록"""
    return get_prompt_manager().list_templates(category=category)


# 호환성을 위한 별칭
PromptManager = PromptTemplateManager  # 기존 코드 호환성

# 모든 공개 클래스와 함수 내보내기
__all__ = [
    'PromptTemplateManager',
    'PromptManager',  # 호환성 별칭
    'PromptTemplate', 
    'PromptType',
    'CommandPromptManager',
    'MemoryPromptManager', 
    'ResultsPromptManager',
    'ToolsPromptManager',
    'get_prompt_manager',
    'render_prompt',
    'list_available_templates'
]
