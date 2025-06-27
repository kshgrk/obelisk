"""
Configuration settings for Obelisk Temporal Integration
"""
import os
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseSettings(BaseModel):
    """Database configuration settings"""
    url: str = Field(default="sqlite:///./chat_sessions.db")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=5)
    max_overflow: int = Field(default=10)


class OpenRouterSettings(BaseModel):
    """OpenRouter API configuration"""
    api_key: str = Field(default="")
    base_url: str = Field(default="https://openrouter.ai/api/v1")
    model: str = Field(default="deepseek/deepseek-chat-v3-0324:free")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    timeout: int = Field(default=60)


class TemporalSettings(BaseModel):
    """Temporal workflow configuration"""
    server_url: str = Field(default="localhost:7233")
    namespace: str = Field(default="default")
    task_queue: str = Field(default="obelisk-task-queue")
    workflow_execution_timeout: int = Field(default=3600)  # 1 hour
    activity_execution_timeout: int = Field(default=300)  # 5 minutes
    retry_attempts: int = Field(default=3)


class ServerSettings(BaseModel):
    """FastAPI server configuration"""
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8001)
    debug: bool = Field(default=True)
    reload: bool = Field(default=True)
    cors_origins: list[str] = Field(default=["*"])


class LoggingSettings(BaseModel):
    """Logging configuration"""
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_path: Optional[str] = Field(default=None)


class ChatSettings(BaseModel):
    """Chat-specific configuration"""
    max_context_messages: int = Field(default=5)
    session_timeout_hours: int = Field(default=24)
    max_message_length: int = Field(default=10000)
    enable_streaming: bool = Field(default=True)


class Settings(BaseModel):
    """Main application settings"""
    app_name: str = "Obelisk Temporal Chat Server"
    app_version: str = "0.1.0"
    
    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    chat: ChatSettings = Field(default_factory=ChatSettings)

    def __init__(self, **kwargs):
        # Load environment variables with defaults
        env_data = {
            "database": {
                "url": os.getenv("DATABASE_URL", "sqlite:///./chat_sessions.db"),
                "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
                "pool_size": int(os.getenv("DATABASE_POOL_SIZE", "5")),
                "max_overflow": int(os.getenv("DATABASE_MAX_OVERFLOW", "10")),
            },
            "openrouter": {
                "api_key": os.getenv("OPENROUTER_KEY", ""),
                "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                "model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free"),
                "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", "0.7")),
                "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "1000")),
                "timeout": int(os.getenv("OPENROUTER_TIMEOUT", "60")),
            },
            "temporal": {
                "server_url": os.getenv("TEMPORAL_SERVER_URL", "localhost:7233"),
                "namespace": os.getenv("TEMPORAL_NAMESPACE", "default"),
                "task_queue": os.getenv("TEMPORAL_TASK_QUEUE", "obelisk-task-queue"),
                "workflow_execution_timeout": int(os.getenv("TEMPORAL_WORKFLOW_TIMEOUT", "3600")),
                "activity_execution_timeout": int(os.getenv("TEMPORAL_ACTIVITY_TIMEOUT", "300")),
                "retry_attempts": int(os.getenv("TEMPORAL_RETRY_ATTEMPTS", "3")),
            },
            "server": {
                "host": os.getenv("SERVER_HOST", "127.0.0.1"),
                "port": int(os.getenv("SERVER_PORT", "8001")),
                "debug": os.getenv("SERVER_DEBUG", "true").lower() == "true",
                "reload": os.getenv("SERVER_RELOAD", "true").lower() == "true",
                "cors_origins": os.getenv("CORS_ORIGINS", "*").split(","),
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "format": os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                "file_path": os.getenv("LOG_FILE_PATH"),
            },
            "chat": {
                "max_context_messages": int(os.getenv("CHAT_MAX_CONTEXT_MESSAGES", "5")),
                "session_timeout_hours": int(os.getenv("CHAT_SESSION_TIMEOUT_HOURS", "24")),
                "max_message_length": int(os.getenv("CHAT_MAX_MESSAGE_LENGTH", "10000")),
                "enable_streaming": os.getenv("CHAT_ENABLE_STREAMING", "true").lower() == "true",
            },
        }
        
        # Merge with any provided kwargs
        for key, value in kwargs.items():
            if key in env_data:
                env_data[key].update(value)
        
        super().__init__(**env_data, **kwargs)


# Global settings instance
settings = Settings() 