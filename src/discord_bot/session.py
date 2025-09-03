"""
Discord Bot 대화 세션 관리 시스템

사용자별 대화 컨텍스트와 히스토리를 관리하여
개인화된 AI 어시스턴트 경험을 제공합니다.
"""

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path
import sys
from enum import Enum

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logger import get_discord_logger


class SessionStatus(Enum):
    """세션 상태 열거형"""
    ACTIVE = "active"        # 활성 세션
    IDLE = "idle"           # 유휴 상태
    EXPIRED = "expired"     # 만료됨
    ARCHIVED = "archived"   # 보관됨


@dataclass
class ConversationTurn:
    """대화 턴 데이터 클래스"""
    id: str
    session_id: str
    user_message: str
    bot_response: Optional[str]
    timestamp: datetime
    processing_time_ms: Optional[int] = None
    message_type: str = "natural_language"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationTurn':
        """딕셔너리에서 생성"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        if 'metadata' not in data:
            data['metadata'] = {}
        return cls(**data)


@dataclass
class UserSession:
    """사용자 세션 데이터 클래스"""
    session_id: str
    user_id: int
    user_name: str
    channel_id: int
    channel_name: str
    status: SessionStatus
    created_at: datetime
    last_activity: datetime
    expires_at: Optional[datetime]
    conversation_turns: List[ConversationTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        data = asdict(self)
        data['status'] = self.status.value
        data['created_at'] = self.created_at.isoformat()
        data['last_activity'] = self.last_activity.isoformat()
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        data['conversation_turns'] = [turn.to_dict() for turn in self.conversation_turns]
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """딕셔너리에서 생성"""
        data['status'] = SessionStatus(data['status'])
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_activity'] = datetime.fromisoformat(data['last_activity'])
        if data.get('expires_at'):
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        
        # conversation_turns 변환
        turns_data = data.get('conversation_turns', [])
        data['conversation_turns'] = [ConversationTurn.from_dict(turn) for turn in turns_data]
        
        if 'context' not in data:
            data['context'] = {}
        if 'preferences' not in data:
            data['preferences'] = {}
            
        return cls(**data)

    def get_recent_conversation(self, limit: int = 10) -> List[ConversationTurn]:
        """최근 대화 내용 조회"""
        return sorted(self.conversation_turns, key=lambda x: x.timestamp, reverse=True)[:limit]

    def add_conversation_turn(self, turn: ConversationTurn):
        """대화 턴 추가"""
        self.conversation_turns.append(turn)
        self.last_activity = datetime.now()

    def is_expired(self) -> bool:
        """세션 만료 여부 확인"""
        if self.expires_at and datetime.now() > self.expires_at:
            return True
        return False

    def extend_session(self, hours: int = 24):
        """세션 연장"""
        self.expires_at = datetime.now() + timedelta(hours=hours)
        self.last_activity = datetime.now()


class SessionManager:
    """
    Discord Bot 세션 관리 클래스
    
    사용자별 대화 세션을 관리하고 컨텍스트를 유지합니다.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        세션 매니저 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로 (기본: data/sessions.db)
        """
        self.logger = get_discord_logger()
        
        # 데이터베이스 경로 설정
        if db_path is None:
            self.db_path = project_root / "data" / "sessions.db"
        else:
            self.db_path = db_path
            
        # 데이터베이스 디렉토리 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 메모리 캐시 (활성 세션만)
        self.active_sessions: Dict[int, UserSession] = {}
        
        # 세션 설정
        self.default_session_hours = 24
        self.max_conversation_turns = 100
        self.cleanup_interval_hours = 6
        
        # 백그라운드 태스크
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # 데이터베이스 초기화
        self._init_database()
        
        self.logger.info("세션 관리 시스템 초기화 완료")

    def _init_database(self):
        """데이터베이스 스키마 초기화"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 세션 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        user_name TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        channel_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        last_activity TEXT NOT NULL,
                        expires_at TEXT,
                        context TEXT,
                        preferences TEXT
                    )
                """)
                
                # 대화 턴 테이블
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversation_turns (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_message TEXT NOT NULL,
                        bot_response TEXT,
                        timestamp TEXT NOT NULL,
                        processing_time_ms INTEGER,
                        message_type TEXT DEFAULT 'natural_language',
                        metadata TEXT,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                """)
                
                # 인덱스 생성
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_session_id ON conversation_turns(session_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_turns_timestamp ON conversation_turns(timestamp)")
                
                conn.commit()
                
            self.logger.info("세션 데이터베이스 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"세션 데이터베이스 초기화 실패: {e}", exc_info=True)
            raise

    async def start(self):
        """세션 관리 백그라운드 처리 시작"""
        if self.is_running:
            self.logger.warning("세션 관리자가 이미 실행 중입니다")
            return
            
        self.is_running = True
        
        # 활성 세션 로드
        await self._load_active_sessions()
        
        # 백그라운드 태스크 시작
        self.background_tasks = [
            asyncio.create_task(self._cleanup_expired_sessions()),
            asyncio.create_task(self._archive_old_sessions()),
            asyncio.create_task(self._update_session_cache())
        ]
        
        self.logger.info("세션 관리 백그라운드 처리 시작")

    async def stop(self):
        """세션 관리 백그라운드 처리 중지"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        # 활성 세션 저장
        await self._save_active_sessions()
        
        # 백그라운드 태스크 취소
        for task in self.background_tasks:
            task.cancel()
            
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        
        self.logger.info("세션 관리 백그라운드 처리 중지")

    async def get_or_create_session(
        self,
        user_id: int,
        user_name: str,
        channel_id: int,
        channel_name: str
    ) -> UserSession:
        """사용자 세션 조회 또는 생성"""
        try:
            # 활성 세션에서 먼저 확인
            if user_id in self.active_sessions:
                session = self.active_sessions[user_id]
                if not session.is_expired():
                    session.extend_session(self.default_session_hours)
                    return session
                else:
                    # 만료된 세션 제거
                    del self.active_sessions[user_id]
            
            # 데이터베이스에서 최근 세션 조회
            session = await self._load_user_session(user_id)
            
            if session and not session.is_expired():
                # 기존 세션 복원
                session.extend_session(self.default_session_hours)
                session.status = SessionStatus.ACTIVE
                self.active_sessions[user_id] = session
                
                self.logger.info(f"기존 세션 복원: {user_id}")
                return session
            
            # 새 세션 생성
            session = await self._create_new_session(
                user_id, user_name, channel_id, channel_name
            )
            
            self.active_sessions[user_id] = session
            self.logger.info(f"새 세션 생성: {user_id}")
            
            return session
            
        except Exception as e:
            self.logger.error(f"세션 조회/생성 실패: {user_id} - {e}", exc_info=True)
            raise

    async def add_conversation_turn(
        self,
        user_id: int,
        user_message: str,
        bot_response: Optional[str] = None,
        processing_time_ms: Optional[int] = None,
        message_type: str = "natural_language",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """대화 턴 추가"""
        try:
            session = self.active_sessions.get(user_id)
            if not session:
                raise ValueError(f"활성 세션을 찾을 수 없음: {user_id}")
            
            # 대화 턴 생성
            turn_id = f"turn_{user_id}_{int(datetime.now().timestamp() * 1000)}"
            turn = ConversationTurn(
                id=turn_id,
                session_id=session.session_id,
                user_message=user_message,
                bot_response=bot_response,
                timestamp=datetime.now(),
                processing_time_ms=processing_time_ms,
                message_type=message_type,
                metadata=metadata or {}
            )
            
            # 세션에 추가
            session.add_conversation_turn(turn)
            
            # 대화 턴 수 제한
            if len(session.conversation_turns) > self.max_conversation_turns:
                session.conversation_turns = session.conversation_turns[-self.max_conversation_turns:]
            
            # 데이터베이스에 저장
            await self._save_conversation_turn(turn)
            
            self.logger.info(f"대화 턴 추가: {turn_id} (사용자: {user_id})")
            return turn_id
            
        except Exception as e:
            self.logger.error(f"대화 턴 추가 실패: {user_id} - {e}", exc_info=True)
            raise

    async def update_conversation_turn(
        self,
        turn_id: str,
        bot_response: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ):
        """대화 턴 업데이트 (봇 응답 추가 등)"""
        try:
            # 활성 세션에서 찾기
            for session in self.active_sessions.values():
                for turn in session.conversation_turns:
                    if turn.id == turn_id:
                        if bot_response is not None:
                            turn.bot_response = bot_response
                        if processing_time_ms is not None:
                            turn.processing_time_ms = processing_time_ms
                        
                        # 데이터베이스 업데이트
                        await self._update_conversation_turn(turn)
                        
                        self.logger.info(f"대화 턴 업데이트: {turn_id}")
                        return
            
            self.logger.warning(f"업데이트할 대화 턴을 찾을 수 없음: {turn_id}")
            
        except Exception as e:
            self.logger.error(f"대화 턴 업데이트 실패: {turn_id} - {e}", exc_info=True)

    async def get_conversation_context(
        self,
        user_id: int,
        turns_limit: int = 10
    ) -> List[ConversationTurn]:
        """사용자의 최근 대화 컨텍스트 조회"""
        try:
            session = self.active_sessions.get(user_id)
            if session:
                return session.get_recent_conversation(turns_limit)
            
            # 비활성 세션의 경우 데이터베이스에서 조회
            session = await self._load_user_session(user_id)
            if session:
                return session.get_recent_conversation(turns_limit)
            
            return []
            
        except Exception as e:
            self.logger.error(f"대화 컨텍스트 조회 실패: {user_id} - {e}", exc_info=True)
            return []

    async def update_user_context(
        self,
        user_id: int,
        context_key: str,
        context_value: Any
    ):
        """사용자 컨텍스트 업데이트"""
        try:
            session = self.active_sessions.get(user_id)
            if session:
                session.context[context_key] = context_value
                session.last_activity = datetime.now()
                
                self.logger.info(f"사용자 컨텍스트 업데이트: {user_id} - {context_key}")
            
        except Exception as e:
            self.logger.error(f"컨텍스트 업데이트 실패: {user_id} - {e}", exc_info=True)

    async def _create_new_session(
        self,
        user_id: int,
        user_name: str,
        channel_id: int,
        channel_name: str
    ) -> UserSession:
        """새 세션 생성"""
        session_id = f"session_{user_id}_{int(datetime.now().timestamp())}"
        now = datetime.now()
        expires_at = now + timedelta(hours=self.default_session_hours)
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            channel_name=channel_name,
            status=SessionStatus.ACTIVE,
            created_at=now,
            last_activity=now,
            expires_at=expires_at
        )
        
        # 데이터베이스에 저장
        await self._save_session(session)
        
        return session

    async def _save_session(self, session: UserSession):
        """세션을 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                context_json = json.dumps(session.context) if session.context else None
                preferences_json = json.dumps(session.preferences) if session.preferences else None
                
                conn.execute("""
                    INSERT OR REPLACE INTO sessions 
                    (session_id, user_id, user_name, channel_id, channel_name, status,
                     created_at, last_activity, expires_at, context, preferences)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.session_id, session.user_id, session.user_name,
                    session.channel_id, session.channel_name, session.status.value,
                    session.created_at.isoformat(), session.last_activity.isoformat(),
                    session.expires_at.isoformat() if session.expires_at else None,
                    context_json, preferences_json
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"세션 저장 실패: {session.session_id} - {e}", exc_info=True)
            raise

    async def _load_user_session(self, user_id: int) -> Optional[UserSession]:
        """사용자의 최신 세션 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM sessions 
                    WHERE user_id = ? 
                    ORDER BY last_activity DESC 
                    LIMIT 1
                """, (user_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                session_data = dict(zip([col[0] for col in cursor.description], row))
                
                # JSON 필드 파싱
                if session_data.get('context'):
                    session_data['context'] = json.loads(session_data['context'])
                else:
                    session_data['context'] = {}
                    
                if session_data.get('preferences'):
                    session_data['preferences'] = json.loads(session_data['preferences'])
                else:
                    session_data['preferences'] = {}
                
                session = UserSession.from_dict(session_data)
                
                # 대화 턴 로드
                await self._load_conversation_turns(session)
                
                return session
                
        except Exception as e:
            self.logger.error(f"세션 로드 실패: {user_id} - {e}", exc_info=True)
            return None

    async def _load_conversation_turns(self, session: UserSession):
        """세션의 대화 턴들 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT * FROM conversation_turns 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (session.session_id, self.max_conversation_turns))
                
                turns = []
                for row in cursor.fetchall():
                    turn_data = dict(zip([col[0] for col in cursor.description], row))
                    
                    if turn_data.get('metadata'):
                        turn_data['metadata'] = json.loads(turn_data['metadata'])
                    else:
                        turn_data['metadata'] = {}
                    
                    turn = ConversationTurn.from_dict(turn_data)
                    turns.append(turn)
                
                session.conversation_turns = list(reversed(turns))  # 시간 순으로 정렬
                
        except Exception as e:
            self.logger.error(f"대화 턴 로드 실패: {session.session_id} - {e}", exc_info=True)

    async def _save_conversation_turn(self, turn: ConversationTurn):
        """대화 턴을 데이터베이스에 저장"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                metadata_json = json.dumps(turn.metadata) if turn.metadata else None
                
                conn.execute("""
                    INSERT OR REPLACE INTO conversation_turns 
                    (id, session_id, user_message, bot_response, timestamp,
                     processing_time_ms, message_type, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    turn.id, turn.session_id, turn.user_message, turn.bot_response,
                    turn.timestamp.isoformat(), turn.processing_time_ms,
                    turn.message_type, metadata_json
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"대화 턴 저장 실패: {turn.id} - {e}", exc_info=True)
            raise

    async def _update_conversation_turn(self, turn: ConversationTurn):
        """대화 턴 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                metadata_json = json.dumps(turn.metadata) if turn.metadata else None
                
                conn.execute("""
                    UPDATE conversation_turns 
                    SET bot_response = ?, processing_time_ms = ?, metadata = ?
                    WHERE id = ?
                """, (
                    turn.bot_response, turn.processing_time_ms,
                    metadata_json, turn.id
                ))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"대화 턴 업데이트 실패: {turn.id} - {e}", exc_info=True)

    async def _load_active_sessions(self):
        """활성 세션들을 메모리로 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT user_id FROM sessions 
                    WHERE status = ? AND expires_at > ?
                """, (SessionStatus.ACTIVE.value, datetime.now().isoformat()))
                
                for row in cursor.fetchall():
                    user_id = row[0]
                    session = await self._load_user_session(user_id)
                    if session and not session.is_expired():
                        self.active_sessions[user_id] = session
                
                self.logger.info(f"활성 세션 {len(self.active_sessions)}개 로드됨")
                
        except Exception as e:
            self.logger.error(f"활성 세션 로드 실패: {e}", exc_info=True)

    async def _save_active_sessions(self):
        """활성 세션들을 데이터베이스에 저장"""
        try:
            for session in self.active_sessions.values():
                await self._save_session(session)
                
            self.logger.info(f"활성 세션 {len(self.active_sessions)}개 저장됨")
            
        except Exception as e:
            self.logger.error(f"활성 세션 저장 실패: {e}", exc_info=True)

    async def _cleanup_expired_sessions(self):
        """만료된 세션 정리 백그라운드 태스크"""
        while self.is_running:
            try:
                now = datetime.now()
                expired_users = []
                
                # 메모리에서 만료된 세션 제거
                for user_id, session in self.active_sessions.items():
                    if session.is_expired():
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    session = self.active_sessions.pop(user_id)
                    session.status = SessionStatus.EXPIRED
                    await self._save_session(session)
                    self.logger.info(f"세션 만료 처리: {user_id}")
                
                # 30분마다 정리
                await asyncio.sleep(1800)
                
            except Exception as e:
                self.logger.error(f"세션 정리 중 오류: {e}", exc_info=True)
                await asyncio.sleep(1800)

    async def _archive_old_sessions(self):
        """오래된 세션 아카이브 백그라운드 태스크"""
        while self.is_running:
            try:
                # 30일 이전 세션 아카이브
                cutoff_date = datetime.now() - timedelta(days=30)
                
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        UPDATE sessions 
                        SET status = ? 
                        WHERE status = ? AND last_activity < ?
                    """, (SessionStatus.ARCHIVED.value, SessionStatus.EXPIRED.value, cutoff_date.isoformat()))
                    
                    if cursor.rowcount > 0:
                        self.logger.info(f"오래된 세션 {cursor.rowcount}개 아카이브됨")
                    
                    conn.commit()
                
                # 6시간마다 아카이브
                await asyncio.sleep(21600)
                
            except Exception as e:
                self.logger.error(f"세션 아카이브 중 오류: {e}", exc_info=True)
                await asyncio.sleep(21600)

    async def _update_session_cache(self):
        """세션 캐시 업데이트 백그라운드 태스크"""
        while self.is_running:
            try:
                # 활성 세션들을 주기적으로 데이터베이스에 저장
                await self._save_active_sessions()
                
                # 5분마다 캐시 업데이트
                await asyncio.sleep(300)
                
            except Exception as e:
                self.logger.error(f"세션 캐시 업데이트 중 오류: {e}", exc_info=True)
                await asyncio.sleep(300)

    def get_stats(self) -> Dict[str, Any]:
        """세션 통계 정보 반환"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # 세션 상태별 통계
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM sessions 
                    GROUP BY status
                """)
                status_counts = dict(cursor.fetchall())
                
                # 최근 활동 통계
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM sessions 
                    WHERE last_activity > datetime('now', '-1 hour')
                """)
                recent_active = cursor.fetchone()[0]
                
                # 총 대화 턴 수
                cursor = conn.execute("SELECT COUNT(*) FROM conversation_turns")
                total_turns = cursor.fetchone()[0]
                
                return {
                    "active_sessions": len(self.active_sessions),
                    "status_counts": status_counts,
                    "recent_active_sessions": recent_active,
                    "total_conversation_turns": total_turns,
                    "is_running": self.is_running
                }
                
        except Exception as e:
            self.logger.error(f"세션 통계 조회 실패: {e}", exc_info=True)
            return {"error": str(e)}
