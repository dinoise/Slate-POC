"""Fixtures for notifications service tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from slate_notifications.core.auth import verify_google_token


def _mock_verify_token() -> dict:
    """Return a fake claims dict — bypasses real Google token verification in tests."""
    return {"sub": "test-user", "email": "test@example.com"}


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient wired to the notifications FastAPI app.

    Patches the background tasks (listener + outbox poller) so no real
    asyncpg connection or DB session is required during tests.
    """

    # Patch the coroutine functions used inside the lifespan so that the
    # asyncio.create_task() calls in main.py don't start real background work.
    async def _noop(*_args, **_kwargs) -> None:  # noqa: RUF029
        pass

    with (
        patch("slate_notifications.services.listener.listen", new=_noop),
        patch("slate_notifications.services.outbox_poller.poll", new=_noop),
    ):
        from slate_notifications.main import app

        app.dependency_overrides[verify_google_token] = _mock_verify_token

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c

        app.dependency_overrides.clear()
