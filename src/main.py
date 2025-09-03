#!/usr/bin/env python3
"""
Personal AI Assistant - 메인 엔트리포인트

Discord를 통해 자연어 명령을 받아 에이전틱 AI가 스스로 판단하고 
MCP 도구를 활용하여 임무를 완수하는 지능형 개인 비서
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cli.main import cli

if __name__ == "__main__":
    cli()
