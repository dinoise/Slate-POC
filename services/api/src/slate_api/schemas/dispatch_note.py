"""Pydantic schemas for DispatchNote."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DispatchNoteCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)
    agent_type: str | None = None


class DispatchNoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispatch_id: int
    content: str
    created_by_agent: bool
    agent_type: str | None
    created_at: datetime
