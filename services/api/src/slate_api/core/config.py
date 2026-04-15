"""Application configuration using Pydantic Settings."""

import os
from functools import lru_cache
from typing import Any

from pydantic import (
    PostgresDsn,
    RedisDsn,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine which .env file to load based on ENVIRONMENT.
# In production (Cloud Run), no file is loaded — vars come from the runtime.
_ENV = os.getenv("ENVIRONMENT", "development")
_ENV_FILES: dict[str, tuple[str, ...]] = {
    "development": (".env",),
    "test": (".env.test",),
}
_env_files = _ENV_FILES.get(_ENV, ())


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_env_files,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn

    # API
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Adjuster Optimizer"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Routing / Traffic provider
    TRAFFIC_PROVIDER: str = "osrm"  # "osrm" | "valhalla" | "google"
    TRAFFIC_TOP_K: int = 5  # top-K candidates to rerank with traffic

    # OSRM
    OSRM_URL: str = "http://router.project-osrm.org"

    # Valhalla (not yet implemented)
    VALHALLA_URL: str = "http://localhost:8002"

    # Google Routes API (not yet implemented)
    GOOGLE_ROUTES_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Logging
    LOG_LEVEL: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"

    @computed_field  # type: ignore[misc]
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"

    @computed_field  # type: ignore[misc]
    @property
    def is_local(self) -> bool:
        """Check if running locally (not in cloud)."""
        return self.ENVIRONMENT in ("development", "local")

    @computed_field  # type: ignore[misc]
    @property
    def effective_log_level(self) -> str:
        """Determine log level: explicit override > environment default."""
        if self.LOG_LEVEL:
            return self.LOG_LEVEL
        return "DEBUG" if self.is_local else "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
