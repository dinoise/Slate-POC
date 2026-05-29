"""DispatchStatusHistory — immutable audit trail of dispatch status transitions."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

if TYPE_CHECKING:
    from .dispatch import Dispatch


class DispatchStatusHistory(Base):
    """Immutable record of every status transition for a dispatch.

    Written exclusively by the DB trigger ``handle_dispatch_change``.
    """

    __tablename__ = "dispatch_status_history"
    __table_args__ = (
        Index("ix_dsh_dispatch_id", "dispatch_id"),
        Index("ix_dsh_changed_at", "changed_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dispatch_id: Mapped[int] = mapped_column(
        ForeignKey("dispatches.id", ondelete="CASCADE"),
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

    dispatch: Mapped["Dispatch"] = relationship("Dispatch", back_populates="status_history")

    def __repr__(self) -> str:
        return (
            f"DispatchStatusHistory(id={self.id}, "
            f"dispatch_id={self.dispatch_id}, "
            f"{self.from_status!r} → {self.to_status!r})"
        )
