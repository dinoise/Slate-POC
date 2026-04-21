"""Custom exceptions for the API service — re-exported from slate_infra."""

from slate_infra.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)

__all__ = [
    "AppException",
    "NotFoundError",
    "ValidationError",
    "UnauthorizedError",
    "ForbiddenError",
    "ConflictError",
    "ServiceUnavailableError",
]
