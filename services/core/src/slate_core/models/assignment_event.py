"""AssignmentEvent — outbox table for reliable SSE delivery."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .assignment import Assignment


class AssignmentEvent(Base):
    """Outbox record written atomically by the DB trigger on every assignment change.

    The notifications service polls ``processed_at IS NULL`` events, broadcasts
    them via SSE, then marks them processed — guaranteeing delivery even if
    ``pg_notify`` was missed during a reconnect.
    """

    __tablename__ = "assignment_events"
    __table_args__ = (Index("ix_ae_adjuster", "adjuster_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    adjuster_id: Mapped[int] = mapped_column(nullable=False)
    incident_id: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    new_status: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    assignment: Mapped["Assignment"] = relationship(
        "Assignment",
        back_populates="events",
    )

    def __repr__(self) -> str:
        return (
            f"AssignmentEvent(id={self.id}, "
            f"assignment_id={self.assignment_id}, "
            f"event_type={self.event_type!r}, "
            f"processed={'yes' if self.processed_at else 'no'})"
        )
