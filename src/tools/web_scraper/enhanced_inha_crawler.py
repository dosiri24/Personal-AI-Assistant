"""
개선된 인하대 공지사항 크롤러

- 고정 공지 vs 일반 공지 구분
- 상세 내용 크롤링 기능
- 첨부파일 정보 수집
"""

import asyncio
import requests
import time
import json
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import re


class EnhancedInhaNoticeCrawler:
    """개선된 인하대 공지사항 크롤러"""
    
    def __init__(self):
        self.base_url = "https://www.inha.ac.kr/kr/950/subview.do"
        self.detail_base_url = "https://www.inha.ac.kr"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    async def crawl_notices_with_details(self, max_pages: int = 2, include_content: bool = True) -> List[Dict[str, Any]]:
        """공지사항을 상세 내용과 함께 크롤링"""
        notices = []
        
        for page in range(1, max_pages + 1):
            try:
                page_url = f"{self.base_url}?page={page}"
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                notice_rows = soup.select('table tbody tr')
                
                for row_idx, row in enumerate(notice_rows):
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 5:
                            continue
                        
                        # 기본 정보 추출
                        category = cells[0].get_text(strip=True)
                        title_cell = cells[1]
                        title_link = None
                        if isinstance(title_cell, Tag):
                            title_link = title_cell.find('a')
                        
                        if title_link and isinstance(title_link, Tag):
                            title = title_link.get_text(strip=True)
                            detail_link_attr = title_link.get('href', '')
                            detail_link = str(detail_link_attr) if detail_link_attr else ""
                            if detail_link and not detail_link.startswith('http'):
                                detail_link = f"{self.detail_base_url}{detail_link}"
                        else:
                            title = title_cell.get_text(strip=True) if isinstance(title_cell, Tag) else str(title_cell)
                            detail_link = ""
                        
                        author = cells[2].get_text(strip=True)
                        date = cells[3].get_text(strip=True)
                        views = cells[4].get_text(strip=True)
                        
                        # 고정 공지 여부 판단
                        is_pinned = self._is_pinned_notice(row_idx, page, category, title)
                        
                        # 기본 공지사항 정보
                        notice = {
                            'category': category,
                            'title': title,
                            'author': author,
                            'date': date,
                            'views': views,
                            'link': detail_link,
                            'is_pinned': is_pinned,
                            'priority': 'high' if is_pinned else 'normal',
                            'crawled_at': datetime.now().isoformat(),
                            'page_number': page,
                            'row_index': row_idx
                        }
                        
                        # 상세 내용 크롤링 (옵션)
                        if include_content and detail_link:
                            detail_info = await self._crawl_detail_content(detail_link)
                            notice.update(detail_info)
                            
                            # 요청 간 지연 (상세 페이지 크롤링 시)
                            await asyncio.sleep(0.5)
                        
                        notices.append(notice)
                        
                        print(f"{'📌' if is_pinned else '📄'} {title[:50]}... 수집 완료")
                    
                    except Exception as e:
                        print(f"행 파싱 오류 (페이지 {page}, 행 {row_idx}): {e}")
                        continue
                
                # 페이지 간 지연
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"페이지 {page} 크롤링 오류: {e}")
                break
        
        # 고정 공지를 앞으로 정렬
        notices.sort(key=lambda x: (not x['is_pinned'], x['page_number'], x['row_index']))
        
        return notices
    
    def _is_pinned_notice(self, row_index: int, page: int, category: str, title: str) -> bool:
        """고정 공지 여부 판단"""
        
        # 첫 페이지 상위 몇 개는 고정 공지일 가능성 높음
        if page == 1 and row_index <= 2:
            return True
        
        # 카테고리나 제목에서 중요도 키워드 확인
        important_keywords = [
            '중요', '필수', '긴급', '주의', '공지',
            '등록', '장학', '모집', '신청',
            '변경', '연기', '취소'
        ]
        
        high_priority_keywords = [
            '등록금', '장학금', '졸업', '입학', '시험',
            '채용', '모집', '마감', '신청'
        ]
        
        # 제목에서 중요 키워드 체크
        for keyword in high_priority_keywords:
            if keyword in title:
                return True
        
        # 카테고리가 중요한 경우
        if category in ['중요공지', '긴급공지', '필수공지']:
            return True
        
        return False
    
    async def _crawl_detail_content(self, detail_url: str) -> Dict[str, Any]:
        """공지사항 상세 내용 크롤링"""
        detail_info = {
            'content': '',
            'attachments': [],
            'contact_info': {},
            'content_length': 0,
            'has_attachments': False
        }
        
        try:
            response = self.session.get(detail_url, timeout=10)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 내용 추출
            content = self._extract_content(soup)
            if content:
                detail_info['content'] = content
                detail_info['content_length'] = len(content)
            
            # 첨부파일 추출
            attachments = self._extract_attachments(soup)
            if attachments:
                detail_info['attachments'] = attachments
                detail_info['has_attachments'] = True
            
            # 담당자 정보 추출
            contact_info = self._extract_contact_info(soup)
            if contact_info:
                detail_info['contact_info'] = contact_info
        
        except Exception as e:
            print(f"상세 내용 크롤링 오류 ({detail_url}): {e}")
            detail_info['error'] = str(e)
        
        return detail_info
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """공지사항 본문 내용 추출"""
        content_selectors = [
            '.artclItem.viewForm',
            '.artclView',
            '.content',
            '.view_content',
            '[class*="content"]'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # 불필요한 태그 제거
                for tag in content_elem(['script', 'style', 'header', 'nav', 'footer']):
                    tag.decompose()
                
                # 텍스트 추출 및 정리
                content = content_elem.get_text(separator='\n', strip=True)
                
                # 연속된 공백과 줄바꿈 정리
                content = re.sub(r'\n\s*\n', '\n\n', content)
                content = re.sub(r'[ \t]+', ' ', content)
                
                # 의미있는 길이의 내용인 경우 반환
                if len(content) > 100:
                    return content[:2000]  # 최대 2000자로 제한
        
        return ""
    
    def _extract_attachments(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """첨부파일 정보 추출"""
        attachments = []
        
        # 첨부파일 링크 찾기
        attachment_selectors = [
            'a[href*="download"]',
            'a[href*="file"]',
            'a[href*=".pdf"]',
            'a[href*=".doc"]',
            'a[href*=".hwp"]',
            '.file_list a',
            '.attach a'
        ]
        
        for selector in attachment_selectors:
            for link in soup.select(selector):
                if isinstance(link, Tag):
                    filename = link.get_text(strip=True)
                    file_url_attr = link.get('href', '')
                    file_url = str(file_url_attr) if file_url_attr else ""
                    
                    # 파일 확장자 확인
                    if any(ext in filename.lower() for ext in ['.pdf', '.doc', '.hwp', '.xlsx', '.zip']):
                        if file_url and not file_url.startswith('http'):
                            file_url = f"{self.detail_base_url}{file_url}"
                        
                        attachments.append({
                            'name': filename,
                            'url': file_url,
                            'type': self._get_file_type(filename)
                        })
        
        # 중복 제거
        seen = set()
        unique_attachments = []
        for attach in attachments:
            if attach['name'] not in seen:
                seen.add(attach['name'])
                unique_attachments.append(attach)
        
        return unique_attachments
    
    def _extract_contact_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """담당자 연락처 정보 추출"""
        contact_info = {}
        
        # 텍스트에서 연락처 정보 패턴 매칭
        text = soup.get_text()
        
        # 담당자 이름
        name_pattern = r'담당자[:\s]*([가-힣]+)'
        name_match = re.search(name_pattern, text)
        if name_match:
            contact_info['contact_person'] = name_match.group(1)
        
        # 전화번호
        phone_pattern = r'연락처[:\s]*([\d-]+)'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            contact_info['phone'] = phone_match.group(1)
        
        # 이메일
        email_pattern = r'이메일[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        email_match = re.search(email_pattern, text)
        if email_match:
            contact_info['email'] = email_match.group(1)
        
        return contact_info
    
    def _get_file_type(self, filename: str) -> str:
        """파일 타입 분류"""
        filename_lower = filename.lower()
        
        if '.pdf' in filename_lower:
            return 'PDF'
        elif any(ext in filename_lower for ext in ['.doc', '.docx']):
            return 'Word'
        elif '.hwp' in filename_lower:
            return 'HWP'
        elif any(ext in filename_lower for ext in ['.xls', '.xlsx']):
            return 'Excel'
        elif any(ext in filename_lower for ext in ['.zip', '.rar']):
            return 'Archive'
        else:
            return 'Other'
    
    def save_enhanced_results(self, notices: List[Dict[str, Any]], filename: str = "inha_notices_enhanced.json"):
        """개선된 결과를 JSON 파일로 저장"""
        
        # 통계 정보 생성
        total_notices = len(notices)
        pinned_notices = len([n for n in notices if n['is_pinned']])
        with_content = len([n for n in notices if n.get('content')])
        with_attachments = len([n for n in notices if n.get('has_attachments')])
        
        result = {
            'crawl_info': {
                'timestamp': datetime.now().isoformat(),
                'total_notices': total_notices,
                'pinned_notices': pinned_notices,
                'notices_with_content': with_content,
                'notices_with_attachments': with_attachments
            },
            'notices': notices
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n📊 크롤링 완료 통계:")
        print(f"- 총 공지사항: {total_notices}개")
        print(f"- 고정 공지: {pinned_notices}개")
        print(f"- 상세 내용 포함: {with_content}개")
        print(f"- 첨부파일 포함: {with_attachments}개")
        print(f"- 저장 파일: {filename}")
    
    def get_summary(self, notices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """크롤링 결과 요약"""
        
        # 고정 공지와 일반 공지 분리
        pinned = [n for n in notices if n['is_pinned']]
        regular = [n for n in notices if not n['is_pinned']]
        
        return {
            'total_count': len(notices),
            'pinned_count': len(pinned),
            'regular_count': len(regular),
            'pinned_notices': [
                {
                    'title': n['title'],
                    'date': n['date'],
                    'category': n['category'],
                    'has_content': bool(n.get('content')),
                    'attachments_count': len(n.get('attachments', []))
                }
                for n in pinned[:5]  # 상위 5개만
            ],
            'latest_regular': [
                {
                    'title': n['title'],
                    'date': n['date'],
                    'category': n['category'],
                    'has_content': bool(n.get('content')),
                    'attachments_count': len(n.get('attachments', []))
                }
                for n in regular[:10]  # 상위 10개만
            ]
        }


# 사용 예시
async def main():
    """개선된 크롤러 테스트"""
    crawler = EnhancedInhaNoticeCrawler()
    
    print("🚀 개선된 인하대 공지사항 크롤링 시작...")
    print("- 고정 공지 vs 일반 공지 구분")
    print("- 상세 내용 및 첨부파일 정보 수집")
    print()
    
    # 상세 내용과 함께 크롤링 (처음 몇 개만)
    notices = await crawler.crawl_notices_with_details(max_pages=1, include_content=True)
    
    # 결과 저장
    crawler.save_enhanced_results(notices)
    
    # 요약 정보 출력
    summary = crawler.get_summary(notices)
    
    print(f"\n📌 고정 공지 ({summary['pinned_count']}개):")
    for notice in summary['pinned_notices']:
        attachments_info = f" 📎{notice['attachments_count']}개" if notice['attachments_count'] > 0 else ""
        content_info = " 📄상세" if notice['has_content'] else ""
        print(f"- {notice['title'][:50]}... ({notice['date']}){attachments_info}{content_info}")
    
    print(f"\n📄 최신 일반 공지 ({min(10, summary['regular_count'])}개):")
    for notice in summary['latest_regular'][:5]:  # 처음 5개만 표시
        attachments_info = f" 📎{notice['attachments_count']}개" if notice['attachments_count'] > 0 else ""
        content_info = " 📄상세" if notice['has_content'] else ""
        print(f"- {notice['title'][:50]}... ({notice['date']}){attachments_info}{content_info}")


if __name__ == "__main__":
    asyncio.run(main())
