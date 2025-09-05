"""
모니터링 관련 명령어들 (logs, queue, sessions, process-message)
"""

import asyncio
import json
import click
from src.utils.logger import get_logger
from .utils import async_command, handle_errors


@click.command()
@click.option('--follow', '-f', is_flag=True, help='실시간 로그 추적 (tail -f)')
@click.option('--lines', '-n', default=50, help='표시할 라인 수')
@click.option('--log-type', default='all', help='로그 타입 (all, bot, ai, error)')
def logs(follow, lines, log_type):
    """AI Assistant 로그를 확인합니다."""
    from src.config import get_settings
    from pathlib import Path
    
    logger = get_logger("cli")
    settings = get_settings()
    logs_dir = settings.get_logs_dir()
    
    # 로그 파일 매핑
    log_files = {
        'all': ['personal_ai_assistant.log', 'discord_bot.log', 'ai_engine.log', 'errors.log'],
        'bot': ['discord_bot.log'],
        'ai': ['ai_engine.log'], 
        'error': ['errors.log'],
        'main': ['personal_ai_assistant.log']
    }
    
    target_files = log_files.get(log_type, log_files['all'])
    
    if follow:
        click.echo(f"📄 실시간 로그 추적 중... (Ctrl+C로 종료)")
        click.echo(f"🔍 로그 타입: {log_type}")
        # TODO: 실시간 로그 추적 구현
        click.echo("⚠️  실시간 추적 기능은 추후 구현 예정입니다.")
        return
    
    click.echo(f"📄 최근 {lines}줄 로그 조회 (타입: {log_type}):")
    
    for log_file in target_files:
        log_path = logs_dir / log_file
        
        if not log_path.exists():
            click.echo(f"❌ 로그 파일이 없습니다: {log_file}")
            continue
        
        click.echo(f"\n📝 {log_file}:")
        click.echo("-" * 50)
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                log_lines = f.readlines()
                
            # 최근 N줄만 표시
            recent_lines = log_lines[-lines:]
            
            for line in recent_lines:
                click.echo(line.rstrip())
                
            if len(log_lines) > lines:
                click.echo(f"\n... ({len(log_lines) - lines}줄 더 있음)")
                
        except Exception as e:
            click.echo(f"❌ 로그 파일 읽기 실패: {e}")
            logger.error(f"로그 파일 읽기 실패 ({log_file}): {e}")


@click.command()
@click.option("--clear", is_flag=True, help="모든 큐 메시지 삭제")
@click.option("--status", default="all", help="상태별 필터 (pending, processing, completed, failed, timeout)")
@click.option("--limit", default=10, help="표시할 메시지 수")
def queue(clear, status, limit):
    """메시지 큐 상태를 확인하고 관리합니다."""
    from src.discord_bot.message_queue import MessageQueue, MessageStatus
    
    logger = get_logger("cli")
    logger.info("메시지 큐 관리 요청")
    
    async def manage_queue():
        try:
            queue_manager = MessageQueue()
            
            if clear:
                # 큐 초기화 (개발용)
                click.echo("⚠️  큐 초기화는 아직 구현되지 않았습니다.")
                return
            
            # 큐 통계 표시
            stats = queue_manager.get_stats()
            
            click.echo("📊 메시지 큐 통계:")
            click.echo(f"   총 메시지: {stats.get('total_messages', 0)}개")
            click.echo(f"   최근 1시간: {stats.get('recent_messages', 0)}개")
            click.echo(f"   캐시 크기: {stats.get('cache_size', 0)}개")
            click.echo(f"   실행 상태: {'🟢 실행 중' if stats.get('is_running') else '🔴 중지됨'}")
            click.echo(f"   등록된 핸들러: {stats.get('handlers_registered', 0)}개")
            
            # 상태별 메시지 수
            status_counts = stats.get('status_counts', {})
            if status_counts:
                click.echo("\n📋 상태별 메시지:")
                for status_name, count in status_counts.items():
                    status_emoji = {
                        'pending': '⏳',
                        'processing': '🔄', 
                        'completed': '✅',
                        'failed': '❌',
                        'timeout': '⏰'
                    }.get(status_name, '📝')
                    click.echo(f"   {status_emoji} {status_name}: {count}개")
            
            # 대기 중인 메시지 표시
            if status == "all" or status == "pending":
                pending_messages = await queue_manager.get_pending_messages(limit)
                if pending_messages:
                    click.echo(f"\n⏳ 대기 중인 메시지 (최대 {limit}개):")
                    for msg in pending_messages:
                        click.echo(f"   📝 {msg.id[:8]}... | 사용자: {msg.user_id} | {msg.created_at.strftime('%H:%M:%S')}")
                        click.echo(f"      내용: {msg.content[:50]}...")
            
        except Exception as e:
            logger.error(f"큐 관리 실패: {e}", exc_info=True)
            click.echo(f"❌ 큐 관리 실패: {e}")
    
    asyncio.run(manage_queue())


@click.command()
@click.option("--user-id", type=int, help="특정 사용자 ID로 필터")
@click.option("--status", default="all", help="세션 상태로 필터 (active, idle, expired, archived)")
@click.option("--limit", default=10, help="표시할 세션 수")
@click.option("--show-context", is_flag=True, help="최근 대화 내용 표시")
def sessions(user_id, status, limit, show_context):
    """사용자 세션 상태를 확인하고 관리합니다."""
    from src.discord_bot.session import SessionManager, SessionStatus
    
    logger = get_logger("cli")
    logger.info("세션 관리 요청")
    
    async def manage_sessions():
        try:
            session_manager = SessionManager()
            
            # 세션 통계 표시
            stats = session_manager.get_stats()
            
            click.echo("👥 세션 관리 통계:")
            click.echo(f"   활성 세션: {stats.get('active_sessions', 0)}개")
            click.echo(f"   최근 활동: {stats.get('recent_active_sessions', 0)}개")
            click.echo(f"   총 대화 턴: {stats.get('total_conversation_turns', 0)}개")
            click.echo(f"   실행 상태: {'🟢 실행 중' if stats.get('is_running') else '🔴 중지됨'}")
            
            # 상태별 세션 수
            status_counts = stats.get('status_counts', {})
            if status_counts:
                click.echo("\n📊 상태별 세션:")
                for status_name, count in status_counts.items():
                    status_emoji = {
                        'active': '🟢',
                        'idle': '🟡', 
                        'expired': '🔴',
                        'archived': '📦'
                    }.get(status_name, '📝')
                    click.echo(f"   {status_emoji} {status_name}: {count}개")
            
            # 특정 사용자 세션 조회
            if user_id:
                session = await session_manager._load_user_session(user_id)
                if session:
                    click.echo(f"\n👤 사용자 {user_id} 세션 정보:")
                    click.echo(f"   세션 ID: {session.session_id}")
                    click.echo(f"   상태: {session.status.value}")
                    click.echo(f"   생성: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                    click.echo(f"   마지막 활동: {session.last_activity.strftime('%Y-%m-%d %H:%M:%S')}")
                    click.echo(f"   대화 턴: {len(session.conversation_turns)}개")
                    
                    if show_context and session.conversation_turns:
                        click.echo("\n💬 최근 대화:")
                        recent_turns = session.get_recent_conversation(5)
                        for turn in recent_turns:
                            click.echo(f"   👤 사용자: {turn.user_message[:50]}...")
                            if turn.bot_response:
                                click.echo(f"   🤖 봇: {turn.bot_response[:50]}...")
                            click.echo(f"      ({turn.timestamp.strftime('%H:%M:%S')})")
                else:
                    click.echo(f"\n❌ 사용자 {user_id}의 세션을 찾을 수 없습니다.")
            
        except Exception as e:
            logger.error(f"세션 관리 실패: {e}", exc_info=True)
            click.echo(f"❌ 세션 관리 실패: {e}")
    
    asyncio.run(manage_sessions())


@click.command(name="process-message")
@click.option("--message", required=True, help="처리할 자연어 메시지")
@click.option("--user-id", type=int, default=0, help="사용자 ID")
@click.option("--user-name", default="Unknown", help="사용자 이름")
@click.option("--context", default="channel", help="메시지 컨텍스트 (dm/mention/channel)")
@click.option("--format", default="text", help="출력 형식 (text/json)")
def process_message(message, user_id, user_name, context, format):
    """자연어 메시지를 AI가 처리합니다."""
    import asyncio
    logger = get_logger("cli")
    logger.info(f"자연어 메시지 처리 요청: {message[:50]}...")
    
    async def process_ai_message():
        try:
            from src.ai_engine.natural_language import NaturalLanguageProcessor
            from src.config import get_settings
            
            settings = get_settings()
            nlp_processor = NaturalLanguageProcessor(settings)
            
            # AI 엔진 초기화
            await nlp_processor.initialize()
            
            # 자연어 명령 파싱 및 처리
            parsed_result = await nlp_processor.parse_command(
                user_command=message,
                user_id=str(user_id),
                context={"user_name": user_name, "platform": context}
            )
            
            # 개인화된 응답 생성
            ai_response = await nlp_processor.generate_personalized_response(
                user_id=str(user_id),
                message=message,
                context={
                    "user_profile": {"name": user_name},
                    "parsed_command": parsed_result
                }
            )
            
            response_data = {
                "status": "success",
                "message": f"'{message}' 메시지를 성공적으로 처리했습니다.",
                "response": ai_response,
                "intent": parsed_result.intent.value,
                "confidence": parsed_result.confidence,
                "urgency": parsed_result.urgency.value,
                "required_tools": parsed_result.requires_tools,
                "user_id": user_id,
                "user_name": user_name,
                "context": context,
                "ai_engine": "Google Gemini 2.5 Pro"
            }
            
            return response_data
            
        except Exception as e:
            logger.error(f"AI 처리 실패: {e}")
            # 실패시 기본 응답
            return {
                "status": "partial_success",
                "message": f"'{message}' 메시지를 받았습니다.",
                "response": f"안녕하세요 {user_name}님! '{message}'라고 말씀하셨군요. AI 엔진이 일시적으로 사용할 수 없어 기본 응답을 드립니다.",
                "user_id": user_id,
                "user_name": user_name,
                "context": context,
                "ai_engine": "fallback mode",
                "error": str(e)
            }
    
    try:
        response_data = asyncio.run(process_ai_message())
        
        if format == "json":
            click.echo(json.dumps(response_data, ensure_ascii=False, indent=2))
        else:
            click.echo(f"✅ 메시지 처리 완료")
            click.echo(f"👤 사용자: {user_name} ({user_id})")
            click.echo(f"📝 메시지: {message}")
            click.echo(f"🤖 AI 응답: {response_data['response']}")
            
            if "intent" in response_data:
                click.echo(f"🎯 의도: {response_data['intent']}")
                click.echo(f"📊 신뢰도: {response_data['confidence']}")
                if response_data['required_tools']:
                    click.echo(f"🔧 필요 도구: {', '.join(response_data['required_tools'])}")
            
        logger.info("자연어 메시지 처리 완료")
        
    except Exception as e:
        error_response = {
            "status": "error",
            "error": str(e),
            "message": message
        }
        
        if format == "json":
            click.echo(json.dumps(error_response, ensure_ascii=False, indent=2))
        else:
            click.echo(f"❌ 메시지 처리 실패: {e}")
            
        logger.error(f"자연어 메시지 처리 실패: {e}")


# 모니터링 명령어들을 리스트로 export
monitoring_commands = [
    logs,
    queue,
    sessions,
    process_message
]
