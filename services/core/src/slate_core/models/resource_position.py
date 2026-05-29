"""ResourcePosition model — stores resource positions for demo scenarios."""

from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .resource import Resource


class ResourcePosition(BaseModel):
    """Stores resource positions for different positioning scenarios."""

    __tablename__ = "resource_positions"
    __table_args__ = (
        Index("idx_resource_positions_location", "location", postgresql_using="gist"),
        Index("idx_resource_positions_scenario", "scenario"),
        Index("idx_resource_positions_h3_r8", "h3_r8"),
        Index("idx_resource_positions_resource_id", "resource_id"),
    )

    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
    )

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    h3_r8: Mapped[str | None] = mapped_column(String(20), nullable=True)

    scenario: Mapped[str] = mapped_column(String(100), nullable=False, default="initial")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="dbscan_cluster")

    demand_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    hora_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dia_semana_num: Mapped[int | None] = mapped_column(Integer, nullable=True)

    resource: Mapped["Resource"] = relationship("Resource", back_populates="positions")

    def __repr__(self) -> str:
        return (
            f"ResourcePosition(id={self.id}, resource_id={self.resource_id}, "
            f"scenario={self.scenario!r}, lat={self.lat:.4f}, lon={self.lon:.4f})"
        )
