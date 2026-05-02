"""HTTP auth helper for tools calling slate-api.

In production (Agent Engine → Cloud Run):
    fetch_id_token(audience=SLATE_API_URL) generates a Bearer token that
    slate-api accepts via its allowed_service_audiences setting.

In local dev (adk web → localhost:8000):
    No auth configured on slate-api → token fetch will fail → returns None
    → headers are sent without Authorization → slate-api skips verification.
"""

from __future__ import annotations

from .config import settings
from .logging import get_logger

logger = get_logger(__name__)


def get_api_headers() -> dict[str, str]:
    """Return HTTP headers for slate-api requests, with Bearer token via ADC."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    audience = settings.SLATE_API_URL

    logger.debug("get_api_headers: audience=%s", audience or "<EMPTY>")

    if not audience:
        logger.error(
            "SLATE_API_URL is not configured — all tool HTTP calls will fail. "
            "Verify env_vars in Agent Engine deployment."
        )
        return headers

    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
        headers["Authorization"] = f"Bearer {token}"
        logger.debug("ID token fetched successfully for audience=%s", audience)
    except Exception as exc:
        logger.warning(
            "ID token fetch failed (audience=%s): %s — sending request without Authorization",
            audience,
            exc,
        )

    return headers
