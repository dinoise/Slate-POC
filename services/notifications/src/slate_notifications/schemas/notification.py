"""Public schemas for the notifications service SSE contract.

These Pydantic models define the shape of data delivered to SSE clients
*after* DB enrichment. They are the public HTTP contract — any change
here is a breaking change for frontend consumers.

The internal pg_notify payload (before enrichment) is represented by
``domain.events.NotificationPayload``, which is not exposed publicly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer


class EnrichedAssignmentEvent(BaseModel):
    """SSE event payload delivered to both adjuster and reporter clients.

    Produced by ``services.enricher.Enricher`` by joining the raw
    pg_notify payload with the assignment and incident rows in the DB.

    This schema is serialised to JSON and sent as the ``data:`` field
    of an SSE ``assignment`` event.

    Attributes:
        assignment_id: PK of the assignment that changed.
        adjuster_id: Adjuster assigned to this incident.
        incident_id: Incident being handled.
        status: Current assignment status after the change.
        event_type: ``'assignment.created'`` or ``'assignment.updated'``.
        distance_km: Straight-line distance estimate from the optimizer.
        travel_time_minutes: Travel-time estimate from the optimizer.
        assigned_at: ISO-8601 timestamp of initial assignment.
        route_polyline: Encoded polyline from the routing provider, if available.
        route_provider: Name of routing provider (e.g. ``'osrm'``, ``'google'``).
        route_distance_m: Route distance in metres from routing provider.
        route_duration_s: Route duration in seconds from routing provider.
        incident_type: Type code of the incident (e.g. ``'collision'``).
        severity: Incident severity level (1–5).
        description: Free-text incident description, may be None.
        address: Human-readable address of the incident location.
        latitude: WGS-84 latitude of the incident.
        longitude: WGS-84 longitude of the incident.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Assignment fields
    assignment_id: int
    adjuster_id: int
    incident_id: int
    status: str
    event_type: str = "assignment.updated"
    distance_km: float | None = None
    travel_time_minutes: int | None = None
    assigned_at: datetime | None = None

    # Route fields — populated once the route-fetch job has run
    route_polyline: str | None = None
    route_provider: str | None = None
    route_distance_m: int | None = None
    route_duration_s: int | None = None

    # Incident fields — joined from the incidents table
    incident_type: str
    severity: int
    description: str | None = None
    address: str | None = None
    latitude: float
    longitude: float

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
