"""Repository for DispatchNote."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DispatchNote
from .base_repository import BaseRepository


class DispatchNoteRepository(BaseRepository[DispatchNote]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, DispatchNote)

    async def get_by_dispatch(self, dispatch_id: int) -> list[DispatchNote]:
        query = (
            select(DispatchNote)
            .where(DispatchNote.dispatch_id == dispatch_id)
            .order_by(DispatchNote.created_at)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
