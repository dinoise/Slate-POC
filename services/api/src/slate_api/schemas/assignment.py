"""Pydantic schemas for Assignment model."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrafficSpeed = Literal["NORMAL", "SLOW", "TRAFFIC_JAM"]


class TrafficSegment(BaseModel):
    """One traffic-coloured segment mapped onto a decoded route polyline."""

    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., ge=0)
    speed: TrafficSpeed


class AssignmentBase(BaseModel):
    """Base schema for Assignment."""

    incident_id: int = Field(..., gt=0)
    adjuster_id: int = Field(..., gt=0)
    notes: str | None = None


class AssignmentCreate(AssignmentBase):
    """Schema for creating an Assignment."""

    assigned_at: datetime = Field(default_factory=datetime.now)


class AssignmentUpdate(BaseModel):
    """Schema for updating an Assignment."""

    estimated_arrival_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    completed_at: datetime | None = None
    status: str | None = Field(
        None,
        pattern="^(assigned|accepted|en_route|arrived|in_progress|completed|cancelled)$",
    )
    notes: str | None = None


class AssignmentRead(AssignmentBase):
    """Schema for reading an Assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    assigned_at: datetime
    estimated_arrival_time: datetime | None
    actual_arrival_time: datetime | None
    completed_at: datetime | None
    distance_km: float | None
    travel_time_minutes: int | None
    optimization_score: float | None
    status: str
    created_at: datetime
    updated_at: datetime


# ── Optimize endpoint schemas ────────────────────────────────────────────────


class IncidentCoord(BaseModel):
    """Incident location for optimization input."""

    incident_id: int = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AdjusterCoord(BaseModel):
    """Adjuster location for optimization input."""

    adjuster_id: int = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class OptimizeRequest(BaseModel):
    """
    Request body for POST /assignments/optimize.

    Provide explicit incident and adjuster lists, or let the service
    query the DB for pending incidents and available adjusters by setting
    use_db=True (incidents and adjusters fields are ignored in that case).
    """

    incidents: list[IncidentCoord] = Field(
        default_factory=list,
        description="Incidents to assign. Required when use_db=False.",
    )
    adjusters: list[AdjusterCoord] = Field(
        default_factory=list,
        description="Available adjusters. Required when use_db=False.",
    )
    use_db: bool = Field(
        False,
        description="Query DB for pending incidents and available adjusters.",
    )
    radius_km: float = Field(
        30.0,
        ge=1.0,
        le=200.0,
        description="Search radius in km used to filter candidate adjusters.",
    )
    persist: bool = Field(
        True,
        description="Persist resulting assignments to the database.",
    )
    max_travel_min: float = Field(
        90.0,
        gt=0,
        description=(
            "Maximum acceptable travel time in minutes. "
            "Adjuster-incident pairs exceeding this limit are treated as "
            "unreachable (set to np.inf) before solving."
        ),
    )
    top_k: int = Field(
        1,
        ge=1,
        le=20,
        description=(
            "Number of candidate adjusters to return per incident, sorted by travel time. "
            "Only the optimal assignment (rank 1) is persisted. "
            "Candidates 2..K are included in the response for comparison only."
        ),
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "OptimizeRequest":
        if not self.use_db and (not self.incidents or not self.adjusters):
            raise ValueError("Provide non-empty 'incidents' and 'adjusters', or set use_db=True.")
        return self


class OptimizedAssignment(BaseModel):
    """Single assignment produced by the solver."""

    adjuster_id: int
    incident_id: int
    travel_time_s: float
    travel_time_min: float
    assignment_id: int | None = Field(None, description="DB assignment ID (set when persist=True).")


class CandidateResult(BaseModel):
    """One entry in the top-K candidate list for a given incident."""

    incident_id: int
    adjuster_id: int
    travel_time_s: float
    travel_time_min: float
    rank: int = Field(..., ge=1, description="1 = optimal (same as the persisted assignment).")


class RouteResponse(BaseModel):
    """Response body for GET /assignments/route."""

    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    duration_s: float
    distance_m: float
    polyline: str = Field(..., description="Precision-5 encoded polyline of the full route.")
    provider: str
    traffic_segments: list[TrafficSegment] = Field(
        default_factory=list,
        description=(
            "Per-segment traffic conditions indexed into the decoded polyline. "
            "Empty when the active provider does not support traffic data."
        ),
    )


class OptimizeResponse(BaseModel):
    """Response body for POST /assignments/optimize."""

    assignments: list[OptimizedAssignment]
    candidates: list[CandidateResult] = Field(
        default_factory=list,
        description=(
            "Top-K candidates per incident sorted by travel time. "
            "Populated only when top_k > 1. Rank-1 entries duplicate the optimal assignment."
        ),
    )
    unassigned_incident_ids: list[int]
    solver: str = "ortools_linear_sum_assignment"
    total_travel_min: float
    median_travel_min: float
    p90_travel_min: float
    solver_time_s: float
    n_incidents: int
    n_adjusters: int
    routing_provider: str = Field("", description="Provider used to compute travel times.")
    traffic_aware: bool = Field(False, description="True if travel times account for traffic.")
