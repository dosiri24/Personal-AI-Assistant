"""
Apple MCP 관련 CLI 명령어들

외부 Apple MCP 서버 관리, 테스트, 연결 상태 확인 등
"""

import click
import asyncio
import subprocess
import os
import psutil
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

logger = get_logger(__name__)


@click.group()
def apple():
    """Apple MCP 서버 관리 및 테스트"""
    pass


@apple.command()
@click.option("--port", default=3001, help="Apple MCP 서버 포트")
@click.option("--background", "-b", is_flag=True, help="백그라운드에서 실행")
def start(port: int, background: bool):
    """Apple MCP 서버 시작"""
    apple_mcp_path = Path("external/apple-mcp")
    
    if not apple_mcp_path.exists():
        click.echo("❌ Apple MCP 서버가 설치되지 않았습니다.")
        click.echo("다음 명령어로 설치하세요: pai apple install")
        return
    
    click.echo("🍎 Apple MCP 서버 시작 중...")
    
    try:
        if background:
            # 백그라운드에서 실행
            process = subprocess.Popen(
                ["bun", "run", "index.ts"],
                cwd=apple_mcp_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "PORT": str(port)}
            )
            
            # PID 파일 저장
            pid_file = Path("data/apple-mcp.pid")
            pid_file.parent.mkdir(exist_ok=True)
            pid_file.write_text(str(process.pid))
            
            click.echo(f"✅ Apple MCP 서버가 백그라운드에서 시작되었습니다 (PID: {process.pid})")
        else:
            # 포그라운드에서 실행
            subprocess.run(
                ["bun", "run", "index.ts"],
                cwd=apple_mcp_path,
                env={**os.environ, "PORT": str(port)}
            )
    except FileNotFoundError:
        click.echo("❌ Bun이 설치되지 않았습니다.")
        click.echo("https://bun.sh에서 Bun을 설치하세요.")
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Apple MCP 서버 시작 실패: {e}")


@apple.command()
def stop():
    """Apple MCP 서버 중지"""
    pid_file = Path("data/apple-mcp.pid")
    
    if not pid_file.exists():
        click.echo("⚠️ 실행 중인 Apple MCP 서버가 없습니다.")
        return
    
    try:
        pid = int(pid_file.read_text().strip())
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=10)
        
        pid_file.unlink()
        click.echo("✅ Apple MCP 서버가 중지되었습니다.")
    except (ValueError, psutil.NoSuchProcess):
        click.echo("⚠️ Apple MCP 서버 프로세스를 찾을 수 없습니다.")
        if pid_file.exists():
            pid_file.unlink()
    except psutil.TimeoutExpired:
        click.echo("⚠️ 프로세스 종료 시간 초과, 강제 종료합니다.")
        process.kill()
        pid_file.unlink()


@apple.command()
def status():
    """Apple MCP 서버 상태 확인"""
    pid_file = Path("data/apple-mcp.pid")
    
    if not pid_file.exists():
        click.echo("🔴 Apple MCP 서버: 중지됨")
        return
    
    try:
        pid = int(pid_file.read_text().strip())
        process = psutil.Process(pid)
        
        if process.is_running():
            click.echo(f"🟢 Apple MCP 서버: 실행 중 (PID: {pid})")
            click.echo(f"   메모리 사용량: {process.memory_info().rss / 1024 / 1024:.1f} MB")
            click.echo(f"   CPU 사용량: {process.cpu_percent():.1f}%")
        else:
            click.echo("🔴 Apple MCP 서버: 중지됨")
            pid_file.unlink()
    except (ValueError, psutil.NoSuchProcess):
        click.echo("🔴 Apple MCP 서버: 중지됨")
        if pid_file.exists():
            pid_file.unlink()


@apple.command()
def install():
    """Apple MCP 서버 설치"""
    click.echo("🍎 Apple MCP 서버 설치 중...")
    
    external_dir = Path("external")
    apple_mcp_path = external_dir / "apple-mcp"
    
    # external 디렉토리 생성
    external_dir.mkdir(exist_ok=True)
    
    if apple_mcp_path.exists():
        click.echo("⚠️ Apple MCP 서버가 이미 설치되어 있습니다.")
        if click.confirm("다시 설치하시겠습니까?"):
            import shutil
            shutil.rmtree(apple_mcp_path)
        else:
            return
    
    try:
        # Git clone
        click.echo("📥 리포지토리 다운로드 중...")
        subprocess.run([
            "git", "clone", 
            "https://github.com/supermemoryai/apple-mcp.git",
            str(apple_mcp_path)
        ], check=True)
        
        # Bun install
        click.echo("📦 의존성 설치 중...")
        subprocess.run(["bun", "install"], cwd=apple_mcp_path, check=True)
        
        click.echo("✅ Apple MCP 서버 설치 완료!")
        click.echo("")
        click.echo("🔐 다음 단계: macOS 권한 설정")
        click.echo("다음 명령어를 실행하세요: pai apple setup-permissions")
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ 설치 실패: {e}")
    except FileNotFoundError:
        click.echo("❌ Git 또는 Bun이 설치되지 않았습니다.")
        click.echo("필요한 도구들:")
        click.echo("- Git: https://git-scm.com/")
        click.echo("- Bun: https://bun.sh/")


@apple.command()
def setup_permissions():
    """macOS 권한 설정 가이드"""
    click.echo("🔐 Apple MCP macOS 권한 설정 가이드")
    click.echo("=" * 40)
    
    # 권한 설정 스크립트 실행
    script_path = Path("scripts/setup-apple-permissions.sh")
    if script_path.exists():
        subprocess.run(["bash", str(script_path)])
    else:
        click.echo("⚠️ 권한 설정 스크립트를 찾을 수 없습니다.")
    
    # 시스템 설정 열기
    if click.confirm("시스템 설정을 열어 권한을 설정하시겠습니까?"):
        subprocess.run([
            "open", 
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Automation"
        ])


@apple.command()
@click.option("--app", help="테스트할 Apple 앱 (contacts, notes, messages, etc.)")
def test(app: Optional[str]):
    """Apple MCP 서버 기능 테스트"""
    apple_mcp_path = Path("external/apple-mcp")
    
    if not apple_mcp_path.exists():
        click.echo("❌ Apple MCP 서버가 설치되지 않았습니다.")
        click.echo("다음 명령어로 설치하세요: pai apple install")
        return
    
    click.echo("🧪 Apple MCP 서버 테스트 시작...")
    
    try:
        if app:
            # 특정 앱 테스트
            test_file = f"tests/integration/{app}.test.ts"
            if not (apple_mcp_path / test_file).exists():
                test_file = f"tests/integration/{app}-simple.test.ts"
            
            click.echo(f"📱 {app} 앱 테스트 중...")
            result = subprocess.run([
                "bun", "test", test_file, "--preload", "./tests/setup.ts"
            ], cwd=apple_mcp_path, capture_output=True, text=True)
        else:
            # 모든 테스트 실행
            click.echo("📱 모든 Apple 앱 테스트 중...")
            result = subprocess.run([
                "bun", "test", "tests/integration/", "--preload", "./tests/setup.ts"
            ], cwd=apple_mcp_path, capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("✅ 테스트 성공!")
        else:
            click.echo("❌ 테스트 실패")
            if result.stderr:
                click.echo("오류:")
                click.echo(result.stderr)
            
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ 테스트 실행 실패: {e}")


@apple.command()
def tools():
    """사용 가능한 Apple MCP 도구 목록"""
    click.echo("🛠️ Apple MCP 지원 도구들")
    click.echo("=" * 30)
    click.echo("")
    
    tools_info = [
        ("📱 Messages", "메시지 전송/읽기/예약, 읽지 않은 메시지 확인"),
        ("📝 Notes", "노트 생성/검색/조회, 폴더별 관리"),
        ("👥 Contacts", "연락처 검색/조회, 전화번호 찾기"),
        ("📧 Mail", "메일 전송/검색, 읽지 않은 메일 확인, 계정/메일박스별 관리"),
        ("⏰ Reminders", "미리 알림 생성/검색, 목록별 관리"),
        ("📅 Calendar", "이벤트 생성/검색, 일정 조회"),
        ("🗺️ Maps", "위치 검색/저장, 길찾기/가이드 관리"),
        ("🌐 Web Search", "Safari 기반 웹 검색 및 결과 스크래핑")
    ]
    
    for tool_name, description in tools_info:
        click.echo(f"{tool_name}")
        click.echo(f"  {description}")
        click.echo("")


# Apple 명령어 그룹을 리스트로 내보내기
apple_commands = [apple]
