#!/usr/bin/env python3
"""
인하대학교 최근 공지사항 5개 내용 정리 테스트
"""

import json
from datetime import datetime
from typing import List, Dict, Any

def load_notices() -> Dict[str, Any]:
    """JSON 파일에서 공지사항 데이터 로드"""
    try:
        with open('inha_notices_enhanced.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ 공지사항 데이터 파일을 찾을 수 없습니다.")
        return {}
    except json.JSONDecodeError:
        print("❌ JSON 파일 형식이 잘못되었습니다.")
        return {}

def format_date(date_str: str) -> str:
    """날짜 형식 정리"""
    return date_str.replace('.', '-').rstrip('-')

def get_recent_notices(notices: List[Dict], count: int = 5) -> List[Dict]:
    """최신 공지사항 추출 (날짜순 정렬)"""
    try:
        # 날짜를 기준으로 정렬 (최신순)
        sorted_notices = sorted(
            notices, 
            key=lambda x: datetime.strptime(x['date'].replace('.', '').strip(), '%Y%m%d'), 
            reverse=True
        )
        return sorted_notices[:count]
    except (ValueError, KeyError) as e:
        print(f"⚠️ 날짜 정렬 중 오류 발생: {e}")
        # 순서대로 상위 5개 반환
        return notices[:count]

def summarize_notice(notice: Dict) -> str:
    """개별 공지사항 요약"""
    title = notice.get('title', '제목 없음')
    author = notice.get('author', '작성자 미상')
    date = format_date(notice.get('date', '날짜 미상'))
    views = notice.get('views', '0')
    content = notice.get('content', '').strip()
    
    # 중요도 표시
    priority_icon = "📌" if notice.get('is_pinned', False) else "📄"
    
    # 첨부파일 정보
    attachments = notice.get('attachments', [])
    attachment_info = f" (📎{len(attachments)}개 첨부)" if attachments else ""
    
    # 연락처 정보
    contact = notice.get('contact_info', {})
    contact_info = ""
    if contact:
        contact_person = contact.get('contact_person', '')
        phone = contact.get('phone', '')
        email = contact.get('email', '')
        
        contact_parts = []
        if contact_person:
            contact_parts.append(f"담당자: {contact_person}")
        if phone:
            contact_parts.append(f"연락처: {phone}")
        if email:
            contact_parts.append(f"이메일: {email}")
        
        if contact_parts:
            contact_info = f"\n   📞 {' | '.join(contact_parts)}"
    
    # 내용 요약 (최대 200자)
    content_summary = ""
    if content and len(content) > 10:
        # 개행 제거 및 정리
        content_clean = ' '.join(content.split())
        if len(content_clean) > 200:
            content_summary = f"\n   💬 {content_clean[:200]}..."
        else:
            content_summary = f"\n   💬 {content_clean}"
    
    summary = f"{priority_icon} **{title}**{attachment_info}\n"
    summary += f"   📅 {date} | 👤 {author} | 👀 {views}회 조회"
    summary += contact_info
    summary += content_summary
    
    return summary

def generate_report(data: Dict[str, Any]) -> str:
    """종합 리포트 생성"""
    if not data or 'notices' not in data:
        return "❌ 공지사항 데이터가 없습니다."
    
    notices = data['notices']
    crawl_info = data.get('crawl_info', {})
    
    # 헤더
    report = "🏫 **인하대학교 최근 공지사항 TOP 5 요약**\n"
    report += "=" * 60 + "\n\n"
    
    # 크롤링 정보
    timestamp = crawl_info.get('timestamp', '')
    if timestamp:
        crawl_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        report += f"📊 **데이터 수집 정보**\n"
        report += f"   🕐 수집 시간: {crawl_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        report += f"   📈 총 공지사항: {crawl_info.get('total_notices', 0)}개\n"
        report += f"   📌 중요 공지: {crawl_info.get('pinned_notices', 0)}개\n"
        report += f"   📄 상세 내용: {crawl_info.get('notices_with_content', 0)}개\n"
        report += f"   📎 첨부파일: {crawl_info.get('notices_with_attachments', 0)}개\n\n"
    
    # 최신 공지사항 5개 추출
    recent_notices = get_recent_notices(notices, 5)
    
    report += f"📋 **최신 공지사항 5개 상세 내용**\n"
    report += "-" * 60 + "\n\n"
    
    for i, notice in enumerate(recent_notices, 1):
        report += f"**{i}. {summarize_notice(notice)}**\n\n"
    
    # 통계 정보
    pinned_count = sum(1 for notice in recent_notices if notice.get('is_pinned', False))
    with_content_count = sum(1 for notice in recent_notices if notice.get('content', '').strip())
    with_attachments_count = sum(1 for notice in recent_notices if notice.get('attachments', []))
    
    report += "📊 **TOP 5 통계**\n"
    report += f"   📌 중요 공지: {pinned_count}개\n"
    report += f"   📄 상세 내용: {with_content_count}개\n"
    report += f"   📎 첨부파일: {with_attachments_count}개\n\n"
    
    # 카테고리 분석
    categories = {}
    for notice in recent_notices:
        title = notice.get('title', '')
        if '[' in title and ']' in title:
            # 대괄호 내 부서명 추출
            category = title[title.find('[')+1:title.find(']')]
            categories[category] = categories.get(category, 0) + 1
    
    if categories:
        report += "🏢 **부서별 분포**\n"
        for dept, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
            report += f"   • {dept}: {count}건\n"
        report += "\n"
    
    report += "=" * 60 + "\n"
    report += "✅ **테스트 완료**: 웹 스크래핑 및 데이터 분석이 성공적으로 수행되었습니다."
    
    return report

def main():
    """메인 함수"""
    print("🚀 인하대학교 공지사항 분석 시작...")
    
    # 데이터 로드
    data = load_notices()
    if not data:
        return
    
    # 리포트 생성
    report = generate_report(data)
    
    # 결과 출력
    print("\n" + report)
    
    # 파일로 저장
    output_filename = f"inha_notice_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n💾 리포트가 {output_filename} 파일로 저장되었습니다.")
    except Exception as e:
        print(f"⚠️ 파일 저장 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
