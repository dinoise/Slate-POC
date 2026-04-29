"""Business logic for AssignmentNote."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import NotFoundError
from ..models.assignment_note import AssignmentNote
from ..repositories.assignment_note_repository import AssignmentNoteRepository
from ..repositories.assignment_repository import AssignmentRepository


class AssignmentNoteService:
    def __init__(self, db: AsyncSession) -> None:
        self.repository = AssignmentNoteRepository(db)
        self.assignment_repository = AssignmentRepository(db)

    async def create_note(
        self,
        assignment_id: int,
        content: str,
        agent_type: str | None = None,
        created_by_agent: bool = True,
    ) -> AssignmentNote:
        if not await self.assignment_repository.exists(assignment_id):
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return await self.repository.create(
            assignment_id=assignment_id,
            content=content,
            agent_type=agent_type,
            created_by_agent=created_by_agent,
        )

    async def get_notes(self, assignment_id: int) -> list[AssignmentNote]:
        if not await self.assignment_repository.exists(assignment_id):
            raise NotFoundError(f"Assignment {assignment_id} not found")
        return await self.repository.get_by_assignment(assignment_id)
