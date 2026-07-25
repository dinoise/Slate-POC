"""Database helpers for jobs — sync asyncpg connection."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import settings

engine = create_async_engine(str(settings.DATABASE_URL), poolclass=NullPool, future=True)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
