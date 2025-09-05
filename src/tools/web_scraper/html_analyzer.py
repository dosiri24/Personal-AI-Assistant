"""
HTML 구조 분석 AI

Gemini 2.5 Pro를 사용하여 웹페이지의 HTML 구조를 분석하고
크롤링에 필요한 CSS 선택자와 데이터 구조를 추출합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

from ...ai_engine.llm_provider import LLMManager, ChatMessage


@dataclass
class ContentElement:
    """웹페이지 콘텐츠 요소"""
    element_type: str  # 'title', 'date', 'link', 'text', 'image'
    css_selector: str
    xpath: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None
    sample_content: Optional[str] = None


@dataclass
class PageStructure:
    """웹페이지 구조 분석 결과"""
    url: str
    page_type: str  # 'list', 'detail', 'search'
    content_elements: List[ContentElement]
    pagination: Optional[Dict[str, str]] = None
    filters: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class HTMLAnalyzer:
    """Gemini 2.5 Pro 기반 HTML 구조 분석기"""
    
    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm_manager = llm_manager or LLMManager()
        self.logger = logging.getLogger(__name__)
        
    async def analyze_page_structure(self, url: str) -> PageStructure:
        """웹페이지의 구조를 분석하여 크롤링 정보를 추출"""
        try:
            # HTML 콘텐츠 가져오기
            html_content = await self._fetch_html(url)
            
            # DOM 구조 분석
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Gemini 2.5 Pro로 구조 분석
            structure_analysis = await self._analyze_with_ai(url, html_content)
            
            # PageStructure 객체 생성
            page_structure = self._parse_analysis_result(url, structure_analysis, soup)
            
            self.logger.info(f"HTML 구조 분석 완료: {url}")
            return page_structure
            
        except Exception as e:
            self.logger.error(f"HTML 구조 분석 실패 ({url}): {e}")
            raise
    
    async def _fetch_html(self, url: str) -> str:
        """웹페이지 HTML 콘텐츠 가져오기"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            return response.text
        except Exception as e:
            self.logger.error(f"HTML 가져오기 실패 ({url}): {e}")
            raise
    
    async def _analyze_with_ai(self, url: str, html_content: str) -> str:
        """Gemini 2.5 Pro로 HTML 구조 분석"""
        
        # HTML 콘텐츠를 적절한 크기로 제한 (토큰 제한 대응)
        truncated_html = self._truncate_html(html_content)
        
        analysis_prompt = f"""
웹페이지 구조를 분석해 주세요.

URL: {url}

이 웹페이지에서 다음 정보를 추출해 주세요:
1. 페이지 유형 (list, detail, search 중 하나)
2. 주요 콘텐츠의 CSS 선택자
3. 제목, 날짜, 링크 요소들

JSON 형식으로 응답:
{{
    "page_type": "list",
    "content_elements": [
        {{
            "element_type": "title",
            "css_selector": "table tr td:nth-child(2)",
            "sample_content": "공지사항 제목"
        }}
    ]
}}
"""
        
        try:
            messages = [{"role": "user", "content": analysis_prompt}]
            response = await self.llm_manager.generate_response(
                messages=messages,
                temperature=0.1,
                max_tokens=1000
            )
            return response.content
            
        except Exception as e:
            self.logger.error(f"AI 구조 분석 실패: {e}")
            raise
    
    def _truncate_html(self, html_content: str, max_length: int = 8000) -> str:
        """HTML 콘텐츠를 토큰 제한에 맞게 자르기"""
        if len(html_content) <= max_length:
            return html_content
        
        # 주요 섹션 보존하면서 자르기
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 불필요한 태그 제거
        for tag in soup(['script', 'style', 'meta', 'link']):
            tag.decompose()
        
        # 압축된 HTML 반환
        compressed = str(soup)
        if len(compressed) > max_length:
            return compressed[:max_length] + "..."
        return compressed
    
    def _parse_analysis_result(self, url: str, analysis_result: str, soup: BeautifulSoup) -> PageStructure:
        """AI 분석 결과를 PageStructure 객체로 변환"""
        try:
            import json
            
            # JSON 응답에서 실제 JSON 부분 추출
            json_start = analysis_result.find('{')
            json_end = analysis_result.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("JSON 형식을 찾을 수 없습니다")
            
            json_str = analysis_result[json_start:json_end]
            analysis_data = json.loads(json_str)
            
            # ContentElement 리스트 생성
            content_elements = []
            for element_data in analysis_data.get('content_elements', []):
                element = ContentElement(
                    element_type=element_data.get('element_type', 'text'),
                    css_selector=element_data.get('css_selector', ''),
                    sample_content=element_data.get('sample_content')
                )
                content_elements.append(element)
            
            # PageStructure 생성
            page_structure = PageStructure(
                url=url,
                page_type=analysis_data.get('page_type', 'list'),
                content_elements=content_elements,
                pagination=analysis_data.get('pagination'),
                filters=analysis_data.get('filters'),
                metadata={
                    'analyzed_at': asyncio.get_event_loop().time(),
                    'title': soup.title.string if soup.title else 'Unknown'
                }
            )
            
            return page_structure
            
        except Exception as e:
            self.logger.error(f"분석 결과 파싱 실패: {e}")
            # 기본 구조 반환
            return self._create_fallback_structure(url, soup)
    
    def _create_fallback_structure(self, url: str, soup: BeautifulSoup) -> PageStructure:
        """분석 실패 시 기본 구조 생성"""
        return PageStructure(
            url=url,
            page_type='unknown',
            content_elements=[],
            metadata={
                'title': soup.title.string if soup.title else 'Unknown',
                'fallback': True
            }
        )
    
    async def validate_selectors(self, page_structure: PageStructure) -> Dict[str, bool]:
        """생성된 CSS 선택자의 유효성 검증"""
        try:
            html_content = await self._fetch_html(page_structure.url)
            soup = BeautifulSoup(html_content, 'html.parser')
            
            validation_results = {}
            
            for element in page_structure.content_elements:
                try:
                    selected_elements = soup.select(element.css_selector)
                    validation_results[element.css_selector] = len(selected_elements) > 0
                except Exception:
                    validation_results[element.css_selector] = False
            
            self.logger.info(f"선택자 검증 완료: {len(validation_results)}개")
            return validation_results
            
        except Exception as e:
            self.logger.error(f"선택자 검증 실패: {e}")
            return {}


# 사용 예시
async def main():
    """HTML 분석기 테스트"""
    analyzer = HTMLAnalyzer()
    
    # 인하대 공지사항 페이지 분석
    inha_url = "https://www.inha.ac.kr/kr/950/subview.do"
    
    try:
        structure = await analyzer.analyze_page_structure(inha_url)
        print(f"페이지 타입: {structure.page_type}")
        print(f"콘텐츠 요소 수: {len(structure.content_elements)}")
        
        for element in structure.content_elements:
            print(f"- {element.element_type}: {element.css_selector}")
        
        # 선택자 검증
        validation = await analyzer.validate_selectors(structure)
        print(f"검증 결과: {validation}")
        
    except Exception as e:
        print(f"분석 실패: {e}")


if __name__ == "__main__":
    asyncio.run(main())
