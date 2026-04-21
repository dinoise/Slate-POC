"""Configuration for the notifications service."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import SettingsConfigDict

from slate_infra.config import BaseAppSettings

# Resolve .env files relative to the service root — works regardless of CWD.
# Path: src/slate_notifications/core/config.py → parents[3] = services/notifications/
_SERVICE_ROOT = Path(__file__).parents[3]
_ENV = os.getenv("ENVIRONMENT", "development")
_ENV_FILES: dict[str, tuple[str, ...]] = {
    "development": (str(_SERVICE_ROOT / ".env"),),
    "test": (str(_SERVICE_ROOT / ".env.test"),),
}


class Settings(BaseAppSettings):
    """Notifications-specific settings."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES.get(_ENV, ()),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    PROJECT_NAME: str = "slate-notifications"
    VERSION: str = "0.1.0"

    DATABASE_URL: PostgresDsn


settings = Settings()
