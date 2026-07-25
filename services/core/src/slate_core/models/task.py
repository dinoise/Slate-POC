"""Task model — generic work order / incident / claim."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .dispatch import Dispatch
    from .user import User


class Task(BaseModel):
    """Model representing a work order (incident, claim, job, etc.)."""

    __tablename__ = "tasks"
    __table_args__ = (Index("idx_tasks_location", "location", postgresql_using="gist"),)

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    incident_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    incident_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    reported_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    reported_by_user: Mapped["User | None"] = relationship("User")
    dispatches: Mapped[list["Dispatch"]] = relationship(
        "Dispatch",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id}, "
            f"external_id={self.external_id!r}, "
            f"type={self.incident_type!r}, "
            f"status={self.status!r})"
        )
