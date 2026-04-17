"""Google ID token verification for the notifications service."""

from __future__ import annotations

from fastapi import HTTPException, Query, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

_google_request = google_requests.Request()


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def verify_google_token(
    request: Request,
    token_param: str | None = Query(default=None, alias="token"),
) -> dict:
    """
    FastAPI dependency — verifies the Google ID token.

    Accepts the token from:
    1. ``?token=`` query parameter (required for EventSource, which cannot set headers)
    2. ``Authorization: Bearer <token>`` header

    Raises 401 if token is missing, invalid, or expired.
    Skips verification if GOOGLE_CLIENT_ID is not set (local dev).
    """
    if not settings.GOOGLE_CLIENT_ID:
        logger.warning("GOOGLE_CLIENT_ID not set — skipping token verification")
        return {"sub": "dev", "email": "dev@local"}

    token = token_param or _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            _google_request,
            audience=settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=10,
        )
        return claims
    except ValueError as e:
        logger.warning("Invalid Google ID token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
