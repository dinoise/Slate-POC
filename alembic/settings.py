"""Alembic-specific settings — only DATABASE_URL is required."""

from pathlib import Path

from pydantic_settings import BaseSettings


class AlembicSettings(BaseSettings):
    DATABASE_URL: str

    model_config = {
        "env_file": str(Path(__file__).parent / ".env"),
        "extra": "ignore",
    }


settings = AlembicSettings()
