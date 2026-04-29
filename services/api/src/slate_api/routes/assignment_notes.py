"""Assignment notes routes — used by the field_guide AI agent."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..core import DBSession
from ..schemas.assignment_note import AssignmentNoteCreate, AssignmentNoteRead
from ..services.assignment_note_service import AssignmentNoteService

router = APIRouter(prefix="/assignments", tags=["assignment-notes"])


def get_service(db: DBSession) -> AssignmentNoteService:
    return AssignmentNoteService(db)


ServiceDep = Annotated[AssignmentNoteService, Depends(get_service)]


@router.post(
    "/{assignment_id}/notes",
    response_model=AssignmentNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an agent note to an assignment",
)
async def create_note(
    assignment_id: int,
    data: AssignmentNoteCreate,
    service: ServiceDep,
) -> AssignmentNoteRead:
    note = await service.create_note(
        assignment_id=assignment_id,
        content=data.content,
        agent_type=data.agent_type,
        created_by_agent=True,
    )
    return AssignmentNoteRead.model_validate(note)


@router.get(
    "/{assignment_id}/notes",
    response_model=list[AssignmentNoteRead],
    summary="Get all agent notes for an assignment",
)
async def get_notes(
    assignment_id: int,
    service: ServiceDep,
) -> list[AssignmentNoteRead]:
    notes = await service.get_notes(assignment_id)
    return [AssignmentNoteRead.model_validate(n) for n in notes]
