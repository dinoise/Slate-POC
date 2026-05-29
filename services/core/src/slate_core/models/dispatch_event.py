"""DispatchEvent — outbox table for reliable SSE delivery."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .dispatch import Dispatch


class DispatchEvent(Base):
    """Outbox record written atomically by the DB trigger on every dispatch change.

    The notifications service polls ``processed_at IS NULL`` events, broadcasts
    them via SSE, then marks them processed.
    """

    __tablename__ = "dispatch_events"
    __table_args__ = (Index("ix_de_resource", "resource_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("dispatches.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[int] = mapped_column(nullable=False)
    task_id: Mapped[int] = mapped_column(nullable=False)
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

    dispatch: Mapped["Dispatch"] = relationship("Dispatch", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"DispatchEvent(id={self.id}, "
            f"dispatch_id={self.dispatch_id}, "
            f"event_type={self.event_type!r}, "
            f"processed={'yes' if self.processed_at else 'no'})"
        )
