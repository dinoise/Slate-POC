"""AssignmentStatusHistory — immutable audit trail of assignment status transitions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .assignment import Assignment


class AssignmentStatusHistory(Base):
    """Immutable record of every status transition for an assignment.

    Written exclusively by the DB trigger ``handle_assignment_change`` —
    never directly from application code.
    """

    __tablename__ = "assignment_status_history"
    __table_args__ = (
        Index("ix_ash_assignment_id", "assignment_id"),
        Index("ix_ash_changed_at", "changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    changed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    assignment: Mapped["Assignment"] = relationship(
        "Assignment",
        back_populates="status_history",
    )

    def __repr__(self) -> str:
        return (
            f"AssignmentStatusHistory(id={self.id}, "
            f"assignment_id={self.assignment_id}, "
            f"{self.from_status!r} → {self.to_status!r})"
        )
