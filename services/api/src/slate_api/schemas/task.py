"""Pydantic schemas for Task model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from ..core.enums import TaskStatus


class TaskBase(BaseModel):
    external_id: str = Field(..., min_length=1, max_length=100)
    incident_type: str = Field(..., min_length=1, max_length=50)
    severity: int = Field(..., ge=1, le=5, description="Severity from 1 (low) to 5 (high)")
    description: str | None = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = Field(None, max_length=255)
    incident_datetime: datetime
    reported_by_user_id: int | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    incident_type: str | None = Field(None, min_length=1, max_length=50)
    severity: int | None = Field(None, ge=1, le=5)
    description: str | None = None
    status: TaskStatus | None = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
