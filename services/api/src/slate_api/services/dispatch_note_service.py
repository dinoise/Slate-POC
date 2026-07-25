"""Business logic for DispatchNote."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..models import DispatchNote
from ..repositories.dispatch_note_repository import DispatchNoteRepository
from ..repositories.dispatch_repository import DispatchRepository


class DispatchNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = DispatchNoteRepository(db)
        self.dispatch_repository = DispatchRepository(db)

    async def create_note(
        self,
        dispatch_id: int,
        content: str,
        agent_type: str | None = None,
        created_by_agent: bool = True,
    ) -> DispatchNote:
        if not await self.dispatch_repository.exists(dispatch_id):
            raise NotFoundError(f"Dispatch {dispatch_id} not found")
        return await self.repository.create(
            dispatch_id=dispatch_id,
            content=content,
            agent_type=agent_type,
            created_by_agent=created_by_agent,
        )

    async def get_notes(self, dispatch_id: int) -> list[DispatchNote]:
        if not await self.dispatch_repository.exists(dispatch_id):
            raise NotFoundError(f"Dispatch {dispatch_id} not found")
        return await self.repository.get_by_dispatch(dispatch_id)
