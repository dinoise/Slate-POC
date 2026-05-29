"""Pydantic schemas for Dispatch model."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..core.enums import DispatchStatus

TrafficSpeed = Literal["NORMAL", "SLOW", "TRAFFIC_JAM"]


class TrafficSegment(BaseModel):
    start_index: int = Field(..., ge=0)
    end_index: int = Field(..., ge=0)
    speed: TrafficSpeed


class DispatchBase(BaseModel):
    task_id: int = Field(..., gt=0)
    resource_id: int = Field(..., gt=0)
    notes: str | None = None


class DispatchCreate(DispatchBase):
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DispatchUpdate(BaseModel):
    estimated_arrival_time: datetime | None = None
    actual_arrival_time: datetime | None = None
    completed_at: datetime | None = None
    status: DispatchStatus | None = None
    notes: str | None = None


class DispatchRead(DispatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assigned_at: datetime
    estimated_arrival_time: datetime | None
    actual_arrival_time: datetime | None
    completed_at: datetime | None
    distance_km: float | None
    travel_time_minutes: int | None
    optimization_score: float | None
    status: DispatchStatus
    route_polyline: str | None = None
    route_provider: str | None = None
    route_fetched_at: datetime | None = None
    route_distance_m: int | None = None
    route_duration_s: int | None = None
    route_traffic_segments: list[TrafficSegment] | None = None
    created_at: datetime
    updated_at: datetime


class DispatchStatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dispatch_id: int
    from_status: DispatchStatus | None
    to_status: DispatchStatus
    changed_at: datetime
    changed_by: str | None


# ── Optimize endpoint schemas ─────────────────────────────────────────────────


class TaskCoord(BaseModel):
    task_id: int = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ResourceCoord(BaseModel):
    resource_id: int = Field(..., gt=0)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class OptimizeRequest(BaseModel):
    tasks: list[TaskCoord] = Field(default_factory=list)
    resources: list[ResourceCoord] = Field(default_factory=list)
    use_db: bool = Field(False)
    radius_km: float = Field(30.0, ge=1.0, le=200.0)
    persist: bool = Field(True)
    max_travel_min: float = Field(90.0, gt=0)
    top_k: int = Field(1, ge=1, le=20)

    @model_validator(mode="after")
    def validate_inputs(self) -> "OptimizeRequest":
        if not self.use_db and (not self.tasks or not self.resources):
            raise ValueError("Provide non-empty 'tasks' and 'resources', or set use_db=True.")
        return self


class OptimizedDispatch(BaseModel):
    resource_id: int
    task_id: int
    travel_time_s: float
    travel_time_min: float
    dispatch_id: int | None = Field(None)


class CandidateResult(BaseModel):
    task_id: int
    resource_id: int
    travel_time_s: float
    travel_time_min: float
    rank: int = Field(..., ge=1)


class RouteResponse(BaseModel):
    origin_lat: float
    origin_lon: float
    destination_lat: float
    destination_lon: float
    duration_s: float
    distance_m: float
    polyline: str
    provider: str
    traffic_segments: list[TrafficSegment] = Field(default_factory=list)


class OptimizeResponse(BaseModel):
    dispatches: list[OptimizedDispatch]
    candidates: list[CandidateResult] = Field(default_factory=list)
    unassigned_task_ids: list[int]
    solver: str = "ortools_linear_sum_assignment"
    total_travel_min: float
    median_travel_min: float
    p90_travel_min: float
    solver_time_s: float
    n_tasks: int
    n_resources: int
    routing_provider: str = Field("")
    traffic_aware: bool = Field(False)
