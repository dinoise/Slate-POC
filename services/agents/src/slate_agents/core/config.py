"""Configuration for slate-agents — ADK agent code deployed to Vertex AI Agent Engine."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = os.getenv("ENVIRONMENT", "development")

# Resolve .env only for local dev — walk up from this file to find the service
# root (services/agents/). In Agent Engine the package is copied flat into
# /code/ with a temp name, so parents[4] would not exist; we guard with exists().
_SERVICE_ROOT = Path(__file__).parent
for _ in range(4):
    _SERVICE_ROOT = _SERVICE_ROOT.parent

_LOCAL_ENV_FILE = str(_SERVICE_ROOT / ".env") if (_SERVICE_ROOT / ".env").exists() else ""
_TEST_ENV_FILE = str(_SERVICE_ROOT / ".env.test") if (_SERVICE_ROOT / ".env.test").exists() else ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file={
            "development": _LOCAL_ENV_FILE,
            "test": _TEST_ENV_FILE,
        }.get(_ENV, ""),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Entorno ───────────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    # ── Google Cloud ──────────────────────────────────────────────────────────
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    # ── Modelo ────────────────────────────────────────────────────────────────
    ROOT_AGENT_MODEL: str = "gemini-2.5-flash-lite"

    # ── slate-api ─────────────────────────────────────────────────────────────
    # URL base a la que las tools hacen requests HTTP.
    # En local: http://localhost:8000
    # En Agent Engine: URL del Cloud Run de slate-api (requiere ID token auth)
    SLATE_API_URL: str = "http://localhost:8000"

    # ── Staging bucket (solo para deploy, no en runtime) ─────────────────────
    GCS_STAGING_BUCKET: str = ""

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = ""

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT in ("development", "local", "test")

    @property
    def effective_log_level(self) -> str:
        if self.LOG_LEVEL:
            return self.LOG_LEVEL.upper()
        return "DEBUG" if self.is_local else "INFO"


settings = Settings()
