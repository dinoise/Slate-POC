"""DemandPrediction model — cached ML model output per H3 hexagon and time slot."""

from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Float, Index, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class DemandPrediction(Base):
    """Cached demand forecast per H3-R8 hexagon and hour slot."""

    __tablename__ = "demand_predictions"
    __table_args__ = (
        UniqueConstraint("h3_r8", "predicted_for", name="uq_demand_h3_slot"),
        Index(
            "idx_demand_predictions_location",
            "location",
            postgresql_using="gist",
        ),
        Index(
            "idx_demand_predictions_slot",
            "predicted_for",
            text("pred_abs DESC"),
        ),
        Index("idx_demand_predictions_h3", "h3_r8"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # H3 cell identifier (resolution 8)
    h3_r8: Mapped[str] = mapped_column(String(16), nullable=False)

    # Time slot features (mirror model input)
    hora_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dia_semana_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # Model output
    pred_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    pred_abs: Mapped[float] = mapped_column(Float, nullable=False)
    demand_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 0=Low 1=Med 2=High

    # Hex centroid (denormalized for fast non-spatial queries)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    # PostGIS point for ST_Within bbox queries
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    # Provenance
    model_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1.0.0")
    predicted_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"DemandPrediction(h3={self.h3_r8!r}, "
            f"slot={self.predicted_for!r}, "
            f"pred_abs={self.pred_abs:.2f})"
        )
