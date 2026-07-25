"""Public schemas for the notifications service SSE contract.

These Pydantic models define the shape of data delivered to SSE clients
*after* DB enrichment. They are the public HTTP contract — any change
here is a breaking change for frontend consumers.

The internal pg_notify payload (before enrichment) is represented by
``domain.events.NotificationPayload``, which is not exposed publicly.

v1 schema uses a nested envelope:
    {
      assignment_id, status, event_type, assigned_at,
      distance_km, travel_time_minutes,
      incident: { id, type, severity, description, address, latitude, longitude },
      adjuster: { id, latitude, longitude } | null,
      route:    { polyline, provider, distance_m, duration_s, traffic_segments } | null,
    }
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class IncidentInfo(BaseModel):
    """Incident fields nested inside the SSE envelope."""

    id: int
    type: str
    severity: int
    description: str | None = None
    address: str | None = None
    latitude: float
    longitude: float


class AdjusterInfo(BaseModel):
    """Adjuster home position nested inside the SSE envelope.

    Uses ``adjusters.home_latitude/longitude`` — always non-null in the DB.
    Absent (null) only when DB enrichment falls back to the raw payload.
    """

    id: int
    latitude: float
    longitude: float


class RouteInfo(BaseModel):
    """Route data nested inside the SSE envelope.

    Null until the route-fetching background job has run.
    """

    polyline: str | None = None
    provider: str | None = None
    distance_m: int | None = None
    duration_s: int | None = None
    traffic_segments: list[dict] | None = None


class EnrichedAssignmentEvent(BaseModel):
    """SSE event payload delivered to both adjuster and reporter clients.

    Produced by ``services.enricher.Enricher`` by joining the raw
    pg_notify payload with the assignment, incident, and adjuster rows.

    This schema is serialised to JSON and sent as the ``data:`` field
    of an SSE ``assignment`` event.

    Attributes:
        assignment_id: PK of the assignment that changed.
        status: Current assignment status after the change.
        event_type: ``'assignment.created'`` or ``'assignment.updated'``.
        assigned_at: ISO-8601 timestamp of initial assignment.
        distance_km: Straight-line distance estimate from the optimizer.
        travel_time_minutes: Travel-time estimate from the optimizer.
        incident: Incident metadata (type, severity, address, coords).
        adjuster: Adjuster home position — null on enrichment fallback.
        route: Route data — null until route-fetching job runs.
    """

    model_config = ConfigDict(populate_by_name=True)

    assignment_id: int
    status: str
    event_type: str = "assignment.updated"
    assigned_at: datetime | None = None
    distance_km: float | None = None
    travel_time_minutes: int | None = None

    incident: IncidentInfo
    adjuster: AdjusterInfo | None = None
    route: RouteInfo | None = None

    @field_serializer("assigned_at")
    def serialize_assigned_at(self, value: Any) -> str | None:
        """Ensure assigned_at is always a plain ISO-8601 string.

        The underlying value may arrive as a ``datetime`` object from
        SQLAlchemy or as a string from the pg_notify payload dict.
        Normalise to string so JSON serialisation is consistent.

        Args:
            value: Raw value from the model field.

        Returns:
            ISO-8601 string or ``None``.
        """
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
