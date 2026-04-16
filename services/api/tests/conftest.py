"""Shared fixtures for all API integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from slate_api.core.config import settings
from slate_api.core.database import get_db
from slate_api.core.provider_registry import get_active_provider
from slate_api.main import app
from slate_api.models.base import Base

# ── Engine ────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine and tables once per session."""
    engine = create_async_engine(str(settings.DATABASE_URL), poolclass=NullPool, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ── Session ───────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an async DB session isolated per test via nested transaction (SAVEPOINT).
    Rolls back after each test so the next one starts with a clean slate.
    """
    async with test_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        session = session_factory()
        await conn.begin_nested()  # SAVEPOINT

        yield session

        await session.close()
        await conn.rollback()


# ── HTTP Client ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an httpx AsyncClient wired to the FastAPI app.

    Overrides:
    - get_db → uses the test session (same transaction as db_session)
    - start_listener / stop_listener → AsyncMock (no asyncpg LISTEN in tests)
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    # Mock routing provider — tests for incidents/assignments that call ProviderDep
    # do not need a real routing provider (no optimize calls in these tests).
    mock_provider = MagicMock()
    mock_provider.provider_name = "mock"
    mock_provider.supports_traffic = False

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_active_provider] = lambda: mock_provider

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────


def api(path: str) -> str:
    """Prepend the API v1 prefix to a path."""
    return f"/api/v1{path}"
