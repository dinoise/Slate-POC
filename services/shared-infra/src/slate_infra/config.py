"""Base application settings shared across all Slate services.

Each service subclasses ``BaseAppSettings``, overrides ``model_config`` with
absolute paths to its own ``.env`` files, and adds service-specific fields::

    from pathlib import Path
    from pydantic_settings import SettingsConfigDict
    from slate_infra.config import BaseAppSettings

    _SERVICE_ROOT = Path(__file__).parents[3]
    _ENV = os.getenv("ENVIRONMENT", "development")

    class Settings(BaseAppSettings):
        model_config = SettingsConfigDict(
            env_file={
                "development": (str(_SERVICE_ROOT / ".env"),),
                "test": (str(_SERVICE_ROOT / ".env.test"),),
            }.get(_ENV, ()),
            ...
        )
        DATABASE_POOL_SIZE: int = 20
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """Common settings fields shared by all Slate services.

    Subclasses must override ``model_config`` to point ``env_file`` at the
    correct absolute path for their service. This base class intentionally
    does NOT set ``env_file`` — if it did, pydantic-settings would resolve
    the path relative to CWD (the monorepo root), not the service directory.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"

    # CORS — comma-separated origins; "*" allows all in dev
    CORS_ORIGINS: str = "*"

    # Google OAuth — comma-separated client IDs (admin, adjuster, reporter, …)
    # If empty, token verification is skipped (dev / tests).
    GOOGLE_CLIENT_ID: str = ""

    # Logging — empty string means "derive from ENVIRONMENT"
    LOG_LEVEL: str = ""

    @property
    def google_client_ids(self) -> list[str]:
        """List of allowed OAuth client IDs."""
        return [c.strip() for c in self.GOOGLE_CLIENT_ID.split(",") if c.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS CSV string into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT in ("development", "local", "test")

    @property
    def effective_log_level(self) -> str:
        """Explicit LOG_LEVEL override > environment default."""
        if self.LOG_LEVEL:
            return self.LOG_LEVEL.upper()
        return "DEBUG" if self.is_local else "INFO"
