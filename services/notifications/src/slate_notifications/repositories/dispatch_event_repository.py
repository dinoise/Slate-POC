"""Repository for DispatchEvent outbox operations."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from slate_core.models import DispatchEvent


class DispatchEventRepository:
    """Read and drain the dispatch_events outbox table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_unprocessed(self, limit: int = 100) -> list[DispatchEvent]:
        """Return unprocessed events ordered by creation time, locking rows."""
        result = await self.db.execute(
            select(DispatchEvent)
            .where(DispatchEvent.processed_at.is_(None))
            .order_by(DispatchEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_processed(self, ids: list[int], processed_by: str) -> None:
        """Mark a batch of events as processed."""
        if not ids:
            return
        await self.db.execute(
            update(DispatchEvent)
            .where(DispatchEvent.id.in_(ids))
            .values(
                processed_at=datetime.now(UTC),
                processed_by=processed_by,
            )
        )
