"""Fixtures for notifications service tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from slate_notifications.core.auth import verify_google_token


def _mock_verify_token() -> dict:
    """Return a fake claims dict — bypasses real Google token verification in tests."""
    return {"sub": "test-user", "email": "test@example.com"}


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    httpx AsyncClient wired to the notifications FastAPI app.

    Patches:
    - start_listener / stop_listener — no real asyncpg LISTEN in tests
    - verify_google_token — no real Google token validation in tests
    """
    with (
        patch(
            "slate_notifications.main.start_listener",
            new_callable=lambda: lambda: AsyncMock(),
        ),
        patch(
            "slate_notifications.main.stop_listener",
            new_callable=lambda: lambda: AsyncMock(),
        ),
    ):
        from slate_notifications.main import app

        app.dependency_overrides[verify_google_token] = _mock_verify_token

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

        app.dependency_overrides.clear()
