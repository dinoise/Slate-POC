"""Database connection and session management."""
import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from .config import settings

logger = logging.getLogger(__name__)

# Create async engine
engine: AsyncEngine = create_async_engine(
    str(settings.DATABASE_URL),
    poolclass=NullPool,
    echo=settings.DEBUG,
    future=True,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.

    Yields:
        AsyncSession: Database session
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# Type alias for dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def init_db() -> None:
    """Initialize database connection on startup."""
    # Test connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection established")


async def close_db() -> None:
    """Close database connection on shutdown."""
    await engine.dispose()
    logger.info("Database connection closed")
