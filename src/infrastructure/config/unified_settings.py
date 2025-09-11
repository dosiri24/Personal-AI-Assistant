"""
통합 설정 관리 시스템

모든 설정을 중앙에서 관리하는 통합 시스템입니다.
보안, 검증, 환경별 설정을 일관되게 관리합니다.
"""

import os
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseSettings, Field, validator, SecretStr
from pathlib import Path
from enum import Enum


class Environment(str, Enum):
    """실행 환경"""
    DEVELOPMENT = "development"
    STAGING = "staging"  
    PRODUCTION = "production"


class LogLevel(str, Enum):
    """로그 레벨"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class UnifiedSettings(BaseSettings):
    """통합 설정 클래스"""
    
    # === 환경 설정 ===
    environment: Environment = Field(Environment.DEVELOPMENT, env="ENVIRONMENT")
    debug: bool = Field(False, env="DEBUG")
    
    # === AI 설정 ===
    google_api_key: SecretStr = Field(..., env="GOOGLE_AI_API_KEY")
    ai_model: str = Field("gemini-2.5-flash", env="AI_MODEL")
    ai_temperature: float = Field(0.7, env="AI_TEMPERATURE")
    ai_max_tokens: int = Field(8192, env="AI_MAX_TOKENS")
    
    # 에이전틱 AI 설정
    pai_complexity_threshold: int = Field(7, env="PAI_COMPLEXITY_THRESHOLD")
    pai_max_iterations: int = Field(15, env="PAI_MAX_ITERATIONS") 
    pai_self_repair_attempts: int = Field(2, env="PAI_SELF_REPAIR_ATTEMPTS")
    pai_timeout_seconds: int = Field(600, env="PAI_TIMEOUT_SECONDS")
    
    # === Discord 설정 ===
    discord_bot_token: Optional[SecretStr] = Field(None, env="DISCORD_BOT_TOKEN")
    allowed_user_ids: List[str] = Field([], env="ALLOWED_USER_IDS")
    admin_user_ids: List[str] = Field([], env="ADMIN_USER_IDS")
    
    # === Notion 설정 ===
    notion_api_token: Optional[SecretStr] = Field(None, env="NOTION_API_TOKEN")
    notion_todo_database_id: Optional[str] = Field(None, env="NOTION_TODO_DATABASE_ID")
    notion_calendar_database_id: Optional[str] = Field(None, env="NOTION_CALENDAR_DATABASE_ID")
    
    # === 시스템 설정 ===
    log_level: LogLevel = Field(LogLevel.INFO, env="LOG_LEVEL")
    max_memory_usage: int = Field(8192, env="MAX_MEMORY_USAGE")  # MB
    enable_monitoring: bool = Field(True, env="ENABLE_MONITORING")
    
    # 디렉토리 설정
    data_dir: str = Field("data", env="DATA_DIR")
    logs_dir: str = Field("logs", env="LOGS_DIR")
    vector_db_path: str = Field("data/chroma_db", env="VECTOR_DB_PATH")
    
    # === 보안 설정 ===
    allowed_filesystem_paths: List[str] = Field(
        default_factory=lambda: [
            "~/Desktop",
            "~/Documents", 
            "~/Downloads",
            "./data",
            "./temp"
        ],
        env="ALLOWED_FILESYSTEM_PATHS"
    )
    
    max_file_size_mb: int = Field(100, env="MAX_FILE_SIZE_MB")
    enable_file_operations: bool = Field(True, env="ENABLE_FILE_OPERATIONS")
    
    # === 검증기들 ===
    @validator("ai_temperature")
    def validate_temperature(cls, v):
        if not 0.0 <= v <= 2.0:
            raise ValueError("AI temperature must be between 0.0 and 2.0")
        return v
    
    @validator("pai_self_repair_attempts")
    def validate_repair_attempts(cls, v):
        if not 0 <= v <= 10:
            raise ValueError("Self repair attempts must be between 0 and 10")
        return v
    
    @validator("max_memory_usage")
    def validate_memory_usage(cls, v):
        if not 512 <= v <= 32768:
            raise ValueError("Memory usage must be between 512 and 32768 MB")
        return v
    
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
    
    @validator("allowed_filesystem_paths", pre=True)
    def parse_filesystem_paths(cls, v):
        if isinstance(v, str):
            return [path.strip() for path in v.split(",") if path.strip()]
        return v
    
    # === 유틸리티 메서드들 ===
    @property
    def is_discord_enabled(self) -> bool:
        """Discord 기능이 활성화되었는지 확인"""
        return self.discord_bot_token is not None
    
    @property
    def is_notion_enabled(self) -> bool:
        """Notion 통합이 활성화되었는지 확인"""
        return self.notion_api_token is not None and self.notion_todo_database_id is not None
    
    @property
    def is_production(self) -> bool:
        """프로덕션 환경인지 확인"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """개발 환경인지 확인"""
        return self.environment == Environment.DEVELOPMENT
    
    def get_expanded_filesystem_paths(self) -> List[str]:
        """파일시스템 경로들을 절대경로로 확장"""
        expanded = []
        for path in self.allowed_filesystem_paths:
            if path.startswith("~/"):
                expanded.append(os.path.expanduser(path))
            elif path.startswith("./"):
                expanded.append(os.path.abspath(path))
            else:
                expanded.append(path)
        return expanded
    
    def get_secret_value(self, field_name: str) -> Optional[str]:
        """안전하게 시크릿 값 조회"""
        field_value = getattr(self, field_name, None)
        if field_value and hasattr(field_value, 'get_secret_value'):
            return field_value.get_secret_value()
        return field_value
    
    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환"""
        config = {}
        for field_name, field_value in self.__dict__.items():
            if hasattr(field_value, 'get_secret_value'):
                # 시크릿 필드 처리
                if include_secrets:
                    config[field_name] = field_value.get_secret_value()
                else:
                    config[field_name] = "***HIDDEN***"
            else:
                config[field_name] = field_value
        return config
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        # 환경 변수 prefix 사용 가능
        env_prefix = ""


# === 전역 설정 관리 ===
_settings_instance: Optional[UnifiedSettings] = None


def get_settings() -> UnifiedSettings:
    """전역 설정 인스턴스 반환"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = UnifiedSettings()
    return _settings_instance


def reload_settings() -> UnifiedSettings:
    """설정 다시 로드"""
    global _settings_instance
    _settings_instance = UnifiedSettings()
    return _settings_instance


def get_config_summary() -> Dict[str, Any]:
    """설정 요약 정보 반환 (보안 정보 제외)"""
    settings = get_settings()
    return {
        "environment": settings.environment,
        "debug": settings.debug,
        "ai_model": settings.ai_model,
        "discord_enabled": settings.is_discord_enabled,
        "notion_enabled": settings.is_notion_enabled,
        "log_level": settings.log_level,
        "monitoring_enabled": settings.enable_monitoring,
        "data_dir": settings.data_dir,
        "logs_dir": settings.logs_dir
    }