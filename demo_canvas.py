#!/usr/bin/env python3
"""
캔버스 시스템 실전 데모
사용자 요청 "바탕화면 스크린샷 삭제"를 처리하여 중복 작업 방지 기능을 시연
"""

import os
import sys
import asyncio
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, '/Users/taesooa/Python for Macbook/Personal-AI-Assistant')

from src.ai_engine.task_canvas import ExternalTaskCanvas, TaskStatus

async def demo_canvas_workflow():
    """실제 사용자 시나리오 데모"""
    
    print("🎯 캔버스 시스템 실전 데모: 중복 작업 방지")
    print("=" * 60)
    
    canvas_manager = ExternalTaskCanvas()
    
    # 시나리오 1: 첫 번째 요청 - 새로운 캔버스 생성
    print("\n📝 시나리오 1: 첫 번째 요청")
    print("-" * 40)
    
    user_request = "바탕화면에 스크린샷 파일 있는 거좀 다 삭제해줄래"
    print(f"사용자 요청: {user_request}")
    
    # 기존 캔버스 검색
    existing = canvas_manager.find_existing_canvas(user_request)
    if existing:
        print(f"✅ 기존 캔버스 발견: {existing.canvas_id}")
        canvas = existing
    else:
        print("📋 새로운 캔버스 생성 중...")
        steps = [
            {'title': '바탕화면 경로 확인', 'description': '현재 사용자의 바탕화면 위치 파악'},
            {'title': '파일 목록 조회', 'description': '바탕화면에 있는 모든 파일 확인'},
            {'title': '스크린샷 파일 식별', 'description': '파일명으로 스크린샷 파일 찾기'},
            {'title': '스크린샷 파일 삭제', 'description': '식별된 스크린샷 파일들 삭제'}
        ]
        canvas = canvas_manager.create_canvas(user_request, steps)
        print(f"✅ 새로운 캔버스 생성: {canvas.canvas_id}")
    
    print("\n📋 초기 작업 현황:")
    print(canvas_manager.generate_progress_summary(canvas))
    
    # 작업 실행 시뮬레이션
    print("\n🔄 작업 실행 시뮬레이션:")
    print("-" * 40)
    
    # 1단계: 바탕화면 경로 확인
    print("1️⃣ 바탕화면 경로 확인 중...")
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_1",
        status=TaskStatus.IN_PROGRESS
    )
    await asyncio.sleep(1)  # 시뮬레이션 지연
    
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_1",
        status=TaskStatus.COMPLETED,
        result="바탕화면 경로: /Users/taesooa/Desktop"
    )
    print("   ✅ 완료")
    
    # 2단계: 파일 목록 조회
    print("2️⃣ 파일 목록 조회 중...")
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_2",
        status=TaskStatus.IN_PROGRESS
    )
    await asyncio.sleep(1)
    
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_2",
        status=TaskStatus.COMPLETED,
        result="총 14개 파일 발견 (폴더 포함)"
    )
    print("   ✅ 완료")
    
    # 3단계: 스크린샷 파일 식별
    print("3️⃣ 스크린샷 파일 식별 중...")
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_3",
        status=TaskStatus.IN_PROGRESS
    )
    await asyncio.sleep(1)
    
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_3",
        status=TaskStatus.COMPLETED,
        result="1개의 스크린샷 파일 발견: 스크린샷 2025-09-13 오후 7.30.45.png"
    )
    print("   ✅ 완료")
    
    # 4단계: 스크린샷 파일 삭제
    print("4️⃣ 스크린샷 파일 삭제 중...")
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_4",
        status=TaskStatus.IN_PROGRESS
    )
    await asyncio.sleep(1)
    
    canvas_manager.update_step_status(
        canvas=canvas,
        step_id="step_4",
        status=TaskStatus.COMPLETED,
        result="스크린샷 파일 삭제 완료"
    )
    print("   ✅ 완료")
    
    print("\n📋 작업 완료 현황:")
    print(canvas_manager.generate_progress_summary(canvas))
    
    # 시나리오 2: 동일한 요청 재실행 - 중복 작업 방지
    print("\n" + "=" * 60)
    print("📝 시나리오 2: 동일한 요청 재실행 (중복 작업 방지)")
    print("-" * 40)
    
    # 사용자가 같은 요청을 또 함
    same_request = "바탕화면 스크린샷 파일 삭제해줘"  # 약간 다른 표현
    print(f"사용자 요청: {same_request}")
    
    # 기존 캔버스 검색
    existing_canvas = canvas_manager.find_existing_canvas(same_request)
    
    if existing_canvas:
        print(f"✅ 기존 캔버스 발견: {existing_canvas.canvas_id}")
        print(f"📊 진행률: {existing_canvas.completion_percentage:.1f}%")
        
        if existing_canvas.status == TaskStatus.COMPLETED:
            print("🚫 이미 완료된 작업입니다!")
            print("\n📋 이전 작업 결과:")
            print(canvas_manager.generate_progress_summary(existing_canvas))
            print("\n💡 중복 작업이 방지되었습니다.")
        else:
            print("🔄 진행 중인 작업을 계속합니다...")
    else:
        print("❌ 기존 캔버스를 찾지 못함 (새로운 작업으로 처리)")
    
    # 시나리오 3: 다른 표현으로 같은 요청
    print("\n" + "=" * 60)
    print("📝 시나리오 3: 다른 표현으로 같은 요청")
    print("-" * 40)
    
    variations = [
        "바탕화면 스크린샷 정리해줘",
        "desktop screenshot files cleanup",
        "스크린샷 파일들 지워줄래"
    ]
    
    for variation in variations:
        print(f"\n변형 요청: '{variation}'")
        found = canvas_manager.find_existing_canvas(variation)
        if found:
            print(f"   ✅ 기존 작업 연결: {found.canvas_id[:16]}...")
        else:
            print("   ❌ 새로운 작업으로 인식됨")
    
    print("\n🎉 데모 완료!")
    print("\n📊 최종 통계:")
    print(f"   - 캔버스 ID: {canvas.canvas_id}")
    print(f"   - 완료율: {canvas.completion_percentage:.1f}%")
    print(f"   - 상태: {canvas.status.value}")
    print(f"   - 생성시간: {canvas.created_at}")
    print(f"   - 업데이트: {canvas.updated_at}")

if __name__ == "__main__":
    asyncio.run(demo_canvas_workflow())
