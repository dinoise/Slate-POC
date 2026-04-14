"""Assignment model for incident-adjuster assignments."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .adjuster import Adjuster
    from .incident import Incident


class Assignment(BaseModel):
    """Model representing an assignment of an adjuster to an incident."""

    __tablename__ = "assignments"

    # Foreign Keys
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    adjuster_id: Mapped[int] = mapped_column(
        ForeignKey("adjusters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Assignment details
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    estimated_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    actual_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Optimization metrics
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimization_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="assigned",
        nullable=False,
    )  # assigned, accepted, en_route, arrived, in_progress, completed, cancelled

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    incident: Mapped["Incident"] = relationship(
        "Incident",
        back_populates="assignments",
    )
    adjuster: Mapped["Adjuster"] = relationship(
        "Adjuster",
        back_populates="assignments",
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Assignment(id={self.id}, "
            f"incident_id={self.incident_id}, "
            f"adjuster_id={self.adjuster_id}, "
            f"status={self.status!r})"
        )
