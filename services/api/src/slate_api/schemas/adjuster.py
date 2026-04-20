"""Pydantic schemas for Adjuster model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ..core.enums import AdjusterStatus


class AdjusterBase(BaseModel):
    """Base schema for Adjuster."""

    external_id: str = Field(..., min_length=1, max_length=100)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(None, max_length=20)
    home_latitude: float = Field(..., ge=-90, le=90)
    home_longitude: float = Field(..., ge=-180, le=180)
    skills: list[str] = Field(default_factory=list)
    max_cases_per_day: int = Field(default=5, ge=1, le=20)


class AdjusterCreate(AdjusterBase):
    """Schema for creating an Adjuster."""


class AdjusterUpdate(BaseModel):
    """Schema for updating an Adjuster."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)
    skills: list[str] | None = None
    max_cases_per_day: int | None = Field(None, ge=1, le=20)
    is_active: bool | None = None
    status: AdjusterStatus | None = None


class AdjusterRead(AdjusterBase):
    """Schema for reading an Adjuster."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    status: AdjusterStatus
    created_at: datetime
    updated_at: datetime
    current_latitude: float | None = Field(
        None,
        description="Current working position latitude from adjuster_positions. "
        "Populated by /available/ when a scenario is active. "
        "Falls back to home_latitude when None.",
    )
    current_longitude: float | None = Field(
        None,
        description="Current working position longitude from adjuster_positions.",
    )
