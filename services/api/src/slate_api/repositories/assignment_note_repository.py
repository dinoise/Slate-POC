"""Repository for AssignmentNote."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.assignment_note import AssignmentNote
from .base_repository import BaseRepository


class AssignmentNoteRepository(BaseRepository[AssignmentNote]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AssignmentNote)

    async def get_by_assignment(self, assignment_id: int) -> list[AssignmentNote]:
        query = (
            select(AssignmentNote)
            .where(AssignmentNote.assignment_id == assignment_id)
            .order_by(AssignmentNote.created_at)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
