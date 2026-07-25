"""Shared fixtures for slate_jobs tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from slate_core.models.base import Base


@pytest.fixture(scope="session")
def pg_container():
    """Start a throwaway PostGIS container for the test session."""
    with PostgresContainer("postgis/postgis:16-3.4") as pg:
        yield pg


@pytest_asyncio.fixture(scope="session")
async def test_engine(pg_container: PostgresContainer):
    """Create schema once per session."""
    sync_url: str = pg_container.get_connection_url()
    async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)

    engine = create_async_engine(async_url, poolclass=NullPool, future=True)

    async with engine.begin() as conn:
        # Enable PostGIS extension required for geometry columns
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Isolated session per test via SAVEPOINT rollback."""
    async with test_engine.connect() as conn:
        await conn.begin()
        session = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )()
        await conn.begin_nested()

        yield session

        await session.close()
        await conn.rollback()
