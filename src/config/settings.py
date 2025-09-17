"""
Configuration settings for Obelisk Temporal Integration
"""
import os
import sqlite3
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_config_value(key: str, db_path: str = "chat_sessions.db") -> str:
    """Get a configuration value from the config table in the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        result = cursor.fetchone()
        conn.close()

        if result:
            return result[0]
        return ""
    except Exception as e:
        print(f"Error reading config from database: {e}")
        return ""


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


class MistralSettings(BaseModel):
    """Mistral AI API configuration"""
    api_key: str = Field(default="")
    base_url: str = Field(default="https://api.mistral.ai/v1")
    model: str = Field(default="mistral-small-latest")
    timeout: int = Field(default=30)


class TemporalSettings(BaseModel):
    """Temporal workflow configuration"""
    server_url: str = Field(default="localhost:7233")
    web_ui_port: int = Field(default=8280)
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
    mistral: MistralSettings = Field(default_factory=MistralSettings)
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
                "api_key": get_config_value("openrouter_api_key"),
                "base_url": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                "model": os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324:free"),
                "temperature": float(os.getenv("OPENROUTER_TEMPERATURE", "0.7")),
                "max_tokens": int(os.getenv("OPENROUTER_MAX_TOKENS", "1000")),
                "timeout": int(os.getenv("OPENROUTER_TIMEOUT", "60")),
            },
            "mistral": {
                "api_key": os.getenv("MISTRAL_API_KEY", ""),
                "base_url": os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1"),
                "model": os.getenv("MISTRAL_MODEL", "mistral-small-latest"),
                "timeout": int(os.getenv("MISTRAL_TIMEOUT", "30")),
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

    @property
    def mistral_api_key(self) -> str:
        """Get Mistral API key"""
        return self.mistral.api_key
    
    def refresh_openrouter_api_key(self) -> str:
        """Refresh OpenRouter API key from database and return the current value"""
        new_key = get_config_value("openrouter_api_key")
        self.openrouter.api_key = new_key
        return new_key

    def refresh_from_database(self):
        """Refresh all configuration values from the database"""
        # Refresh OpenRouter settings
        self.openrouter.api_key = get_config_value("openrouter_api_key")
        self.openrouter.base_url = get_config_value("openrouter_base_url") or "https://openrouter.ai/api/v1"
        self.openrouter.model = get_config_value("openrouter_model") or "deepseek/deepseek-chat-v3-0324:free"
        self.openrouter.temperature = float(get_config_value("openrouter_temperature") or "0.7")
        self.openrouter.max_tokens = int(get_config_value("openrouter_max_tokens") or "1000")
        self.openrouter.timeout = int(get_config_value("openrouter_timeout") or "60")

        print(f"Settings refreshed from database - API key: {'configured' if self.openrouter.api_key else 'not configured'}")


# Global settings instance
settings = Settings()

def get_settings() -> Settings:
    """Get the global settings instance"""
    return settings 