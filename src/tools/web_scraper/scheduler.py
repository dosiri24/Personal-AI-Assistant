"""
웹 정보 수집 스케줄링 시스템

정기적인 웹 크롤링 작업을 관리하고
변경 감지 및 알림 기능을 제공합니다.
"""

import asyncio
import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import time
import sys
import os

# 크롤러 클래스를 직접 import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class CrawlJob:
    """크롤링 작업 정의"""
    job_id: str
    name: str
    url: str
    schedule_pattern: str  # cron 스타일: "*/30 * * * *" (매 30분)
    max_pages: int = 3
    enabled: bool = True
    last_run: Optional[str] = None
    last_hash: Optional[str] = None
    change_detected: bool = False
    error_count: int = 0
    max_errors: int = 5


@dataclass
class CrawlResult:
    """크롤링 결과"""
    job_id: str
    timestamp: str
    success: bool
    data_count: int
    changes_detected: bool
    content_hash: str
    error_message: Optional[str] = None
    execution_time: float = 0.0


class WebCrawlScheduler:
    """웹 크롤링 스케줄러"""
    
    def __init__(self, data_dir: str = "data/crawl_results"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs: Dict[str, CrawlJob] = {}
        self.results: List[CrawlResult] = []
        self.logger = logging.getLogger(__name__)
        self.is_running = False
        
        # 변경 감지 콜백
        self.change_callbacks: List[Callable[[CrawlResult], None]] = []
        
        # 기본 인하대 크롤링 작업 등록
        self._register_default_jobs()
    
    def _register_default_jobs(self):
        """기본 크롤링 작업 등록"""
        inha_job = CrawlJob(
            job_id="inha_notices",
            name="인하대 공지사항",
            url="https://www.inha.ac.kr/kr/950/subview.do",
            schedule_pattern="*/30 * * * *",  # 30분마다
            max_pages=2
        )
        self.add_job(inha_job)
    
    def add_job(self, job: CrawlJob):
        """크롤링 작업 추가"""
        self.jobs[job.job_id] = job
        self.logger.info(f"크롤링 작업 추가됨: {job.name} ({job.schedule_pattern})")
    
    def remove_job(self, job_id: str):
        """크롤링 작업 제거"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.logger.info(f"크롤링 작업 제거됨: {job_id}")
    
    def enable_job(self, job_id: str):
        """작업 활성화"""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self.logger.info(f"작업 활성화됨: {job_id}")
    
    def disable_job(self, job_id: str):
        """작업 비활성화"""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            self.logger.info(f"작업 비활성화됨: {job_id}")
    
    async def execute_job(self, job: CrawlJob) -> CrawlResult:
        """단일 크롤링 작업 실행"""
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        try:
            self.logger.info(f"크롤링 작업 시작: {job.name}")
            
            # 인하대 크롤러 실행
            if job.job_id == "inha_notices":
                notices = await self._crawl_inha_notices(job.max_pages)
                
                # 데이터 해시 계산
                content_hash = self._calculate_hash(notices)
                
                # 변경 감지
                changes_detected = (job.last_hash is None or 
                                  content_hash != job.last_hash)
                
                # 결과 저장
                if notices:
                    result_file = self.data_dir / f"{job.job_id}_{timestamp[:10]}.json"
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(notices, f, ensure_ascii=False, indent=2)
                
                # 작업 상태 업데이트
                job.last_run = timestamp
                job.last_hash = content_hash
                job.change_detected = changes_detected
                job.error_count = 0
                
                execution_time = time.time() - start_time
                
                result = CrawlResult(
                    job_id=job.job_id,
                    timestamp=timestamp,
                    success=True,
                    data_count=len(notices),
                    changes_detected=changes_detected,
                    content_hash=content_hash,
                    execution_time=execution_time
                )
                
                self.logger.info(f"크롤링 완료: {job.name} - {len(notices)}개 항목, 변경: {changes_detected}")
                
                # 변경 감지 시 콜백 실행
                if changes_detected and self.change_callbacks:
                    for callback in self.change_callbacks:
                        try:
                            callback(result)
                        except Exception as e:
                            self.logger.error(f"변경 감지 콜백 오류: {e}")
                
                return result
            
            else:
                raise NotImplementedError(f"크롤러가 구현되지 않은 작업: {job.job_id}")
        
        except Exception as e:
            execution_time = time.time() - start_time
            job.error_count += 1
            
            error_result = CrawlResult(
                job_id=job.job_id,
                timestamp=timestamp,
                success=False,
                data_count=0,
                changes_detected=False,
                content_hash="",
                error_message=str(e),
                execution_time=execution_time
            )
            
            self.logger.error(f"크롤링 실패: {job.name} - {e}")
            return error_result
    
    def _calculate_hash(self, data: Any) -> str:
        """데이터 해시 계산"""
        json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    async def _crawl_inha_notices(self, max_pages: int = 2) -> List[Dict[str, Any]]:
        """개선된 인하대 공지사항 크롤링 (고정공지 구분, 상세내용 포함)"""
        import requests
        from bs4 import BeautifulSoup
        import re
        
        notices = []
        base_url = "https://www.inha.ac.kr/kr/950/subview.do"
        detail_base_url = "https://www.inha.ac.kr"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        for page in range(1, max_pages + 1):
            try:
                page_url = f"{base_url}?page={page}"
                response = requests.get(page_url, headers=headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                notice_rows = soup.select('table tbody tr')
                
                for row_idx, row in enumerate(notice_rows):
                    try:
                        cells = row.find_all('td')
                        if len(cells) < 5:
                            continue
                        
                        category = cells[0].get_text(strip=True)
                        title_cell = cells[1]
                        title_link = title_cell.find('a')
                        
                        if title_link:
                            title = title_link.get_text(strip=True)
                            detail_link = title_link.get('href', '')
                            if detail_link and not detail_link.startswith('http'):
                                detail_link = f"{detail_base_url}{detail_link}"
                        else:
                            title = title_cell.get_text(strip=True)
                            detail_link = ""
                        
                        author = cells[2].get_text(strip=True)
                        date = cells[3].get_text(strip=True)
                        views = cells[4].get_text(strip=True)
                        
                        # 고정 공지 여부 판단
                        is_pinned = self._is_pinned_notice(row_idx, page, category, title)
                        
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
                        
                        # 중요 공지나 최신 공지만 상세 내용 크롤링 (성능 고려)
                        if is_pinned and detail_link:
                            try:
                                detail_info = await self._crawl_detail_content(detail_link)
                                notice.update(detail_info)
                            except Exception as e:
                                self.logger.error(f"상세 내용 크롤링 실패: {e}")
                        
                        notices.append(notice)
                    
                    except Exception as e:
                        self.logger.error(f"행 파싱 오류: {e}")
                        continue
                
                # 페이지 간 지연
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"페이지 {page} 크롤링 오류: {e}")
                break
        
        # 고정 공지를 앞으로 정렬
        notices.sort(key=lambda x: (not x['is_pinned'], x['page_number'], x['row_index']))
        
        return notices
    
    def _is_pinned_notice(self, row_index: int, page: int, category: str, title: str) -> bool:
        """고정 공지 여부 판단"""
        
        # 첫 페이지 상위 몇 개는 고정 공지일 가능성 높음
        if page == 1 and row_index <= 2:
            return True
        
        # 중요 키워드가 포함된 경우
        high_priority_keywords = [
            '등록금', '장학금', '졸업', '입학', '시험',
            '채용', '모집', '마감', '신청', '튜터링',
            '멘토링', '프로그램'
        ]
        
        # 제목에서 중요 키워드 체크
        for keyword in high_priority_keywords:
            if keyword in title:
                return True
        
        return False
    
    async def _crawl_detail_content(self, detail_url: str) -> Dict[str, Any]:
        """공지사항 상세 내용 크롤링"""
        detail_info = {
            'content': '',
            'attachments': [],
            'contact_info': {},
            'content_length': 0
        }
        
        try:
            import requests
            from bs4 import BeautifulSoup
            import re
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            response = requests.get(detail_url, headers=headers, timeout=10)
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 내용 추출
            content_elem = soup.select_one('.artclItem.viewForm')
            if content_elem:
                # 불필요한 태그 제거
                for tag in content_elem(['script', 'style']):
                    tag.decompose()
                
                content = content_elem.get_text(separator='\n', strip=True)
                content = re.sub(r'\n\s*\n', '\n\n', content)
                content = re.sub(r'[ \t]+', ' ', content)
                
                if len(content) > 50:
                    detail_info['content'] = content[:1000]  # 최대 1000자로 제한
                    detail_info['content_length'] = len(content)
            
            # 담당자 정보 추출
            text = soup.get_text()
            
            # 담당자 이름
            name_match = re.search(r'담당자[:\s]*([가-힣]+)', text)
            if name_match:
                detail_info['contact_info']['contact_person'] = name_match.group(1)
            
            # 전화번호
            phone_match = re.search(r'연락처[:\s]*([\d-]+)', text)
            if phone_match:
                detail_info['contact_info']['phone'] = phone_match.group(1)
        
        except Exception as e:
            self.logger.error(f"상세 내용 크롤링 오류: {e}")
        
        return detail_info
    
    async def run_once(self) -> List[CrawlResult]:
        """모든 활성 작업을 한 번 실행"""
        results = []
        
        for job in self.jobs.values():
            if job.enabled and job.error_count < job.max_errors:
                result = await self.execute_job(job)
                results.append(result)
                self.results.append(result)
        
        return results
    
    async def run_scheduler(self, interval: int = 60):
        """스케줄러 메인 루프 (초 단위 간격)"""
        self.is_running = True
        self.logger.info(f"스케줄러 시작됨 (간격: {interval}초)")
        
        while self.is_running:
            try:
                current_time = datetime.now()
                
                for job in self.jobs.values():
                    if (job.enabled and 
                        job.error_count < job.max_errors and
                        self._should_run_job(job, current_time)):
                        
                        result = await self.execute_job(job)
                        self.results.append(result)
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                self.logger.error(f"스케줄러 오류: {e}")
                await asyncio.sleep(interval)
    
    def _should_run_job(self, job: CrawlJob, current_time: datetime) -> bool:
        """작업 실행 시점 판단"""
        if job.last_run is None:
            return True
        
        try:
            last_run_time = datetime.fromisoformat(job.last_run)
            
            # 간단한 간격 기반 스케줄링
            if "*/30" in job.schedule_pattern:  # 30분마다
                return current_time - last_run_time >= timedelta(minutes=30)
            elif "*/60" in job.schedule_pattern:  # 1시간마다
                return current_time - last_run_time >= timedelta(hours=1)
            elif "0 */6" in job.schedule_pattern:  # 6시간마다
                return current_time - last_run_time >= timedelta(hours=6)
            elif "0 0" in job.schedule_pattern:  # 매일
                return current_time - last_run_time >= timedelta(days=1)
            
            # 기본: 30분 간격
            return current_time - last_run_time >= timedelta(minutes=30)
            
        except Exception:
            return True
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        self.is_running = False
        self.logger.info("스케줄러 중지됨")
    
    def add_change_callback(self, callback: Callable[[CrawlResult], None]):
        """변경 감지 콜백 추가"""
        self.change_callbacks.append(callback)
        self.logger.info("변경 감지 콜백 추가됨")
    
    def get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 조회"""
        active_jobs = sum(1 for job in self.jobs.values() if job.enabled)
        recent_results = [r for r in self.results if 
                         datetime.fromisoformat(r.timestamp) > 
                         datetime.now() - timedelta(hours=24)]
        
        return {
            "is_running": self.is_running,
            "total_jobs": len(self.jobs),
            "active_jobs": active_jobs,
            "recent_results": len(recent_results),
            "jobs": [asdict(job) for job in self.jobs.values()],
            "last_24h_results": [asdict(r) for r in recent_results[-10:]]
        }
    
    def get_latest_changes(self, hours: int = 24) -> List[CrawlResult]:
        """최근 변경 사항 조회"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        return [r for r in self.results if 
                r.changes_detected and 
                datetime.fromisoformat(r.timestamp) > cutoff]
    
    def save_state(self, filename: str = "scheduler_state.json"):
        """스케줄러 상태 저장"""
        state = {
            "jobs": {job_id: asdict(job) for job_id, job in self.jobs.items()},
            "results": [asdict(r) for r in self.results[-100:]]  # 최근 100개만
        }
        
        state_file = self.data_dir / filename
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"스케줄러 상태 저장됨: {state_file}")
    
    def load_state(self, filename: str = "scheduler_state.json"):
        """스케줄러 상태 복원"""
        state_file = self.data_dir / filename
        
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                # 작업 복원
                for job_id, job_data in state.get("jobs", {}).items():
                    self.jobs[job_id] = CrawlJob(**job_data)
                
                # 결과 복원
                for result_data in state.get("results", []):
                    self.results.append(CrawlResult(**result_data))
                
                self.logger.info(f"스케줄러 상태 복원됨: {len(self.jobs)}개 작업")
                
            except Exception as e:
                self.logger.error(f"상태 복원 실패: {e}")


# 변경 감지 콜백 예시
def on_content_change(result: CrawlResult):
    """콘텐츠 변경 시 알림"""
    print(f"🔔 변경 감지: {result.job_id}")
    print(f"   시간: {result.timestamp}")
    print(f"   항목 수: {result.data_count}")
    print(f"   해시: {result.content_hash[:8]}...")


# 사용 예시
async def main():
    """스케줄러 테스트"""
    
    # 스케줄러 초기화
    scheduler = WebCrawlScheduler()
    
    # 변경 감지 콜백 등록
    scheduler.add_change_callback(on_content_change)
    
    # 상태 복원
    scheduler.load_state()
    
    print("📅 웹 크롤링 스케줄러 시작")
    print(f"등록된 작업: {len(scheduler.jobs)}개")
    
    # 한 번 실행 테스트
    print("\n🔄 모든 작업 실행 중...")
    results = await scheduler.run_once()
    
    for result in results:
        status = "✅ 성공" if result.success else "❌ 실패"
        change = "🔄 변경됨" if result.changes_detected else "⚪ 변경없음"
        print(f"{status} {change} {result.job_id}: {result.data_count}개 항목")
    
    # 상태 확인
    status = scheduler.get_status()
    print(f"\n📊 스케줄러 상태:")
    print(f"- 활성 작업: {status['active_jobs']}/{status['total_jobs']}")
    print(f"- 최근 24시간 결과: {status['recent_results']}개")
    
    # 최근 변경사항
    changes = scheduler.get_latest_changes()
    if changes:
        print(f"\n🔔 최근 변경사항 ({len(changes)}개):")
        for change in changes[-3:]:
            print(f"- {change.job_id}: {change.timestamp[:19]}")
    
    # 상태 저장
    scheduler.save_state()
    
    # 지속적 실행 (테스트에서는 주석 처리)
    # print("\n⏰ 스케줄러 시작 (Ctrl+C로 중지)")
    # try:
    #     await scheduler.run_scheduler(interval=30)
    # except KeyboardInterrupt:
    #     print("\n⏹️ 스케줄러 중지됨")
    #     scheduler.stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
