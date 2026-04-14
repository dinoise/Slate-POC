"""User model for incident reporters (insured clients)."""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class User(BaseModel):
    """Model representing an insured client who reports incidents."""

    __tablename__ = "users"

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"User(id={self.id}, "
            f"external_id={self.external_id!r}, "
            f"name={self.full_name!r}, "
            f"email={self.email!r})"
        )
