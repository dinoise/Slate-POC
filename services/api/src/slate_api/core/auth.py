"""Google ID token verification for end-user authentication."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)

# Reusable Google transport request — not thread-unsafe, create once per process
_google_request = google_requests.Request()


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def verify_google_token(request: Request) -> dict:
    """
    FastAPI dependency — verifies the Google ID token from the Authorization header.

    Raises 401 if:
    - No token present
    - Token is invalid, expired, or has wrong audience

    Returns the decoded token claims dict (includes 'sub', 'email', 'name').
    """
    if not settings.GOOGLE_CLIENT_ID:
        # Auth disabled locally if GOOGLE_CLIENT_ID is not configured
        logger.warning("GOOGLE_CLIENT_ID not set — skipping token verification")
        return {"sub": "dev", "email": "dev@local"}

    token = _extract_bearer(request)
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


# Typed dependency alias for use in route signatures
CurrentUser = Annotated[dict, Depends(verify_google_token)]
