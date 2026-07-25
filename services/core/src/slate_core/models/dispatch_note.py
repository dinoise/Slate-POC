"""DispatchNote model — agent-generated field notes on a dispatch."""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .dispatch import Dispatch


class DispatchNote(BaseModel):
    """A note written by an AI agent (or human) on a dispatch."""

    __tablename__ = "dispatch_notes"
    __table_args__ = (Index("idx_dispatch_notes_dispatch_id", "dispatch_id"),)

    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("dispatches.id", ondelete="CASCADE"),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_agent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    agent_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    dispatch: Mapped["Dispatch"] = relationship("Dispatch", back_populates="agent_notes")

    def __repr__(self) -> str:
        return (
            f"DispatchNote(id={self.id}, "
            f"dispatch_id={self.dispatch_id}, "
            f"agent_type={self.agent_type!r})"
        )
