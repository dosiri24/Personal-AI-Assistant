"""
플레이스홀더 치환 유틸리티

다양한 형태의 플레이스홀더를 실제 값으로 치환하는 유틸리티 함수들
"""

import os
import re
from typing import Any, Dict, List, Optional
from pathlib import Path
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PlaceholderResolver:
    """플레이스홀더 해결기"""
    
    def __init__(self):
        # 기본 경로 매핑
        self.path_mappings = {
            "바탕화면": "~/Desktop",
            "desktop": "~/Desktop", 
            "데스크탑": "~/Desktop",
            "문서": "~/Documents",
            "documents": "~/Documents",
            "다운로드": "~/Downloads", 
            "downloads": "~/Downloads",
            "홈": "~",
            "home": "~"
        }
    
    def resolve_placeholders(self, params: Dict[str, Any], dependency_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """모든 형태의 플레이스홀더를 해결"""
        if dependency_results is None:
            dependency_results = {}
            
        resolved = {}
        for key, value in params.items():
            if isinstance(value, dict):
                resolved[key] = self.resolve_placeholders(value, dependency_results)
            elif isinstance(value, list):
                resolved[key] = [self._resolve_single_value(item, dependency_results) for item in value]
            else:
                resolved[key] = self._resolve_single_value(value, dependency_results)
        
        return resolved
    
    def _resolve_single_value(self, value: Any, dependency_results: Dict[str, Any]) -> Any:
        """단일 값의 플레이스홀더 해결"""
        if not isinstance(value, str):
            return value
        
        original_value = value
        
        # 1. 각도 괄호 플레이스홀더 처리: <바탕화면_경로>, <문서_폴더> 등
        value = self._resolve_angle_brackets(value)
        
        # 2. 대괄호 의존성 참조 처리: [step_1 결과: ...]
        value = self._resolve_dependency_references(value, dependency_results)
        
        # 3. 특수 키워드 처리: "탐색_결과_기반", "이전_단계_결과" 등
        value = self._resolve_special_keywords(value, dependency_results)
        
        # 4. 경로 정규화
        value = self._normalize_path(value)
        
        if value != original_value:
            logger.info(f"플레이스홀더 해결: '{original_value}' → '{value}'")
        
        return value
    
    def _resolve_angle_brackets(self, value: str) -> str:
        """각도 괄호 플레이스홀더 처리"""
        pattern = r'<([^>]+)>'
        
        def replace_angle_placeholder(match):
            placeholder = match.group(1).lower()
            
            # 경로 관련 플레이스홀더
            for keyword, path_template in self.path_mappings.items():
                if keyword in placeholder:
                    expanded_path = os.path.expanduser(path_template)
                    logger.debug(f"경로 플레이스홀더 매핑: {match.group(0)} → {expanded_path}")
                    return expanded_path
            
            # 매핑되지 않은 플레이스홀더는 그대로 반환
            logger.warning(f"해결되지 않은 플레이스홀더: {match.group(0)}")
            return match.group(0)
        
        return re.sub(pattern, replace_angle_placeholder, value)
    
    def _resolve_dependency_references(self, value: str, dependency_results: Dict[str, Any]) -> str:
        """의존성 참조 해결"""
        pattern = r'\[([^]]+)\s+결과:[^]]*\]'
        
        def replace_dependency_ref(match):
            step_ref = match.group(1).strip()
            
            if step_ref in dependency_results:
                result_data = dependency_results[step_ref]
                return self._extract_result_value(result_data)
            
            logger.warning(f"의존성 결과를 찾을 수 없음: {step_ref}")
            return match.group(0)
        
        return re.sub(pattern, replace_dependency_ref, value)
    
    def _resolve_special_keywords(self, value: str, dependency_results: Dict[str, Any]) -> str:
        """특수 키워드 해결"""
        special_keywords = {
            "탐색_결과_기반": self._get_latest_result,
            "이전_단계_결과": self._get_latest_result,
            "최근_결과": self._get_latest_result
        }
        
        for keyword, resolver in special_keywords.items():
            if value == keyword:
                return resolver(dependency_results)
        
        return value
    
    def _extract_result_value(self, result_data: Any) -> str:
        """결과 데이터에서 값 추출"""
        if isinstance(result_data, list) and result_data:
            if isinstance(result_data[0], dict) and 'path' in result_data[0]:
                return result_data[0]['path']
            else:
                return str(result_data[0])
        elif isinstance(result_data, dict):
            if 'path' in result_data:
                return result_data['path']
            elif 'value' in result_data:
                return str(result_data['value'])
            else:
                return str(result_data)
        else:
            return str(result_data)
    
    def _get_latest_result(self, dependency_results: Dict[str, Any]) -> str:
        """가장 최근 의존성 결과 반환"""
        if not dependency_results:
            return ""
        
        latest_result = list(dependency_results.values())[-1]
        return self._extract_result_value(latest_result)
    
    def _normalize_path(self, value: str) -> str:
        """경로 정규화"""
        if not value or not isinstance(value, str):
            return value
        
        # 홈 디렉토리 확장
        if value.startswith('~'):
            value = os.path.expanduser(value)
        
        # 상대 경로를 절대 경로로 변환 (파일 시스템 경로인 경우)
        if os.path.sep in value or '/' in value or '\\' in value:
            try:
                # 경로가 존재하는지 확인하지 않고 정규화만 수행
                normalized = os.path.normpath(value)
                return normalized
            except Exception as e:
                logger.debug(f"경로 정규화 실패: {value} - {e}")
                return value
        
        return value


# 전역 인스턴스
placeholder_resolver = PlaceholderResolver()
