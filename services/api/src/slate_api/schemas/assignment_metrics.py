"""Schema for assignment metrics endpoint."""

from pydantic import BaseModel


class AssignmentMetrics(BaseModel):
    # Counts by status
    total_active: int
    by_status: dict[str, int]

    # Resolution time stats (seconds) — None when no completed assignments in window
    avg_resolution_seconds: float | None
    median_resolution_seconds: float | None

    # Volume over the requested window
    window_hours: int
    completed_in_window: int
    created_in_window: int
