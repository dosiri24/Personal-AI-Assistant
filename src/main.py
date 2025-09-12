#!/usr/bin/env python3
"""
Personal AI Assistant - 메인 엔트리 포인트

리팩토링된 새로운 아키텍처의 메인 엔트리 포인트입니다.
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config import get_settings
from src.utils.logger import setup_logging, get_logger
# from src.infrastructure.container import setup_container  # TODO: 컨테이너 시스템 확인 필요
# from src.mcp.mcp_integration import get_unified_mcp_system  # TODO: 함수명 확인 필요


async def initialize_system():
    """시스템 초기화"""
    # 설정 로드
    settings = get_settings()
    
    # 로깅 설정
    setup_logging()
    
    logger = get_logger(__name__)
    logger.info("Personal AI Assistant 시작")
    logger.info(f"환경: {settings.environment}")
    logger.info(f"디버그 모드: {settings.debug}")
    
    # 의존성 주입 컨테이너 설정 (TODO: 구현 필요)
    # setup_container()
    logger.info("의존성 주입 컨테이너 설정 생략")
    
    # 통합 MCP 시스템 초기화 (TODO: 구현 필요)
    # mcp_system = get_unified_mcp_system()
    # await mcp_system.initialize()
    logger.info("MCP 시스템 초기화 생략")
    
    return settings, logger


async def run_cli_mode():
    """CLI 모드 실행 - 자연어 기반 실행기 사용"""
    settings, logger = await initialize_system()
    
    logger.info("CLI 모드로 실행")
    
    # 🌟 자연어 기반 시스템 초기화
    try:
        from src.ai_engine.react_engine.natural_planning import NaturalPlanningExecutor
        from src.ai_engine.llm_provider import GeminiProvider
        from src.ai_engine.agent_state import AgentContext
        from src.mcp.executor import ToolExecutor
        from src.mcp.registry import ToolRegistry
        
        # 컴포넌트 초기화
        llm_provider = GeminiProvider(settings)
        await llm_provider.initialize()
        
        tool_registry = ToolRegistry()
        tool_executor = ToolExecutor(tool_registry)
        
        # 자연어 실행기 생성
        natural_executor = NaturalPlanningExecutor(llm_provider, tool_executor)
        
        print("🌟 자연어 기반 Personal AI Assistant")
        print("JSON 구조 없이 순수 LLM 추론으로 동작합니다.")
        print("'exit' 또는 'quit'을 입력하면 종료됩니다.")
        print("=" * 50)
        
        session_count = 0
        
        while True:
            try:
                user_input = input("\n💭 목표를 말씀해주세요: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    print("👋 안녕히 가세요!")
                    break
                
                if not user_input:
                    continue
                
                session_count += 1
                print(f"\n🚀 세션 {session_count} 시작...")
                
                # 컨텍스트 생성
                context = AgentContext(
                    user_id="cli_user",
                    session_id=f"cli_session_{session_count}",
                    goal=user_input,
                    max_iterations=20
                )
                
                # 🎯 자연어 기반 목표 실행
                result = await natural_executor.execute_goal(user_input, context)
                
                print(f"\n📊 실행 결과:")
                print(f"성공: {'✅' if result.success else '❌'}")
                
                if result.success:
                    final_answer = result.final_answer if hasattr(result, 'final_answer') else str(result.scratchpad.final_result)
                    print(f"📝 답변: {final_answer}")
                else:
                    partial_result = result.metadata.get('partial_result', '작업을 완료하지 못했습니다.')
                    print(f"📝 부분 결과: {partial_result}")
                
                # 실행 정보
                if hasattr(result, 'metadata'):
                    iterations = result.metadata.get('iterations', 0)
                    execution_time = result.metadata.get('execution_time', 0)
                    print(f"📈 실행 정보: {iterations}회 반복, {execution_time:.2f}초 소요")
                
                # 상세 기록 (선택적으로 표시)
                print(f"\n📚 상세 실행 기록:")
                print(result.scratchpad.get_formatted_history())
                print("=" * 50)
                
            except KeyboardInterrupt:
                print("\n👋 종료합니다.")
                break
            except Exception as e:
                logger.error(f"CLI 실행 중 오류: {str(e)}", exc_info=True)
                print(f"❌ 오류가 발생했습니다: {str(e)}")
                print("다시 시도해주세요.")
                
    except ImportError as e:
        logger.error(f"자연어 시스템 로드 실패: {e}")
        print(f"❌ 자연어 시스템을 로드할 수 없습니다: {e}")
        print("기존 시스템을 사용합니다...")
        
        # 폴백: 기존 시스템 사용
        print("Personal AI Assistant CLI 모드")
        print("'exit' 또는 'quit'을 입력하면 종료됩니다.")
        print()
        
        while True:
            try:
                user_input = input("입력: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                if not user_input:
                    continue
                
                response = f"TODO: 자연어 시스템 연결 필요 - 입력: {user_input}"
                print(f"응답: {response}")
                print()
                
            except KeyboardInterrupt:
                print("\n종료합니다.")
                break
            except Exception as e:
                logger.error(f"CLI 모드 실행 중 오류: {str(e)}", exc_info=True)
            print(f"오류 발생: {str(e)}")


def main():
    """메인 함수"""
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "cli":
            asyncio.run(run_cli_mode())
        else:
            print(f"알 수 없는 모드: {mode}")
            print("사용법: python -m src.main [cli]")
    else:
        # 기본값: CLI 모드
        asyncio.run(run_cli_mode())


if __name__ == "__main__":
    main()
