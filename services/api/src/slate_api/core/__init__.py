"""Core application components."""

from .auth import CurrentUser, verify_google_token
from .config import Settings, get_settings, settings
from .database import DBSession, async_session_maker, close_db, engine, get_db, init_db
from .enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    ACTIVE_INCIDENT_STATUSES,
    BUSY_ADJUSTER_STATUS,
    AdjusterStatus,
    AssignmentStatus,
    IncidentStatus,
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
    "IncidentStatus",
    "AssignmentStatus",
    "AdjusterStatus",
    "ACTIVE_INCIDENT_STATUSES",
    "ACTIVE_ASSIGNMENT_STATUSES",
    "BUSY_ADJUSTER_STATUS",
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
