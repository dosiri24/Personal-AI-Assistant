"""
Discord Bot 메시지 큐 시스템

Discord와 CLI 백엔드 프로세스 간의 비동기 메시지 큐를 관리하여
실시간 양방향 통신을 가능하게 합니다.
"""

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from pathlib import Path
import sys
from enum import Enum

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger


class MessageStatus(Enum):
    """메시지 상태 열거형"""
    PENDING = "pending"        # 대기 중
    PROCESSING = "processing"  # 처리 중
    COMPLETED = "completed"    # 완료됨
    FAILED = "failed"         # 실패함
    TIMEOUT = "timeout"       # 타임아웃


class MessagePriority(Enum):
    """메시지 우선순위 열거형"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class QueueMessage:
    """큐 메시지 데이터 클래스"""
    id: str
    user_id: int
    channel_id: int
    content: str
    message_type: str
    priority: MessagePriority
    status: MessageStatus
    created_at: datetime
    updated_at: datetime
    timeout_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    response: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        # Enum과 datetime 객체를 문자열로 변환
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.timeout_at:
            data['timeout_at'] = self.timeout_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        """딕셔너리에서 생성"""
        # 문자열을 Enum과 datetime으로 변환
        data['priority'] = MessagePriority(data['priority'])
        data['status'] = MessageStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('timeout_at'):
            data['timeout_at'] = datetime.fromisoformat(data['timeout_at'])
        return cls(**data)


class MessageQueue:
    """
    Discord Bot 메시지 큐 관리 클래스
    
    SQLite 기반으로 메시지를 영속적으로 저장하며,
    비동기 처리와 실시간 모니터링을 지원합니다.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        메시지 큐 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로 (기본: data/message_queue.db)
        """
        self.logger = get_discord_logger()
        
        # 데이터베이스 경로 설정
        if db_path is None:
            self.db_path = project_root / "data" / "message_queue.db"
        else:
            self.db_path = db_path
            
        # 데이터베이스 디렉토리 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 메모리 캐시
        self.cache: Dict[str, QueueMessage] = {}
        
        # 이벤트 핸들러
        self.message_handlers: Dict[str, Callable] = {}
        
        # 백그라운드 태스크
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # 데이터베이스 초기화
        self._init_database()
        
        self.logger.info("메시지 큐 시스템 초기화 완료")

    def _init_database(self):
        """데이터베이스 스키마 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS message_queue (
                        id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        channel_id INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        timeout_at TEXT,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        response TEXT,
                        error_message TEXT,
                        metadata TEXT
                    )
                """)
                
                # 인덱스 생성
                conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON message_queue(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON message_queue(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON message_queue(created_at)")
                
                conn.commit()
                
            self.logger.info("메시지 큐 데이터베이스 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"데이터베이스 초기화 실패: {e}", exc_info=True)
            raise

    async def start(self):
        """메시지 큐 백그라운드 처리 시작"""
        if self.is_running:
            self.logger.warning("메시지 큐가 이미 실행 중입니다")
            return
            
        self.is_running = True
        
        # 백그라운드 태스크 시작
        self.background_tasks = [
            asyncio.create_task(self._process_queue()),
            asyncio.create_task(self._cleanup_old_messages()),
            asyncio.create_task(self._handle_timeouts())
        ]
        
        self.logger.info("메시지 큐 백그라운드 처리 시작")

    async def stop(self):
        """메시지 큐 백그라운드 처리 중지"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # 백그라운드 태스크 취소
        for task in self.background_tasks:
            task.cancel()
            
        # 태스크 완료 대기
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        
        self.logger.info("메시지 큐 백그라운드 처리 중지")

    async def enqueue(
        self,
        user_id: int,
        channel_id: int,
        content: str,
        message_type: str = "natural_language",
        priority: MessagePriority = MessagePriority.NORMAL,
        timeout_seconds: int = 300,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        메시지를 큐에 추가
        
        Args:
            user_id: Discord 사용자 ID
            channel_id: Discord 채널 ID
            content: 메시지 내용
            message_type: 메시지 타입
            priority: 우선순위
            timeout_seconds: 타임아웃 시간 (초)
            metadata: 추가 메타데이터
            
        Returns:
            메시지 ID
        """
        try:
            message_id = str(uuid.uuid4())
            now = datetime.now()
            timeout_at = now + timedelta(seconds=timeout_seconds)
            
            message = QueueMessage(
                id=message_id,
                user_id=user_id,
                channel_id=channel_id,
                content=content,
                message_type=message_type,
                priority=priority,
                status=MessageStatus.PENDING,
                created_at=now,
                updated_at=now,
                timeout_at=timeout_at,
                metadata=metadata or {}
            )
            
            # 데이터베이스에 저장
            await self._save_message(message)
            
            # 캐시에 추가
            self.cache[message_id] = message
            
            self.logger.info(f"메시지 큐에 추가됨: {message_id} (사용자: {user_id})")
            return message_id
            
        except Exception as e:
            self.logger.error(f"메시지 큐 추가 실패: {e}", exc_info=True)
            raise

    async def get_message(self, message_id: str) -> Optional[QueueMessage]:
        """메시지 조회"""
        try:
            # 캐시에서 먼저 확인
            if message_id in self.cache:
                return self.cache[message_id]
                
            # 데이터베이스에서 조회
            message = await self._load_message(message_id)
            if message:
                self.cache[message_id] = message
                
            return message
            
        except Exception as e:
            self.logger.error(f"메시지 조회 실패: {message_id} - {e}", exc_info=True)
            return None

    async def update_status(
        self,
        message_id: str,
        status: MessageStatus,
        response: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """메시지 상태 업데이트"""
        try:
            message = await self.get_message(message_id)
            if not message:
                self.logger.warning(f"업데이트할 메시지를 찾을 수 없음: {message_id}")
                return
                
            message.status = status
            message.updated_at = datetime.now()
            
            if response is not None:
                message.response = response
                
            if error_message is not None:
                message.error_message = error_message
                
            # 데이터베이스 업데이트
            await self._save_message(message)
            
            # 캐시 업데이트
            self.cache[message_id] = message
            
            self.logger.info(f"메시지 상태 업데이트: {message_id} -> {status.value}")
            
        except Exception as e:
            self.logger.error(f"메시지 상태 업데이트 실패: {message_id} - {e}", exc_info=True)

    async def get_pending_messages(self, limit: int = 10) -> List[QueueMessage]:
        """대기 중인 메시지 목록 조회 (우선순위 순)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM message_queue 
                    WHERE status = ? 
                    ORDER BY priority DESC, created_at ASC 
                    LIMIT ?
                """, (MessageStatus.PENDING.value, limit))
                
                messages = []
                for row in cursor.fetchall():
                    message_data = dict(zip([col[0] for col in cursor.description], row))
                    if message_data.get('metadata'):
                        message_data['metadata'] = json.loads(message_data['metadata'])
                    else:
                        message_data['metadata'] = {}
                    
                    message = QueueMessage.from_dict(message_data)
                    messages.append(message)
                    
                return messages
                
        except Exception as e:
            self.logger.error(f"대기 메시지 조회 실패: {e}", exc_info=True)
            return []

    async def _save_message(self, message: QueueMessage):
        """메시지를 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                metadata_json = json.dumps(message.metadata) if message.metadata else None
                
                conn.execute("""
                    INSERT OR REPLACE INTO message_queue 
                    (id, user_id, channel_id, content, message_type, priority, status,
                     created_at, updated_at, timeout_at, retry_count, max_retries,
                     response, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.id, message.user_id, message.channel_id, message.content,
                    message.message_type, message.priority.value, message.status.value,
                    message.created_at.isoformat(), message.updated_at.isoformat(),
                    message.timeout_at.isoformat() if message.timeout_at else None,
                    message.retry_count, message.max_retries,
                    message.response, message.error_message, metadata_json
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"메시지 저장 실패: {message.id} - {e}", exc_info=True)
            raise

    async def _load_message(self, message_id: str) -> Optional[QueueMessage]:
        """데이터베이스에서 메시지 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT * FROM message_queue WHERE id = ?", 
                    (message_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                    
                message_data = dict(zip([col[0] for col in cursor.description], row))
                if message_data.get('metadata'):
                    message_data['metadata'] = json.loads(message_data['metadata'])
                else:
                    message_data['metadata'] = {}
                    
                return QueueMessage.from_dict(message_data)
                
        except Exception as e:
            self.logger.error(f"메시지 로드 실패: {message_id} - {e}", exc_info=True)
            return None

    async def _process_queue(self):
        """큐 처리 백그라운드 태스크"""
        while self.is_running:
            try:
                # 대기 중인 메시지 처리
                pending_messages = await self.get_pending_messages(5)
                
                for message in pending_messages:
                    await self._process_message(message)
                    
                # 잠시 대기
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"큐 처리 중 오류: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _process_message(self, message: QueueMessage):
        """개별 메시지 처리"""
        try:
            # 상태를 처리 중으로 변경
            await self.update_status(message.id, MessageStatus.PROCESSING)
            
            # 메시지 타입별 핸들러 호출
            handler = self.message_handlers.get(message.message_type)
            
            if handler:
                try:
                    response = await handler(message)
                    await self.update_status(
                        message.id, 
                        MessageStatus.COMPLETED,
                        response=response
                    )
                except Exception as e:
                    await self._handle_message_error(message, str(e))
            else:
                self.logger.warning(f"핸들러가 없는 메시지 타입: {message.message_type}")
                await self.update_status(
                    message.id,
                    MessageStatus.FAILED,
                    error_message=f"Unknown message type: {message.message_type}"
                )
                
        except Exception as e:
            self.logger.error(f"메시지 처리 실패: {message.id} - {e}", exc_info=True)
            await self._handle_message_error(message, str(e))

    async def _handle_message_error(self, message: QueueMessage, error: str):
        """메시지 처리 오류 핸들링"""
        message.retry_count += 1
        
        if message.retry_count <= message.max_retries:
            # 재시도
            await self.update_status(
                message.id,
                MessageStatus.PENDING,
                error_message=f"Retry {message.retry_count}/{message.max_retries}: {error}"
            )
            self.logger.info(f"메시지 재시도: {message.id} ({message.retry_count}/{message.max_retries})")
        else:
            # 최대 재시도 횟수 초과
            await self.update_status(
                message.id,
                MessageStatus.FAILED,
                error_message=f"Max retries exceeded: {error}"
            )
            self.logger.error(f"메시지 처리 최종 실패: {message.id}")

    async def _handle_timeouts(self):
        """타임아웃 처리 백그라운드 태스크"""
        while self.is_running:
            try:
                now = datetime.now()
                
                with sqlite3.connect(self.db_path) as conn:
                    # 타임아웃된 메시지 조회
                    cursor = conn.execute("""
                        SELECT id FROM message_queue 
                        WHERE status IN (?, ?) AND timeout_at < ?
                    """, (MessageStatus.PENDING.value, MessageStatus.PROCESSING.value, now.isoformat()))
                    
                    timeout_ids = [row[0] for row in cursor.fetchall()]
                    
                    # 타임아웃 상태로 업데이트
                    for message_id in timeout_ids:
                        await self.update_status(
                            message_id,
                            MessageStatus.TIMEOUT,
                            error_message="Message processing timeout"
                        )
                        self.logger.warning(f"메시지 타임아웃: {message_id}")
                
                await asyncio.sleep(30)  # 30초마다 확인
                
            except Exception as e:
                self.logger.error(f"타임아웃 처리 중 오류: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _cleanup_old_messages(self):
        """오래된 메시지 정리 백그라운드 태스크"""
        while self.is_running:
            try:
                # 7일 이전 메시지 삭제
                cutoff_date = datetime.now() - timedelta(days=7)
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "DELETE FROM message_queue WHERE created_at < ?",
                        (cutoff_date.isoformat(),)
                    )
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"오래된 메시지 {cursor.rowcount}개 정리 완료")
                        
                    conn.commit()
                
                # 메모리 캐시도 정리
                expired_keys = [
                    key for key, msg in self.cache.items()
                    if msg.created_at < cutoff_date
                ]
                for key in expired_keys:
                    del self.cache[key]
                
                await asyncio.sleep(3600)  # 1시간마다 정리
                
            except Exception as e:
                self.logger.error(f"메시지 정리 중 오류: {e}", exc_info=True)
                await asyncio.sleep(3600)

    def register_handler(self, message_type: str, handler: Callable):
        """메시지 타입별 핸들러 등록"""
        self.message_handlers[message_type] = handler
        self.logger.info(f"메시지 핸들러 등록됨: {message_type}")

    def get_stats(self) -> Dict[str, Any]:
        """큐 통계 정보 반환"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM message_queue 
                    GROUP BY status
                """)
                
                status_counts = dict(cursor.fetchall())
                
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM message_queue 
                    WHERE created_at > datetime('now', '-1 hour')
                """)
                recent_count = cursor.fetchone()[0]
                
                return {
                    "total_messages": sum(status_counts.values()),
                    "status_counts": status_counts,
                    "recent_messages": recent_count,
                    "cache_size": len(self.cache),
                    "is_running": self.is_running,
                    "handlers_registered": len(self.message_handlers)
                }
                
        except Exception as e:
            self.logger.error(f"통계 조회 실패: {e}", exc_info=True)
            return {"error": str(e)}
