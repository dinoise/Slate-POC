"""Pydantic schemas for AssignmentNote."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssignmentNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    agent_type: str | None = None


class AssignmentNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    content: str
    created_by_agent: bool
    agent_type: str | None
    created_at: datetime
