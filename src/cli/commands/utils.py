"""
CLI 명령어들의 공통 유틸리티 함수들
"""

import asyncio
import click


def async_command(f):
    """비동기 함수를 동기 클릭 명령어로 래핑하는 데코레이터"""
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def handle_errors(f):
    """명령어 실행 중 발생하는 오류를 처리하는 데코레이터"""
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            click.echo(f"❌ 오류 발생: {e}")
            import traceback
            if click.get_current_context().obj.get('debug', False):
                traceback.print_exc()
            return 1
    return wrapper


def format_status(status: bool, success_msg: str, fail_msg: str) -> str:
    """상태에 따른 메시지 포맷팅"""
    if status:
        return f"✅ {success_msg}"
    else:
        return f"❌ {fail_msg}"


def format_service_status(status_data: dict) -> str:
    """서비스 상태 정보를 포맷팅"""
    lines = []
    for service, data in status_data.items():
        if isinstance(data, dict):
            status_icon = "🟢" if data.get('running', False) else "🔴"
            pid = data.get('pid', 'N/A')
            uptime = data.get('uptime', 'N/A')
            lines.append(f"{status_icon} {service}: PID {pid}, Uptime {uptime}")
        else:
            status_icon = "🟢" if data else "🔴"
            lines.append(f"{status_icon} {service}")
    return "\n".join(lines)


def confirm_action(message: str, default: bool = False) -> bool:
    """사용자에게 확인을 요청"""
    return click.confirm(message, default=default)
