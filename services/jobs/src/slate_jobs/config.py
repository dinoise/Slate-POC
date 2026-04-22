"""Configuration for the jobs service."""

from __future__ import annotations

from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import SettingsConfigDict

from slate_infra.config import BaseAppSettings

_SERVICE_ROOT = Path(__file__).parents[4]


class Settings(BaseAppSettings):
    model_config = SettingsConfigDict(
        env_file=str(_SERVICE_ROOT / "services" / "jobs" / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: PostgresDsn

    # Cloud Storage — model artifacts
    GCS_BUCKET: str = "lennken-poc-models"
    MODEL_VERSION: str = "v1.0.0"

    # Demand refresh behaviour
    HOURS_AHEAD: int = 24
    PRED_ABS_THRESHOLD: float = 0.5


settings = Settings()
