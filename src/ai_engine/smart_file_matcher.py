"""
스마트 파일 매칭 모듈

파일 목록과 사용자 요청을 LLM에게 전달하여 정확한 파일 식별을 수행
"""

import json
import asyncio
from typing import List, Dict, Any, Optional
from .llm_provider import LLMProvider, ChatMessage
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SmartFileMatcher:
    """LLM 기반 스마트 파일 매칭"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
    
    async def match_files(
        self, 
        file_list: List[Dict[str, Any]], 
        user_request: str,
        context: Optional[str] = None
    ) -> List[str]:
        """
        파일 목록과 사용자 요청을 분석하여 관련 파일들을 식별
        
        Args:
            file_list: 파일 정보 목록 (이름, 크기, 수정날짜 등)
            user_request: 사용자의 원본 요청
            context: 추가 컨텍스트 정보
            
        Returns:
            선택된 파일 경로들의 리스트
        """
        try:
            # 파일 목록을 읽기 쉬운 형태로 변환
            file_info = self._format_file_list(file_list)
            
            # LLM에게 파일 선택 요청
            prompt = self._create_matching_prompt(file_info, user_request, context)
            
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=prompt)
            ])
            
            # 응답에서 선택된 파일들 추출
            selected_files = self._parse_file_selection(response.content)
            
            logger.info(f"파일 매칭 완료: {len(selected_files)}개 파일 선택됨")
            return selected_files
            
        except Exception as e:
            logger.error(f"파일 매칭 실패: {e}")
            return []
    
    def _format_file_list(self, file_list: List[Dict[str, Any]]) -> str:
        """파일 목록을 LLM이 이해하기 쉬운 형태로 포맷"""
        formatted_lines = []
        
        for i, file_info in enumerate(file_list, 1):
            name = file_info.get('name', 'Unknown')
            size = file_info.get('size', 0)
            path = file_info.get('path', '')
            modified = file_info.get('modified', '')
            
            # 크기를 읽기 쉽게 변환
            size_str = self._format_file_size(size)
            
            line = f"{i:2d}. {name}"
            if size_str:
                line += f" ({size_str})"
            if modified:
                line += f" - {modified}"
            if path:
                line += f" -> {path}"
                
            formatted_lines.append(line)
        
        return "\n".join(formatted_lines)
    
    def _format_file_size(self, size_bytes: int) -> str:
        """파일 크기를 읽기 쉽게 포맷"""
        if size_bytes == 0:
            return ""
        
        size_float = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_float < 1024:
                return f"{size_float:.1f}{unit}"
            size_float /= 1024
        
        return f"{size_float:.1f}TB"
    
    def _create_matching_prompt(
        self, 
        file_info: str, 
        user_request: str,
        context: Optional[str] = None
    ) -> str:
        """파일 매칭을 위한 프롬프트 생성"""
        
        prompt = f"""다음 파일 목록에서 사용자 요청에 해당하는 파일들을 선택해주세요.

📁 **파일 목록**:
{file_info}

👤 **사용자 요청**: {user_request}
"""
        
        if context:
            prompt += f"\n🔍 **추가 정보**: {context}"
        
        prompt += """

📋 **선택 기준**:
- 파일명, 확장자, 크기, 수정날짜를 모두 고려
- 사용자 요청의 의도를 정확히 파악
- 애매한 경우 관련성이 높은 파일들 포함
- 명확하지 않은 파일은 제외

⚡ **응답 형식** (JSON만):
```json
{
    "selected_files": [
        "정확한_파일_경로1",
        "정확한_파일_경로2"
    ],
    "reasoning": "선택 이유 간단 설명"
}
```

사용자 요청에 맞는 파일들을 정확히 선택해주세요."""

        return prompt
    
    def _parse_file_selection(self, response_content: str) -> List[str]:
        """LLM 응답에서 선택된 파일 목록 추출"""
        try:
            # JSON 추출 시도
            start_idx = response_content.find('{')
            end_idx = response_content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_content[start_idx:end_idx]
                result = json.loads(json_str)
                
                selected_files = result.get('selected_files', [])
                reasoning = result.get('reasoning', '')
                
                if reasoning:
                    logger.info(f"파일 선택 이유: {reasoning}")
                
                return selected_files
            
            # JSON 파싱 실패 시 대안 방법
            logger.warning("JSON 파싱 실패, 대안 방법 시도")
            return self._extract_files_fallback(response_content)
            
        except Exception as e:
            logger.error(f"파일 선택 결과 파싱 실패: {e}")
            return []
    
    def _extract_files_fallback(self, content: str) -> List[str]:
        """JSON 파싱 실패 시 대안 추출 방법"""
        files = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            # 파일 경로로 보이는 패턴 찾기
            if ('/' in line or '\\' in line) and not line.startswith('#'):
                # 따옴표 제거
                clean_line = line.strip('"\'`')
                if clean_line:
                    files.append(clean_line)
        
        return files
