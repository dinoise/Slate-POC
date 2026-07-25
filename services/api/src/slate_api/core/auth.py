"""Google ID token verification for the API service.

Re-exports ``verify_google_token`` and ``CurrentUser`` from ``slate_infra.auth``
so the rest of the codebase can continue importing from ``.core.auth``.

The actual dependency implementation is registered at startup in ``main.py``
via ``app.dependency_overrides``.
"""

from slate_infra.auth import CurrentUser, make_verify_google_token, verify_google_token

__all__ = ["verify_google_token", "CurrentUser", "make_verify_google_token"]
