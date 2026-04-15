"""Schemas for AdjusterPosition."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdjusterPositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    adjuster_id: int
    lat: float
    lon: float
    h3_r8: str | None
    scenario: str
    source: str
    demand_score: float | None
    gap_index: float | None
    cluster_id: int | None
    hora_num: int | None
    dia_semana_num: int | None
    created_at: datetime
    updated_at: datetime

    # Denormalized from adjuster for convenience
    adjuster_name: str | None = None
