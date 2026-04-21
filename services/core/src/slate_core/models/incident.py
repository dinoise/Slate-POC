"""Incident model for insurance claims."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .assignment import Assignment
    from .user import User


class Incident(BaseModel):
    """Model representing an insurance incident/claim."""

    __tablename__ = "incidents"
    __table_args__ = (Index("idx_incidents_location", "location", postgresql_using="gist"),)

    # Basic info
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Geospatial
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Temporal
    incident_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Reporter (user who filed the incident)
    reported_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )  # pending, assigned, in_progress, completed

    # Relationships
    reported_by_user: Mapped["User | None"] = relationship("User")
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="incident",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Incident(id={self.id}, "
            f"external_id={self.external_id!r}, "
            f"type={self.incident_type!r}, "
            f"status={self.status!r})"
        )
