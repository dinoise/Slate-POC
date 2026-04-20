"""Configuration for the notifications service."""

from __future__ import annotations

import os

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = os.getenv("ENVIRONMENT", "development")
_ENV_FILES: dict[str, tuple[str, ...]] = {
    "development": (".env",),
    "test": (".env.test",),
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES.get(_ENV, ()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "slate-notifications"
    VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    DATABASE_URL: PostgresDsn

    # Comma-separated origins — "*" allows all in dev
    CORS_ORIGINS: str = "*"

    # Google OAuth — Client ID para verificar tokens de GIS del frontend
    # Si está vacío, la verificación se omite (útil para tests y dev local)
    GOOGLE_CLIENT_ID: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def google_client_ids(self) -> list[str]:
        return [c.strip() for c in self.GOOGLE_CLIENT_ID.split(",") if c.strip()]


settings = Settings()
