"""Core application components."""

from .auth import CurrentUser, verify_google_token
from .config import Settings, get_settings, settings
from .database import DBSession, async_session_maker, close_db, engine, get_db, init_db
from .enums import (
    ACTIVE_DISPATCH_STATUSES,
    ACTIVE_TASK_STATUSES,
    BUSY_RESOURCE_STATUSES,
    DispatchStatus,
    ResourceStatus,
    TaskStatus,
)
from .exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from .logging import get_logger, setup_logging

__all__ = [
    # Auth
    "verify_google_token",
    "CurrentUser",
    # Enums
    "TaskStatus",
    "DispatchStatus",
    "ResourceStatus",
    "ACTIVE_TASK_STATUSES",
    "ACTIVE_DISPATCH_STATUSES",
    "BUSY_RESOURCE_STATUSES",
    # Config
    "Settings",
    "get_settings",
    "settings",
    # Database
    "engine",
    "async_session_maker",
    "get_db",
    "DBSession",
    "init_db",
    "close_db",
    # Logging
    "setup_logging",
    "get_logger",
    # Exceptions
    "AppException",
    "NotFoundError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
]
