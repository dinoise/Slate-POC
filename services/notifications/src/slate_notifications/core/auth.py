"""Google ID token verification for the notifications service.

Re-exports from slate_infra.auth. The dependency is wired up at startup
in main.py via app.dependency_overrides.

Notifications accepts the token from both:
- ``Authorization: Bearer <token>`` header (standard HTTP)
- ``?token=`` query parameter (required for SSE / EventSource)
"""

from slate_infra.auth import CurrentUser, make_verify_google_token, verify_google_token

__all__ = ["verify_google_token", "CurrentUser", "make_verify_google_token"]
