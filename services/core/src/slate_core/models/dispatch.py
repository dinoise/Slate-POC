"""Dispatch model — assignment of a resource to a task."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .dispatch_event import DispatchEvent
    from .dispatch_note import DispatchNote
    from .dispatch_status_history import DispatchStatusHistory
    from .resource import Resource
    from .task import Task


class Dispatch(BaseModel):
    """Model representing a dispatch of a resource to a task."""

    __tablename__ = "dispatches"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_arrival_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    travel_time_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    optimization_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    route_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    route_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    route_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    route_distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route_duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route_traffic_segments: Mapped[list | None] = mapped_column(JSON, nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="dispatches")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="dispatches")
    status_history: Mapped[list["DispatchStatusHistory"]] = relationship(
        "DispatchStatusHistory",
        back_populates="dispatch",
        order_by="DispatchStatusHistory.changed_at",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["DispatchEvent"]] = relationship(
        "DispatchEvent",
        back_populates="dispatch",
        order_by="DispatchEvent.created_at",
        cascade="all, delete-orphan",
    )
    agent_notes: Mapped[list["DispatchNote"]] = relationship(
        "DispatchNote",
        back_populates="dispatch",
        order_by="DispatchNote.created_at",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"Dispatch(id={self.id}, "
            f"task_id={self.task_id}, "
            f"resource_id={self.resource_id}, "
            f"status={self.status!r})"
        )
