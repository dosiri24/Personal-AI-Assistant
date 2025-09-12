"""
스마트 파일 매칭 모듈

파일 목록과 사용자 요청을 LLM에게 전달하여 정확한 파일 식별을 수행
"""

import json
import asyncio
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from .llm_provider import LLMProvider, ChatMessage
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SmartFileMatcher:
    """LLM 기반 스마트 파일 매칭"""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm_provider = llm_provider
    
    async def find_files_in_directory(
        self, 
        directory_path: str,
        user_request: str,
        recursive: bool = True,
        file_extensions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        디렉토리를 스캔하고 사용자 요청에 맞는 파일들을 찾기
        
        Args:
            directory_path: 검색할 디렉토리 경로
            user_request: 사용자 요청 (예: "젠트리피케이션 관련 논문들")
            recursive: 하위 디렉토리까지 검색할지 여부
            file_extensions: 검색할 파일 확장자 필터 (예: ['.pdf', '.docx'])
            
        Returns:
            Dict: 검색 결과와 선택된 파일들
        """
        try:
            # 1단계: 디렉토리 스캔
            file_list = await self._scan_directory(directory_path, recursive, file_extensions)
            
            if not file_list:
                return {
                    "success": False,
                    "message": f"디렉토리 '{directory_path}'에서 파일을 찾을 수 없습니다.",
                    "total_files": 0,
                    "selected_files": []
                }
            
            # 2단계: LLM을 통한 스마트 매칭
            selected_files = await self.match_files(file_list, user_request)
            
            return {
                "success": True,
                "directory": directory_path,
                "total_files": len(file_list),
                "selected_files": selected_files,
                "message": f"{len(file_list)}개 파일 중 {len(selected_files)}개 파일을 선택했습니다."
            }
            
        except Exception as e:
            logger.error(f"디렉토리 스마트 검색 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_files": 0,
                "selected_files": []
            }
    
    async def find_target_directory(
        self,
        search_paths: List[str],
        directory_description: str
    ) -> Optional[str]:
        """
        여러 경로에서 사용자가 설명한 디렉토리를 찾기
        
        Args:
            search_paths: 검색할 경로들 (예: ["~/Desktop", "~/Documents", "~/Downloads"])
            directory_description: 디렉토리 설명 (예: "논문 폴더", "연구 자료")
            
        Returns:
            찾은 디렉토리 경로 또는 None
        """
        try:
            all_directories = []
            
            # 각 경로에서 디렉토리 목록 수집
            for search_path in search_paths:
                expanded_path = os.path.expanduser(search_path)
                if os.path.exists(expanded_path):
                    dirs = await self._get_directories(expanded_path)
                    all_directories.extend(dirs)
            
            if not all_directories:
                return None
            
            # LLM에게 가장 적절한 디렉토리 선택 요청
            selected_dir = await self._select_target_directory(all_directories, directory_description)
            return selected_dir
            
        except Exception as e:
            logger.error(f"대상 디렉토리 찾기 실패: {e}")
            return None
    
    async def _scan_directory(
        self, 
        directory_path: str, 
        recursive: bool = True,
        file_extensions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """디렉토리 스캔하여 파일 정보 수집"""
        file_list = []
        expanded_path = os.path.expanduser(directory_path)
        
        if not os.path.exists(expanded_path):
            logger.warning(f"경로가 존재하지 않습니다: {expanded_path}")
            return []
        
        try:
            if recursive:
                for root, dirs, files in os.walk(expanded_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_info = await self._get_file_info(file_path, file_extensions)
                        if file_info:
                            file_list.append(file_info)
            else:
                for item in os.listdir(expanded_path):
                    item_path = os.path.join(expanded_path, item)
                    if os.path.isfile(item_path):
                        file_info = await self._get_file_info(item_path, file_extensions)
                        if file_info:
                            file_list.append(file_info)
                            
        except Exception as e:
            logger.error(f"디렉토리 스캔 오류: {e}")
        
        return file_list
    
    async def _get_file_info(self, file_path: str, file_extensions: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """파일 정보 추출"""
        try:
            # 확장자 필터링
            if file_extensions:
                file_ext = Path(file_path).suffix.lower()
                if file_ext not in [ext.lower() for ext in file_extensions]:
                    return None
            
            stat = os.stat(file_path)
            
            return {
                "name": os.path.basename(file_path),
                "path": file_path,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
                "extension": Path(file_path).suffix.lower()
            }
        except Exception as e:
            logger.warning(f"파일 정보 추출 실패 ({file_path}): {e}")
            return None
    
    async def _get_directories(self, search_path: str) -> List[Dict[str, str]]:
        """지정된 경로에서 디렉토리 목록 가져오기"""
        directories = []
        
        try:
            for item in os.listdir(search_path):
                item_path = os.path.join(search_path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    directories.append({
                        "name": item,
                        "path": item_path
                    })
        except Exception as e:
            logger.warning(f"디렉토리 목록 가져오기 실패 ({search_path}): {e}")
        
        return directories
    
    async def _select_target_directory(self, directories: List[Dict[str, str]], description: str) -> Optional[str]:
        """LLM을 통해 설명에 가장 맞는 디렉토리 선택"""
        if not directories:
            return None
        
        # 디렉토리 목록 포맷팅
        dir_list = "\n".join([f"- {d['name']} -> {d['path']}" for d in directories])
        
        prompt = f"""다음 디렉토리 목록에서 사용자 설명에 가장 적합한 디렉토리를 선택해주세요.

📁 **디렉토리 목록**:
{dir_list}

👤 **사용자 설명**: {description}

📋 **선택 기준**:
- 디렉토리명과 사용자 설명 간의 의미적 연관성
- 일반적인 명명 규칙 고려 (예: "Papers" = "논문", "Research" = "연구")
- 애매한 경우 가장 가능성 높은 것 선택

⚡ **응답 형식** (JSON만):
```json
{{
    "selected_directory": "정확한_디렉토리_경로",
    "reasoning": "선택 이유"
}}
```

가장 적절한 디렉토리 하나만 선택해주세요."""

        try:
            response = await self.llm_provider.generate_response([
                ChatMessage(role="user", content=prompt)
            ])
            
            # JSON 파싱
            start_idx = response.content.find('{')
            end_idx = response.content.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response.content[start_idx:end_idx]
                result = json.loads(json_str)
                
                selected_dir = result.get('selected_directory')
                reasoning = result.get('reasoning', '')
                
                if reasoning:
                    logger.info(f"디렉토리 선택 이유: {reasoning}")
                
                return selected_dir
                
        except Exception as e:
            logger.error(f"디렉토리 선택 실패: {e}")
        
        return None
    
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
