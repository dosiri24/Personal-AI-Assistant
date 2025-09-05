"""
동적 크롤러 생성기

웹사이트의 구조를 분석하여 자동으로 크롤링 코드를 생성합니다.
인하대 공지사항 사이트에 특화된 크롤러를 생성합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
from pathlib import Path

from .html_analyzer import PageStructure, ContentElement


@dataclass
class CrawlerConfig:
    """크롤러 설정"""
    name: str
    target_url: str
    selectors: Dict[str, str]
    output_format: str = "json"
    delay: float = 1.0
    max_pages: int = 5


class CrawlerGenerator:
    """사이트별 맞춤 크롤러 자동 생성"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_inha_crawler(self, page_structure: PageStructure) -> str:
        """인하대 공지사항 크롤러 코드 생성"""
        
        crawler_code = f'''"""
인하대 공지사항 크롤러
자동 생성된 코드 - {page_structure.url}
"""

import requests
import time
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from datetime import datetime


class InhaNoticeCrawler:
    """인하대 공지사항 크롤러"""
    
    def __init__(self):
        self.base_url = "{page_structure.url}"
        self.session = requests.Session()
        self.session.headers.update({{
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }})
    
    def crawl_notices(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        """공지사항 크롤링"""
        notices = []
        
        for page in range(1, max_pages + 1):
            try:
                page_url = f"{{self.base_url}}?page={{page}}"
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 공지사항 테이블에서 데이터 추출
                notice_rows = soup.select('table tbody tr')
                
                for row in notice_rows:
                    try:
                        # 번호 추출 (첫 번째 td)
                        number_cell = row.select_one('td:first-child')
                        number = number_cell.get_text(strip=True) if number_cell else ""
                        
                        # 제목 추출 (두 번째 td의 링크)
                        title_cell = row.select_one('td:nth-child(2)')
                        if title_cell:
                            title_link = title_cell.select_one('a')
                            title = title_link.get_text(strip=True) if title_link else title_cell.get_text(strip=True)
                            link = title_link.get('href') if title_link else ""
                            if link and not link.startswith('http'):
                                link = f"https://www.inha.ac.kr{{link}}"
                        else:
                            title = ""
                            link = ""
                        
                        # 날짜 추출 (세 번째 td)
                        date_cell = row.select_one('td:nth-child(3)')
                        date = date_cell.get_text(strip=True) if date_cell else ""
                        
                        # 카테고리 추출 (첫 번째 td에서 일반공지 등)
                        category = "일반공지"  # 기본값
                        
                        if number and title:  # 유효한 데이터인 경우만 추가
                            notice = {{
                                'number': number,
                                'title': title,
                                'date': date,
                                'category': category,
                                'link': link,
                                'crawled_at': datetime.now().isoformat()
                            }}
                            notices.append(notice)
                    
                    except Exception as e:
                        print(f"행 파싱 오류: {{e}}")
                        continue
                
                print(f"페이지 {{page}} 완료: {{len([n for n in notices if n.get('crawled_at', '').startswith(datetime.now().date().isoformat())])}}개 공지사항")
                
                # 요청 간 지연
                time.sleep(1)
                
            except Exception as e:
                print(f"페이지 {{page}} 크롤링 오류: {{e}}")
                break
        
        return notices
    
    def save_to_json(self, notices: List[Dict[str, Any]], filename: str = "inha_notices.json"):
        """결과를 JSON 파일로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)
        print(f"{{len(notices)}}개 공지사항을 {{filename}}에 저장했습니다.")
    
    def get_latest_notices(self, days: int = 7) -> List[Dict[str, Any]]:
        """최근 N일간의 공지사항만 필터링"""
        from datetime import datetime, timedelta
        
        all_notices = self.crawl_notices(max_pages=2)
        cutoff_date = datetime.now() - timedelta(days=days)
        
        recent_notices = []
        for notice in all_notices:
            try:
                notice_date = datetime.strptime(notice['date'], '%Y.%m.%d.')
                if notice_date >= cutoff_date:
                    recent_notices.append(notice)
            except:
                continue
        
        return recent_notices


# 사용 예시
if __name__ == "__main__":
    crawler = InhaNoticeCrawler()
    
    # 최근 공지사항 크롤링
    print("인하대 공지사항 크롤링 시작...")
    notices = crawler.crawl_notices(max_pages=2)
    
    print(f"총 {{len(notices)}}개 공지사항 수집")
    
    # JSON 파일로 저장
    crawler.save_to_json(notices)
    
    # 최근 3일간 공지사항만 확인
    recent = crawler.get_latest_notices(days=3)
    print(f"최근 3일간 {{len(recent)}}개 공지사항:")
    for notice in recent[:5]:  # 상위 5개만 출력
        print(f"- {{notice['title']}} ({{notice['date']}})")
'''
        
        return crawler_code
    
    def generate_crawler_config(self, page_structure: PageStructure) -> CrawlerConfig:
        """PageStructure에서 CrawlerConfig 생성"""
        
        selectors = {}
        for element in page_structure.content_elements:
            selectors[element.element_type] = element.css_selector
        
        config = CrawlerConfig(
            name="inha_notice_crawler",
            target_url=page_structure.url,
            selectors=selectors,
            output_format="json",
            delay=1.0,
            max_pages=5
        )
        
        return config
    
    def save_crawler_code(self, crawler_code: str, filename: str = "inha_crawler.py"):
        """생성된 크롤러 코드를 파일로 저장"""
        try:
            output_path = Path(filename)
            output_path.write_text(crawler_code, encoding='utf-8')
            self.logger.info(f"크롤러 코드 저장됨: {output_path.absolute()}")
            return str(output_path.absolute())
        except Exception as e:
            self.logger.error(f"크롤러 코드 저장 실패: {e}")
            raise
    
    def generate_and_save(self, page_structure: PageStructure, output_dir: str = ".") -> str:
        """크롤러 생성 및 저장"""
        
        # 크롤러 코드 생성
        crawler_code = self.generate_inha_crawler(page_structure)
        
        # 파일 저장
        output_path = Path(output_dir) / "inha_notice_crawler.py"
        saved_path = self.save_crawler_code(crawler_code, str(output_path))
        
        self.logger.info(f"인하대 공지사항 크롤러 생성 완료: {saved_path}")
        return saved_path


# 사용 예시
async def main():
    """크롤러 생성기 테스트"""
    from .html_analyzer import HTMLAnalyzer
    
    # HTML 분석
    analyzer = HTMLAnalyzer()
    await analyzer.llm_manager.initialize()
    
    # 페이지 구조 분석 (실패 시 기본 구조 사용)
    try:
        structure = await analyzer.analyze_page_structure("https://www.inha.ac.kr/kr/950/subview.do")
    except:
        # 분석 실패 시 기본 구조 사용
        from bs4 import BeautifulSoup
        structure = PageStructure(
            url="https://www.inha.ac.kr/kr/950/subview.do",
            page_type="list",
            content_elements=[
                ContentElement(
                    element_type="title",
                    css_selector="table tbody tr td:nth-child(2) a",
                    sample_content="공지사항 제목"
                ),
                ContentElement(
                    element_type="date", 
                    css_selector="table tbody tr td:nth-child(3)",
                    sample_content="2025.09.05"
                )
            ]
        )
    
    # 크롤러 생성
    generator = CrawlerGenerator()
    crawler_path = generator.generate_and_save(structure)
    
    print(f"크롤러 생성 완료: {crawler_path}")


if __name__ == "__main__":
    asyncio.run(main())
