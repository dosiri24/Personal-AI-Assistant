"""
인하대 공지사항 크롤러
자동 생성된 코드 - https://www.inha.ac.kr/kr/950/subview.do
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
        self.base_url = "https://www.inha.ac.kr/kr/950/subview.do"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def crawl_notices(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        """공지사항 크롤링"""
        notices = []
        
        for page in range(1, max_pages + 1):
            try:
                page_url = f"{self.base_url}?page={page}"
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 공지사항 테이블에서 데이터 추출
                notice_rows = soup.select('table tbody tr')
                
                for row in notice_rows:
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 5:  # 5개 컬럼이 없으면 스킵
                            continue
                        
                        # 카테고리/번호 (첫 번째 td)
                        category = cells[0].get_text(strip=True)
                        
                        # 제목 및 링크 (두 번째 td)
                        title_cell = cells[1]
                        title_link = title_cell.find('a')
                        if title_link:
                            title = title_link.get_text(strip=True)
                            link = title_link.get('href', '')
                            if link and not link.startswith('http'):
                                link = f"https://www.inha.ac.kr{link}"
                        else:
                            title = title_cell.get_text(strip=True)
                            link = ""
                        
                        # 작성자 (세 번째 td)
                        author = cells[2].get_text(strip=True)
                        
                        # 작성일 (네 번째 td)
                        date = cells[3].get_text(strip=True)
                        
                        # 조회수 (다섯 번째 td)
                        views = cells[4].get_text(strip=True)
                        
                        if title and date:  # 유효한 데이터인 경우만 추가
                            notice = {
                                'category': category,
                                'title': title,
                                'author': author,
                                'date': date,
                                'views': views,
                                'link': link,
                                'crawled_at': datetime.now().isoformat()
                            }
                            notices.append(notice)
                    
                    except Exception as e:
                        print(f"행 파싱 오류: {e}")
                        continue
                
                print(f"페이지 {page} 완료: {len([n for n in notices if n.get('crawled_at', '').startswith(datetime.now().date().isoformat())])}개 공지사항")
                
                # 요청 간 지연
                time.sleep(1)
                
            except Exception as e:
                print(f"페이지 {page} 크롤링 오류: {e}")
                break
        
        return notices
    
    def save_to_json(self, notices: List[Dict[str, Any]], filename: str = "inha_notices.json"):
        """결과를 JSON 파일로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(notices, f, ensure_ascii=False, indent=2)
        print(f"{len(notices)}개 공지사항을 {filename}에 저장했습니다.")
    
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
    
    print(f"총 {len(notices)}개 공지사항 수집")
    
    # JSON 파일로 저장
    crawler.save_to_json(notices)
    
    # 최근 3일간 공지사항만 확인
    recent = crawler.get_latest_notices(days=3)
    print(f"최근 3일간 {len(recent)}개 공지사항:")
    for notice in recent[:5]:  # 상위 5개만 출력
        print(f"- {notice['title']} ({notice['date']})")
