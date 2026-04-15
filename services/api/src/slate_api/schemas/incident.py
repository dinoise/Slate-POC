"""Pydantic schemas for Incident model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class IncidentBase(BaseModel):
    """Base schema for Incident."""

    external_id: str = Field(..., min_length=1, max_length=100)
    incident_type: str = Field(..., min_length=1, max_length=50)
    severity: int = Field(..., ge=1, le=5, description="Severity from 1 (low) to 5 (high)")
    description: str | None = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    address: str | None = Field(None, max_length=255)
    incident_datetime: datetime
    reported_by_user_id: int | None = None


class IncidentCreate(IncidentBase):
    """Schema for creating an Incident."""

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_coordinates(cls, v: float, info: Any) -> float:
        """Validate that coordinates are valid."""
        field_name = info.field_name
        if field_name == "latitude" and not -90 <= v <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        if field_name == "longitude" and not -180 <= v <= 180:
            raise ValueError("Longitude must be between -180 and 180")
        return v


class IncidentUpdate(BaseModel):
    """Schema for updating an Incident."""

    incident_type: str | None = Field(None, min_length=1, max_length=50)
    severity: int | None = Field(None, ge=1, le=5)
    description: str | None = None
    status: str | None = Field(None, pattern="^(pending|assigned|in_progress|completed|cancelled)$")


class IncidentRead(IncidentBase):
    """Schema for reading an Incident."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    created_at: datetime
    updated_at: datetime
