"""
의사결정 엔진 테스트 스크립트

Step 3.3 구현이 제대로 작동하는지 테스트합니다.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import Settings
from src.ai_engine.llm_provider import GeminiProvider
from src.ai_engine.prompt_templates import PromptManager
from src.ai_engine.decision_engine import AgenticDecisionEngine, DecisionContext


async def test_decision_engine():
    """의사결정 엔진 테스트"""
    print("🧠 의사결정 엔진 테스트 시작...")
    
    try:
        # 설정 및 프로바이더 초기화
        settings = Settings()
        llm_provider = GeminiProvider(settings)
        prompt_manager = PromptManager()
        
        # LLM 프로바이더 초기화
        await llm_provider.initialize()
        print("✅ LLM 프로바이더 초기화 완료")
        
        # 의사결정 엔진 초기화
        decision_engine = AgenticDecisionEngine(llm_provider, prompt_manager)
        print("✅ 에이전틱 의사결정 엔진 초기화 완료")
        
        # 테스트 시나리오들
        test_scenarios = [
            {
                "user_message": "내일 오후 3시에 팀 회의 일정을 추가해줘",
                "user_id": "test_user_1",
                "description": "일정 관리 테스트"
            },
            {
                "user_message": "Python 프로젝트 폴더 만들고 main.py 파일 생성해줘",
                "user_id": "test_user_2",
                "description": "파일 조작 테스트"
            },
            {
                "user_message": "오늘 날씨 어때?",
                "user_id": "test_user_3",
                "description": "정보 조회 테스트"
            }
        ]
        
        # 각 시나리오 테스트
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n📋 테스트 {i}: {scenario['description']}")
            print(f"요청: '{scenario['user_message']}'")
            
            # 컨텍스트 생성
            context = DecisionContext(
                user_message=scenario['user_message'],
                user_id=scenario['user_id'],
                conversation_history=[],
                available_tools=decision_engine.get_available_tools(),
                current_time=datetime.now()
            )
            
            # 의사결정 수행
            decision = await decision_engine.make_decision(context)
            
            # 결과 출력
            print(f"🔧 선택된 도구: {', '.join(decision.selected_tools)}")
            print(f"📊 신뢰도: {decision.confidence_score:.2f} ({decision.confidence_level.value})")
            print(f"⏰ 예상 시간: {decision.estimated_time}초")
            print(f"💭 추론: {decision.reasoning[:100]}...")
            
            if decision.requires_user_input:
                print(f"❓ 추가 입력 필요: {decision.user_input_prompt}")
            
            if decision.execution_plan:
                print(f"📝 실행 계획: {len(decision.execution_plan)}개 단계")
                for step in decision.execution_plan[:2]:  # 처음 2단계만 출력
                    print(f"   {step.get('step', '?')}. {step.get('description', 'N/A')}")
            
            print("─" * 50)
        
        print("\n🎉 모든 테스트 완료!")
        
    except Exception as e:
        print(f"❌ 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_decision_engine())
