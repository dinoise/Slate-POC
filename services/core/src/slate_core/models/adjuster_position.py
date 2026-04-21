"""AdjusterPosition model — stores adjuster positions for demo scenarios."""

from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import BaseModel

if TYPE_CHECKING:
    from .adjuster import Adjuster


class AdjusterPosition(BaseModel):
    """Stores adjuster positions for different positioning scenarios.

    Each row is one adjuster in one scenario snapshot.
    scenario examples: 'initial', 'optimized_tue_14h', 'optimized_wed_09h'
    source: 'dbscan_cluster' | 'greedy_optimizer'
    """

    __tablename__ = "adjuster_positions"
    __table_args__ = (
        Index("idx_adjuster_positions_location", "location", postgresql_using="gist"),
        Index("idx_adjuster_positions_scenario", "scenario"),
        Index("idx_adjuster_positions_h3_r8", "h3_r8"),
        Index("idx_adjuster_positions_adjuster_id", "adjuster_id"),
    )

    # FK to adjusters — always required
    adjuster_id: Mapped[int] = mapped_column(
        ForeignKey("adjusters.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Geospatial
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )
    h3_r8: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Scenario metadata
    scenario: Mapped[str] = mapped_column(
        String(100), nullable=False, default="initial"
    )  # 'initial' | 'optimized_tue_14h' | ...
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="dbscan_cluster"
    )  # 'dbscan_cluster' | 'greedy_optimizer'

    # Optional positioning context
    demand_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Slot for which this position was optimized (null = initial state)
    hora_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dia_semana_num: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationship back to adjuster
    adjuster: Mapped["Adjuster"] = relationship("Adjuster", back_populates="positions")

    def __repr__(self) -> str:
        return (
            f"AdjusterPosition(id={self.id}, adjuster_id={self.adjuster_id}, "
            f"scenario={self.scenario!r}, lat={self.lat:.4f}, lon={self.lon:.4f})"
        )
