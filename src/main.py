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

from src.infrastructure.config.settings import get_settings
from src.shared.logging import setup_logging, get_logger
from src.infrastructure.container import setup_container
from src.core.mcp_integration import get_unified_mcp_system


async def initialize_system():
    """시스템 초기화"""
    # 설정 로드
    settings = get_settings()
    
    # 로깅 설정
    setup_logging(
        log_level=settings.system.log_level.value,
        logs_dir=settings.system.logs_dir,
        enable_console=True,
        enable_file=True,
        enable_structured=True
    )
    
    logger = get_logger(__name__)
    logger.info("Personal AI Assistant 시작")
    logger.info(f"환경: {settings.environment}")
    logger.info(f"디버그 모드: {settings.debug}")
    
    # 의존성 주입 컨테이너 설정
    setup_container()
    logger.info("의존성 주입 컨테이너 설정 완료")
    
    # 통합 MCP 시스템 초기화
    mcp_system = get_unified_mcp_system()
    await mcp_system.initialize()
    logger.info("MCP 시스템 초기화 완료")
    
    return settings, logger


async def run_cli_mode():
    """CLI 모드 실행"""
    settings, logger = await initialize_system()
    
    logger.info("CLI 모드로 실행")
    
    # MCP 시스템 가져오기
    mcp_system = get_unified_mcp_system()
    
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
            
            # 사용자 요청 처리
            response = await mcp_system.process_user_request(user_input)
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
