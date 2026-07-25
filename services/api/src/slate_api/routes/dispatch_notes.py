"""Dispatch notes routes — used by the field_guide AI agent."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from ..core import DBSession
from ..schemas.dispatch_note import DispatchNoteCreate, DispatchNoteRead
from ..services.dispatch_note_service import DispatchNoteService

router = APIRouter(prefix="/assignments", tags=["assignment-notes"])


def get_service(db: DBSession) -> DispatchNoteService:
    return DispatchNoteService(db)


ServiceDep = Annotated[DispatchNoteService, Depends(get_service)]


@router.post(
    "/{dispatch_id}/notes",
    response_model=DispatchNoteRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an agent note to a dispatch",
)
async def create_note(
    dispatch_id: int,
    data: DispatchNoteCreate,
    service: ServiceDep,
) -> DispatchNoteRead:
    note = await service.create_note(
        dispatch_id=dispatch_id,
        content=data.content,
        agent_type=data.agent_type,
        created_by_agent=True,
    )
    return DispatchNoteRead.model_validate(note)


@router.get(
    "/{dispatch_id}/notes",
    response_model=list[DispatchNoteRead],
    summary="Get all agent notes for a dispatch",
)
async def get_notes(dispatch_id: int, service: ServiceDep) -> list[DispatchNoteRead]:
    notes = await service.get_notes(dispatch_id)
    return [DispatchNoteRead.model_validate(n) for n in notes]
