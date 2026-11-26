"""Application settings loaded from environment variables."""

import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://archradar:archradar@localhost:5432/archradar"
DEFAULT_VERCEL_SQLITE_URL = "sqlite+aiosqlite:////tmp/archradar.db"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def _is_vercel_runtime() -> bool:
    return os.environ.get("VERCEL") == "1"


def _default_database_url() -> str:
    return DEFAULT_VERCEL_SQLITE_URL if _is_vercel_runtime() else DEFAULT_DATABASE_URL


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
    seed_demo_on_startup: bool = False
    auto_init_db: bool = False
    allow_local_path_indexing: bool | None = None

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    github_token: str = ""
    github_webhook_secret: str = ""
    github_app_private_key: str = ""

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return _default_database_url()
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed == DEFAULT_DATABASE_URL and _is_vercel_runtime():
                return DEFAULT_VERCEL_SQLITE_URL
            if trimmed.startswith("postgres://"):
                return "postgresql+asyncpg://" + trimmed[len("postgres://") :]
            if trimmed.startswith("postgresql://"):
                return "postgresql+asyncpg://" + trimmed[len("postgresql://") :]
            return trimmed
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

    @property
    def local_path_indexing_enabled(self) -> bool:
        """Disable arbitrary server filesystem indexing in cloud/production deployments."""
        if self.allow_local_path_indexing is not None:
            return self.allow_local_path_indexing
        return not (_is_vercel_runtime() or self.environment.lower() == "production")

    @property
    def should_auto_init_db(self) -> bool:
        """Enable idempotent metadata table creation on serverless/SQLite cold starts."""
        return self.auto_init_db or _is_vercel_runtime()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
