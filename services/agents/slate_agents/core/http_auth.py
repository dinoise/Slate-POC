"""HTTP auth helper for tools calling slate-api.

In production (Agent Engine → Cloud Run):
    fetch_id_token(audience=SLATE_API_URL) generates a Bearer token that
    slate-api accepts via its allowed_service_audiences setting.

In local dev (adk web → localhost:8000):
    No auth configured on slate-api → token fetch will fail → returns None
    → headers are sent without Authorization → slate-api skips verification.
"""

from __future__ import annotations

import logging

from .config import settings

logger = logging.getLogger(__name__)


def get_api_headers() -> dict[str, str]:
    """Return HTTP headers for slate-api requests, with Bearer token via ADC.

    Works in both local dev (gcloud auth application-default login) and
    production (Agent Engine service account). If ADC is not configured,
    sends without Authorization — slate-api will return 401 in that case.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}

    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, settings.SLATE_API_URL)
        headers["Authorization"] = f"Bearer {token}"
    except Exception as exc:
        logger.warning("Could not fetch ID token for slate-api: %s", exc)

    return headers
