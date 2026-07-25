"""Schema for dispatch metrics endpoint."""

from pydantic import BaseModel


class DispatchMetrics(BaseModel):
    total_active: int
    by_status: dict[str, int]

    avg_resolution_seconds: float | None
    median_resolution_seconds: float | None

    window_hours: int
    completed_in_window: int
    created_in_window: int
