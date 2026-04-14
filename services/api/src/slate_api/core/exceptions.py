"""Custom exceptions for the application."""


class AppException(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found exception."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class ValidationError(AppException):
    """Validation error exception."""

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message, status_code=422)


class UnauthorizedError(AppException):
    """Unauthorized access exception."""

    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppException):
    """Forbidden access exception."""

    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, status_code=403)


class ConflictError(AppException):
    """Conflict exception (e.g., duplicate resource)."""

    def __init__(self, message: str = "Resource already exists") -> None:
        super().__init__(message, status_code=409)


class ServiceUnavailableError(AppException):
    """External dependency (routing provider, DB) is not reachable."""

    def __init__(self, message: str = "Service unavailable") -> None:
        super().__init__(message, status_code=503)
