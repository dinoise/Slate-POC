"""Pydantic schemas for DemandPrediction model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DemandPredictionRead(BaseModel):
    """Schema for reading a DemandPrediction (read-only — written by ML pipeline)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    h3_r8: str
    hora_num: int
    dia_semana_num: int
    pred_ratio: float
    pred_abs: float
    demand_level: int = Field(..., ge=0, le=2)  # 0=Low 1=Med 2=High
    lat: float
    lon: float
    model_version: str
    predicted_for: datetime
    created_at: datetime
