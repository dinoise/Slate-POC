"""Pydantic schemas for User model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base schema for User."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(None, max_length=20)


class UserCreate(UserBase):
    """Schema for creating a User. external_id is generated server-side."""

    pass


class UserUpdate(BaseModel):
    """Schema for partially updating a User."""

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=20)


class UserRead(UserBase):
    """Schema for reading a User."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str
    created_at: datetime
    updated_at: datetime
