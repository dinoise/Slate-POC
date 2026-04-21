"""Repository for AssignmentEvent outbox operations."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from slate_core.models import AssignmentEvent


class AssignmentEventRepository:
    """Read and drain the assignment_events outbox table."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_unprocessed(self, limit: int = 100) -> list[AssignmentEvent]:
        """Return unprocessed events ordered by creation time, locking rows.

        Uses SKIP LOCKED so that a future second instance (if ever deployed)
        won't process the same batch twice.
        """
        result = await self.db.execute(
            select(AssignmentEvent)
            .where(AssignmentEvent.processed_at.is_(None))
            .order_by(AssignmentEvent.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def mark_processed(self, ids: list[int], processed_by: str) -> None:
        """Mark a batch of events as processed.

        Does NOT commit — the caller is responsible for committing the
        transaction (e.g. via ``async with session.begin()`` context manager).
        """
        if not ids:
            return
        await self.db.execute(
            update(AssignmentEvent)
            .where(AssignmentEvent.id.in_(ids))
            .values(
                processed_at=datetime.now(UTC),
                processed_by=processed_by,
            )
        )
