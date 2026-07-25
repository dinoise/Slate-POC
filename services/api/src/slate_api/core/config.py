"""Application configuration for the API service."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import PostgresDsn, RedisDsn, computed_field
from pydantic_settings import SettingsConfigDict

from slate_infra.config import BaseAppSettings

# Resolve .env files relative to the service root — works regardless of CWD.
# Path: src/slate_api/core/config.py → parents[3] = services/api/
_SERVICE_ROOT = Path(__file__).parents[3]
_ENV = os.getenv("ENVIRONMENT", "development")
_ENV_FILES: dict[str, tuple[str, ...]] = {
    "development": (str(_SERVICE_ROOT / ".env"),),
    "test": (str(_SERVICE_ROOT / ".env.test"),),
}


class Settings(BaseAppSettings):
    """API-specific settings, extending the shared base."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES.get(_ENV, ()),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"  # type: ignore[assignment]

    # API metadata
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Slate API"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Security (unused for now, kept for future JWT signing)
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Routing / Traffic provider
    TRAFFIC_PROVIDER: str = "osrm"  # "osrm" | "valhalla" | "google"
    TRAFFIC_TOP_K: int = 5

    # OSRM
    OSRM_URL: str = "http://router.project-osrm.org"

    # Valhalla
    VALHALLA_URL: str = "http://localhost:8002"

    # Google Routes API
    GOOGLE_ROUTES_API_KEY: str = ""

    # Vertex AI / Agent Engine
    VERTEX_PROJECT: str = ""
    VERTEX_LOCATION: str = "us-central1"
    AGENT_ENGINE_ID: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[misc]
    @property
    def agent_engine_configured(self) -> bool:
        return bool(self.VERTEX_PROJECT and self.AGENT_ENGINE_ID)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
