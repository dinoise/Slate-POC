"""AssignmentNote model — agent-generated field notes on an assignment."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .assignment import Assignment


class AssignmentNote(BaseModel):
    """A note written by an AI agent (or future human) on an assignment."""

    __tablename__ = "assignment_notes"
    __table_args__ = (Index("idx_assignment_notes_assignment_id", "assignment_id"),)

    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # True when written by an AI agent; False when written by a human (future)
    created_by_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Which agent sub-type authored the note (e.g. "field_guide", "coordinator")
    agent_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    assignment: Mapped["Assignment"] = relationship(
        "Assignment",
        back_populates="agent_notes",
    )

    def __repr__(self) -> str:
        return (
            f"AssignmentNote(id={self.id}, "
            f"assignment_id={self.assignment_id}, "
            f"agent_type={self.agent_type!r})"
        )
