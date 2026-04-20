"""Google ID token verification for the notifications service."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

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


def _peek_audience(token: str) -> str | None:
    """Read 'aud' from the JWT payload without verifying the signature.

    Used to select the correct client ID before cryptographic verification.
    The value is untrusted until the signature is verified — only used for
    audience routing.
    """
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("aud")
    except Exception:
        return None


def verify_google_token(
    request: Request,
    token_param: str | None = Query(default=None, alias="token"),
) -> Mapping[str, Any]:
    """FastAPI dependency — verifies the Google ID token.

    Accepts the token from:
    1. ``?token=`` query parameter (required for EventSource, which cannot set headers)
    2. ``Authorization: Bearer <token>`` header

    Supports multiple GOOGLE_CLIENT_ID values (comma-separated) via audience peek.
    Skips verification if GOOGLE_CLIENT_ID is not set (local dev / tests).

    Raises 401 if token is missing, audience is not allowed, or signature is invalid.
    """
    client_ids = settings.google_client_ids
    if not client_ids:
        logger.warning("GOOGLE_CLIENT_ID not set — skipping token verification")
        return {"sub": "dev", "email": "dev@local"}

    token = token_param or _extract_bearer(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    client_ids_set = set(client_ids)
    audience = _peek_audience(token)
    if audience not in client_ids_set:
        logger.warning("Token audience '%s' not in allowed client IDs", audience)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = id_token.verify_oauth2_token(
            token,
            _google_request,
            audience=audience,
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
