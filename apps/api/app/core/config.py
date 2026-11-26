"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://archradar:archradar@localhost:5432/archradar"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class Settings(BaseSettings):
    """Runtime settings for the ArchRadar FastAPI service."""

    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "archradar-api"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = DEFAULT_DATABASE_URL
    redis_url: str = DEFAULT_REDIS_URL
    cors_origins: str = "http://localhost:3000"

    gemini_api_key: str = ""
    github_webhook_secret: str = ""
    github_app_private_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _default_database_url_if_empty(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_DATABASE_URL
        return value

    @field_validator("redis_url", mode="before")
    @classmethod
    def _default_redis_url_if_empty(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return DEFAULT_REDIS_URL
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
