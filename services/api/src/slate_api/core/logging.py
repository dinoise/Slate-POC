"""Logging setup for the API service — delegates to slate_infra.logging."""

from slate_infra.logging import get_logger
from slate_infra.logging import setup_logging as _setup_infra

from .config import settings


def setup_logging() -> None:
    """Configure logging using service settings."""
    _setup_infra(log_level=settings.effective_log_level, is_local=settings.is_local)


__all__ = ["setup_logging", "get_logger"]
