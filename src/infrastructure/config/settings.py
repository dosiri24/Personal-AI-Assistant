"""
타입 안전한 설정 관리

Pydantic을 사용한 타입 안전한 설정 시스템입니다.
"""

import os
from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, Field, validator
from enum import Enum


class LogLevel(str, Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MockMode(str, Enum):
    """Mock 모드"""
    OFF = "off"
    ECHO = "echo"
    HEURISTIC = "heuristic"


class ParamNormalizationMode(str, Enum):
    """매개변수 정규화 모드"""
    OFF = "off"
    MINIMAL = "minimal"
    FULL = "full"


class AISettings(BaseSettings):
    """AI 엔진 설정"""
    
    # Google Gemini API 설정
    google_api_key: str = Field(..., env="GOOGLE_AI_API_KEY")
    ai_model: str = Field("gemini-2.5-flash", env="AI_MODEL")
    ai_temperature: float = Field(0.7, env="AI_TEMPERATURE")
    ai_max_tokens: int = Field(8192, env="AI_MAX_TOKENS")
    
    # 에이전틱 AI 설정
    mock_mode: MockMode = Field(MockMode.OFF, env="PAI_MOCK_MODE")
    param_normalization_mode: ParamNormalizationMode = Field(
        ParamNormalizationMode.MINIMAL, 
        env="PAI_PARAM_NORMALIZATION_MODE"
    )
    self_repair_attempts: int = Field(2, env="PAI_SELF_REPAIR_ATTEMPTS")
    complexity_threshold: int = Field(7, env="PAI_COMPLEXITY_THRESHOLD")
    max_iterations: int = Field(15, env="PAI_MAX_ITERATIONS")
    timeout_seconds: int = Field(600, env="PAI_TIMEOUT_SECONDS")
    
    @validator("ai_temperature")
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v
    
    @validator("self_repair_attempts")
    def validate_repair_attempts(cls, v):
        if v < 0 or v > 10:
            raise ValueError("Self repair attempts must be between 0 and 10")
        return v


class DiscordSettings(BaseSettings):
    """Discord Bot 설정"""
    
    bot_token: str = Field(..., env="DISCORD_BOT_TOKEN")
    allowed_user_ids: List[str] = Field([], env="ALLOWED_USER_IDS")
    admin_user_ids: List[str] = Field([], env="ADMIN_USER_IDS")
    command_prefix: str = Field("!", env="DISCORD_COMMAND_PREFIX")
    
    @validator("allowed_user_ids", pre=True)
    def parse_user_ids(cls, v):
        if isinstance(v, str):
            return [uid.strip() for uid in v.split(",") if uid.strip()]
        return v
    
    @validator("admin_user_ids", pre=True)
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            return [uid.strip() for uid in v.split(",") if uid.strip()]
        return v


class NotionSettings(BaseSettings):
    """Notion 통합 설정"""
    
    api_token: Optional[str] = Field(None, env="NOTION_API_TOKEN")
    todo_database_id: Optional[str] = Field(None, env="NOTION_TODO_DATABASE_ID")
    calendar_database_id: Optional[str] = Field(None, env="NOTION_CALENDAR_DATABASE_ID")
    
    @property
    def is_enabled(self) -> bool:
        """Notion 통합이 활성화되었는지 확인"""
        return bool(self.api_token and self.todo_database_id)


class AppleSettings(BaseSettings):
    """Apple 시스템 통합 설정 (macOS 전용)"""
    
    mcp_autostart: bool = Field(False, env="APPLE_MCP_AUTOSTART")
    mcp_port: int = Field(3001, env="APPLE_MCP_PORT")
    enable_notifications: bool = Field(True, env="APPLE_ENABLE_NOTIFICATIONS")
    
    @property
    def is_available(self) -> bool:
        """Apple 통합이 사용 가능한지 확인"""
        return os.uname().sysname == "Darwin"  # macOS인지 확인


class SystemSettings(BaseSettings):
    """시스템 설정"""
    
    max_memory_usage: int = Field(8192, env="MAX_MEMORY_USAGE")  # MB
    vector_db_path: str = Field("data/chroma_db", env="VECTOR_DB_PATH")
    log_level: LogLevel = Field(LogLevel.INFO, env="LOG_LEVEL")
    enable_monitoring: bool = Field(True, env="ENABLE_MONITORING")
    
    # 데이터 디렉토리
    data_dir: str = Field("data", env="DATA_DIR")
    logs_dir: str = Field("logs", env="LOGS_DIR")
    
    @validator("max_memory_usage")
    def validate_memory_usage(cls, v):
        if v < 512 or v > 32768:  # 512MB ~ 32GB
            raise ValueError("Memory usage must be between 512 and 32768 MB")
        return v


class Settings(BaseSettings):
    """전체 애플리케이션 설정"""
    
    # 환경 설정
    environment: str = Field("development", env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # 각 섹션별 설정
    ai: AISettings = AISettings()
    discord: DiscordSettings = DiscordSettings()
    notion: NotionSettings = NotionSettings()
    apple: AppleSettings = AppleSettings()
    system: SystemSettings = SystemSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 전역 설정 인스턴스
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """전역 설정 인스턴스 반환"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """설정 다시 로드"""
    global _settings
    _settings = Settings()
    return _settings