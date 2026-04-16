"""Configuration for the notifications service."""

from __future__ import annotations

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "slate-notifications"
    VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: PostgresDsn

    # CORS — allow all origins in dev; restrict in prod via env
    CORS_ORIGINS: list[str] = ["*"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
