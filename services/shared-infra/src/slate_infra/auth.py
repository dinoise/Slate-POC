"""Google ID token verification — shared across all Slate services.

Usage
-----
Standard HTTP endpoints (Authorization header only)::

    from slate_infra.auth import verify_google_token, CurrentUser

    @router.get("/resource")
    async def get_resource(user: CurrentUser) -> ...:
        ...

SSE / EventSource endpoints (also accepts ``?token=`` query param)::

    from slate_infra.auth import make_verify_google_token
    from typing import Annotated
    from fastapi import Depends

    _verify = make_verify_google_token(accept_query_token=True)
    SSEUser = Annotated[dict, Depends(_verify)]

    @router.get("/stream")
    async def stream(user: SSEUser) -> ...:
        ...
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable, Mapping
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, Request, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

logger = logging.getLogger(__name__)

# Reusable Google transport — create once per process
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
        # JWT uses base64url without padding — add required padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("aud")
    except Exception:
        return None


def make_verify_google_token(
    *,
    client_ids: list[str],
    allowed_service_audiences: list[str] | None = None,
    accept_query_token: bool = False,
) -> Callable[..., Mapping[str, Any]]:
    """Factory that returns a FastAPI dependency for Google ID token verification.

    Supports two token types:
    - **User tokens** (OAuth2): ``aud`` is an OAuth client ID like
      ``123456789-abc.apps.googleusercontent.com``. Used by frontend apps.
    - **Service tokens** (service-to-service): ``aud`` is the target Cloud Run
      URL like ``https://slate-api.run.app``. Used by Vertex AI Agent Engine
      tools calling slate-api via ``google.oauth2.id_token.fetch_id_token()``.

    Args:
        client_ids: Allowed OAuth client IDs for user tokens. If empty and
            ``allowed_service_audiences`` is also empty, verification is
            skipped (useful for local dev and tests).
        allowed_service_audiences: Allowed Cloud Run URL audiences for
            service-to-service tokens (Agent Engine → slate-api calls).
            Defaults to ``None`` (no service tokens accepted).
        accept_query_token: If ``True``, also accepts the token from the
            ``?token=`` query parameter. Required for SSE/EventSource clients
            that cannot set custom headers. Defaults to ``False``.

    Returns:
        A callable suitable for use with ``fastapi.Depends``.
    """
    _allowed: frozenset[str] = frozenset(client_ids) | frozenset(allowed_service_audiences or [])

    def _check(token: str | None) -> Mapping[str, Any]:
        """Core verification logic shared by both variants."""
        if not _allowed:
            logger.warning("No auth config — skipping token verification")
            return {"sub": "dev", "email": "dev@local"}

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header missing or invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )

        audience = _peek_audience(token)
        if audience not in _allowed:
            logger.warning("Token audience '%s' not in allowed set", audience)
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

    if accept_query_token:
        # SSE variant: also reads ?token= query param (EventSource cannot set headers)
        def _verify_with_query(
            request: Request,
            token_param: str | None = Query(default=None, alias="token"),
        ) -> Mapping[str, Any]:
            return _check(token_param or _extract_bearer(request))

        return _verify_with_query
    else:
        # Standard variant: Authorization header only
        def _verify_header_only(request: Request) -> Mapping[str, Any]:
            return _check(_extract_bearer(request))

        return _verify_header_only


def verify_google_token(request: Request) -> Mapping[str, Any]:
    """FastAPI dependency — verifies Google ID token from Authorization header.

    This is a module-level placeholder. Each service must wire it up at startup
    via ``app.dependency_overrides`` or by calling ``make_verify_google_token``
    with the service's own settings. See module docstring for usage examples.

    .. warning::
        Do NOT use this directly as a route dependency — it has no access to
        service settings. Use ``make_verify_google_token`` instead.
    """
    raise NotImplementedError(
        "verify_google_token must be overridden. "
        "Call make_verify_google_token(client_ids=settings.google_client_ids) "
        "and register the result via app.dependency_overrides."
    )


# Typed dependency alias — services override the implementation via dependency_overrides
CurrentUser = Annotated[dict, Depends(verify_google_token)]
