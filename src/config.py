"""
환경 설정 관리 모듈

Pydantic Settings를 사용하여 환경 변수를 자동으로 로드하고 
유효성을 검증하는 설정 관리 시스템을 제공합니다.
"""

from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from enum import Enum


class Environment(str, Enum):
    """실행 환경 열거형"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(str, Enum):
    """로그 레벨 열거형"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # 기본 설정
    debug: bool = Field(default=False, description="디버그 모드")
    environment: Environment = Field(default=Environment.PRODUCTION, description="실행 환경")
    
    # Discord Bot 설정
    discord_bot_token: str = Field(default="", description="Discord Bot 토큰")
    allowed_user_ids: str = Field(default="", description="허용된 Discord 사용자 ID 목록 (쉼표 구분)")
    admin_user_ids: str = Field(default="", description="관리자 Discord 사용자 ID 목록 (쉼표 구분)")
    
    # AI 설정
    google_ai_api_key: str = Field(default="", description="Google Gemini API 키")
    ai_model: str = Field(default="gemini-2.0-flash-exp", description="사용할 AI 모델")
    ai_temperature: float = Field(default=0.7, description="AI 응답 온도")
    ai_max_tokens: int = Field(default=8192, description="AI 최대 토큰 수")
    gemini_api_rate_limit: int = Field(default=60, description="Gemini API 분당 요청 제한")
    
    # Notion 설정
    notion_api_token: Optional[str] = Field(default=None, description="Notion API 토큰")
    notion_todo_database_id: Optional[str] = Field(default=None, description="Notion 할일 데이터베이스 ID")
    notion_api_rate_limit: int = Field(default=3, description="Notion API 초당 요청 제한")
    
    # Apple/macOS 설정
    apple_mcp_server_url: str = Field(default="http://localhost:3000", description="Apple MCP 서버 URL")
    
    # 데이터베이스 설정
    database_url: str = Field(default="sqlite:///data/personal_ai_assistant.db", description="메인 데이터베이스 URL")
    vector_db_path: str = Field(default="data/chroma_db", description="벡터 데이터베이스 경로")
    
    # 로깅 설정
    log_level: LogLevel = Field(default=LogLevel.INFO, description="로그 레벨")
    log_file_path: str = Field(default="logs/personal_ai_assistant.log", description="로그 파일 경로")
    log_max_file_size: str = Field(default="100MB", description="로그 파일 최대 크기")
    log_backup_count: int = Field(default=5, description="로그 백업 파일 개수")
    
    # 프로세스 관리 설정
    pid_file_path: str = Field(default="personal_ai_assistant.pid", description="PID 파일 경로")
    daemon_user: Optional[str] = Field(default=None, description="데몬 실행 사용자")
    daemon_group: Optional[str] = Field(default=None, description="데몬 실행 그룹")
    
    # 성능 설정
    max_memory_usage: int = Field(default=8192, description="최대 메모리 사용량 (MB)")
    memory_cleanup_interval: int = Field(default=3600, description="메모리 정리 간격 (초)")
    web_scraping_delay: int = Field(default=1, description="웹 스크래핑 요청 간 지연 (초)")
    
    
    def has_valid_api_key(self) -> bool:
        """유효한 API 키가 있는지 확인"""
        return bool(self.google_ai_api_key and not self.google_ai_api_key.startswith('your_'))
    
    def has_valid_discord_token(self) -> bool:
        """유효한 Discord 토큰이 있는지 확인"""
        return bool(self.discord_bot_token and not self.discord_bot_token.startswith('your_'))
    
    def has_valid_ai_api_key(self) -> bool:
        """유효한 AI API 키가 있는지 확인"""
        return bool(self.google_ai_api_key and not self.google_ai_api_key.startswith('your_'))
    
    def get_allowed_user_ids(self) -> List[str]:
        """허용된 사용자 ID 목록 반환"""
        if not self.allowed_user_ids:
            return []
        return [uid.strip() for uid in self.allowed_user_ids.split(',') if uid.strip()]
    
    def get_admin_user_ids(self) -> List[str]:
        """관리자 사용자 ID 목록 반환"""
        if not self.admin_user_ids:
            return []
        return [uid.strip() for uid in self.admin_user_ids.split(',') if uid.strip()]
        
    def get_project_root(self) -> Path:
        """프로젝트 루트 디렉토리 반환"""
        return Path(__file__).parent.parent
    
    def get_logs_dir(self) -> Path:
        """로그 디렉토리 경로 반환"""
        return self.get_project_root() / "logs"
    
    def get_data_dir(self) -> Path:
        """데이터 디렉토리 경로 반환"""
        return self.get_project_root() / "data"
    
    def ensure_directories(self):
        """필요한 디렉토리들을 생성"""
        self.get_logs_dir().mkdir(exist_ok=True)
        self.get_data_dir().mkdir(exist_ok=True)
    
    def is_development(self) -> bool:
        """개발 환경 여부 확인"""
        return self.environment == Environment.DEVELOPMENT
    
    def is_production(self) -> bool:
        """프로덕션 환경 여부 확인"""
        return self.environment == Environment.PRODUCTION


# 전역 설정 인스턴스
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    전역 설정 인스턴스 반환
    
    Returns:
        Settings 인스턴스
    """
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_directories()
    return _settings


def reload_settings() -> Settings:
    """
    설정을 다시 로드
    
    Returns:
        새로운 Settings 인스턴스
    """
    global _settings
    _settings = Settings()
    _settings.ensure_directories()
    return _settings
