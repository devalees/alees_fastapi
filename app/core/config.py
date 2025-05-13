from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from pydantic import PostgresDsn, AnyHttpUrl

class Settings(BaseSettings):
    # Application Core
    APP_NAME: str = "FastAPI ERP"
    DEBUG_MODE: bool = False
    ENVIRONMENT: str = "development"  # e.g., development, test, staging, production
    API_V1_PREFIX: str = "/api/v1"
    TIME_ZONE: str = "UTC"
    LOG_LEVEL: str = "INFO"  # Default log level

    # CORS
    CORS_ALLOWED_ORIGINS: List[AnyHttpUrl] = []  # Example: ["http://localhost:3000", "https://myfrontend.example.com"]

    # Database
    DATABASE_URL: PostgresDsn  # Must be provided via env or .env
    DB_ECHO_SQL: bool = False  # For debugging SQL in development
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_CACHE_DB: int = 1
    REDIS_MAX_CONNECTIONS: int = 20  # For the general application cache pool

    # Construct full URL from components
    @property
    def REDIS_CACHE_URL(self) -> str:
        return f"redis://{':' + self.REDIS_PASSWORD + '@' if self.REDIS_PASSWORD else ''}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_CACHE_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra='ignore',  # Ignore extra env vars not defined in the model
        case_sensitive=False  # Environment variables are typically case-insensitive
    )

settings = Settings()  # Single, importable instance 