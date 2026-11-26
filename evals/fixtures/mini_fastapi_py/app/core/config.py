"""Application configuration settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    webhook_secret: str = "whsec_demo"
    redis_url: str = "redis://localhost:6379/0"


def get_settings() -> Settings:
    return Settings()
