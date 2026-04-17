"""Fixtures for notifications service tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    httpx AsyncClient wired to the notifications FastAPI app.

    Patches start_listener / stop_listener so no real asyncpg connection
    is attempted during the lifespan — these tests don't need a DB.
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

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            yield c
