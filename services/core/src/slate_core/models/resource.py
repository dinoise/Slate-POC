"""Resource model — generic field agent / adjuster / technician."""

from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, Index, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .dispatch import Dispatch
    from .resource_position import ResourcePosition


class Resource(BaseModel):
    """Model representing a dispatchable field resource."""

    __tablename__ = "resources"
    __table_args__ = (
        Index("idx_resources_home_location", "home_location", postgresql_using="gist"),
    )

    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    home_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    home_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    home_location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    max_cases_per_day: Mapped[int] = mapped_column(default=5, nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)

    dispatches: Mapped[list["Dispatch"]] = relationship(
        "Dispatch",
        back_populates="resource",
        cascade="all, delete-orphan",
    )
    positions: Mapped[list["ResourcePosition"]] = relationship(
        "ResourcePosition",
        back_populates="resource",
        cascade="all, delete-orphan",
        order_by="ResourcePosition.created_at.desc()",
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return (
            f"Resource(id={self.id}, "
            f"external_id={self.external_id!r}, "
            f"name={self.full_name!r}, "
            f"status={self.status!r})"
        )
