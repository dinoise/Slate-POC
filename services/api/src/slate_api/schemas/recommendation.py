"""Schemas for positioning recommendations."""
from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    scenario: str = Field(default="initial", description="Source scenario for adjuster positions")
    hora_num: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    dia_semana_num: int = Field(..., ge=0, le=6, description="Day of week (0=Mon, 6=Sun)")
    radio_km: float = Field(default=7.5, gt=0, le=100, description="Max relocation radius in km")
    umbral_gain: float = Field(default=0.5, ge=0, description="Min demand gain to trigger move")
    spread_factor: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Dispersion factor (0=pure demand-greedy, 1=maximum spread). "
            "Penalises candidates near already-reserved hexagons following "
            "a p-median-inspired objective: score = pred_abs - spread_factor "
            "* Σ pred_abs(neighbour) for neighbours within k_rings H3 rings."
        ),
    )
    spread_rings: int = Field(
        default=3,
        ge=1,
        le=8,
        description="H3 ring radius used for neighbour penalty (k_rings × ~1.2 km at R8).",
    )
    save_as_scenario: str | None = Field(
        default=None,
        description="If set, persist recommended positions as a new scenario with this name",
    )


class RecommendationItem(BaseModel):
    adjuster_id: int
    adjuster_name: str
    current_hex: str | None
    recommended_hex: str
    recommended_lat: float
    recommended_lon: float
    demand_gain: float
    distance_km: float
    eta_min: float
    reason: str


class RecommendationResponse(BaseModel):
    scenario_source: str
    hora_num: int
    dia_semana_num: int
    total_adjusters: int
    adjusters_to_move: int
    recommendations: list[RecommendationItem]
    saved_as: str | None = None
