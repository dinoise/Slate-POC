"""Adjuster model for insurance adjusters."""
from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .adjuster_position import AdjusterPosition
    from .assignment import Assignment


class Adjuster(BaseModel):
    """Model representing an insurance adjuster."""

    __tablename__ = "adjusters"
    __table_args__ = (
        Index("idx_adjusters_home_location", "home_location", postgresql_using="gist"),
    )

    # Basic info
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Geospatial - home base location
    home_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    home_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    home_location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    # Skills and specializations
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        nullable=False,
        default=list,
    )
    max_cases_per_day: Mapped[int] = mapped_column(default=5, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default="available",
        nullable=False,
    )  # available, busy, offline

    # Relationships
    assignments: Mapped[list["Assignment"]] = relationship(
        "Assignment",
        back_populates="adjuster",
        cascade="all, delete-orphan",
    )
    positions: Mapped[list["AdjusterPosition"]] = relationship(
        "AdjusterPosition",
        back_populates="adjuster",
        cascade="all, delete-orphan",
        order_by="AdjusterPosition.created_at.desc()",
    )

    @property
    def full_name(self) -> str:
        """Get full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"Adjuster(id={self.id}, "
            f"external_id={self.external_id!r}, "
            f"name={self.full_name!r}, "
            f"status={self.status!r})"
        )
