"""
Personal AI from .commands import (
    service_commands, 
    testing_commands, 
    monitoring_commands, 
    tools_group,
    notion_group,
    optimization_commands,
    apple_commands,
    apple_apps
) CLI - 모듈화된 메인 파일

기존 2276줄의 단일 파일을 기능별로 모듈화하여
유지보수성과 가독성을 대폭 개선한 새로운 CLI 진입점입니다.
"""

import time
import click
import asyncio
from pathlib import Path

# 로깅 설정
from src.utils.logger import get_logger

# 모듈화된 명령어 그룹들
from src.cli.commands import (
    service_commands,
    testing_commands,
    monitoring_commands, 
    tools_group,
    notion_group,
    optimization_commands,
    apple_commands
)

# Apple 앱 명령어 그룹 import
from src.cli.commands.apple_apps_commands import apple_apps


@click.group()
@click.version_option(version="1.0.0", prog_name="Personal AI Assistant")
@click.option("--log-level", default="INFO", help="로그 레벨 설정 (DEBUG, INFO, WARNING, ERROR)")
@click.pass_context
def cli(ctx, log_level):
    """Personal AI Assistant - 지능형 개인 비서

    Discord를 통해 자연어 명령을 받아 에이전틱 AI가 스스로 판단하고 
    MCP 도구를 활용하여 임무를 완수하는 지능형 개인 비서
    """
    # Context 초기화
    ctx.ensure_object(dict)
    ctx.obj['log_level'] = log_level
    
    # 로깅 설정
    logger = get_logger("cli")
    logger.info(f"Personal AI Assistant CLI 시작됨 (로그 레벨: {log_level})")


# ========== 서비스 관리 명령어들 등록 ==========
for command in service_commands:
    cli.add_command(command)

# ========== 테스트 명령어들 등록 ==========
for command in testing_commands:
    cli.add_command(command)

# ========== 모니터링 명령어들 등록 ==========
for command in monitoring_commands:
    cli.add_command(command)

# ========== 최적화 명령어들 등록 ==========
for command in optimization_commands:
    cli.add_command(command)

# ========== 그룹 명령어들 등록 ==========
cli.add_command(tools_group)
cli.add_command(notion_group)

# ========== Apple MCP 명령어들 등록 ==========
for command in apple_commands:
    cli.add_command(command)

# ========== Apple 앱 명령어들 등록 ==========
cli.add_command(apple_apps)


def _start_service_main(dev_mode: bool = True):
    """실제 서비스 메인 로직"""
    logger = get_logger("service")
    
    try:
        logger.info("AI Assistant 서비스 초기화 시작")
        
        # TODO: Discord Bot 초기화
        click.echo("⏳ Discord Bot 초기화 중...")
        logger.info("Discord Bot 초기화")
        time.sleep(1)  # 임시 대기
        
        # TODO: AI Engine 초기화
        click.echo("⏳ AI Engine 초기화 중...")
        logger.info("AI Engine 초기화")
        time.sleep(1)  # 임시 대기
        
        # TODO: 데이터베이스 연결
        click.echo("⏳ 데이터베이스 연결 중...")
        logger.info("데이터베이스 연결")
        time.sleep(1)  # 임시 대기
        
        if dev_mode:
            click.echo("✅ AI Assistant가 개발 모드로 시작되었습니다!")
            click.echo("   Ctrl+C로 종료할 수 있습니다.")
        
        logger.info("AI Assistant 서비스 시작 완료")
        
        # 메인 이벤트 루프
        while True:
            # TODO: 실제 서비스 로직 구현
            time.sleep(1)
            
    except KeyboardInterrupt:
        if dev_mode:
            click.echo("\n⏹️  종료 신호를 받았습니다...")
        logger.info("서비스 종료 요청")
    except Exception as e:
        logger.error(f"서비스 실행 중 오류: {e}")
        raise
    finally:
        logger.info("AI Assistant 서비스 종료")


if __name__ == "__main__":
    cli()
