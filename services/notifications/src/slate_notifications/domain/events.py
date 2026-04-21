"""Internal event types for the notification pipeline.

These are the raw payloads that travel from the PostgreSQL trigger
through pg_notify and the broadcaster queues, *before* enrichment.
They are internal domain objects — not part of the public HTTP contract.

The public SSE payload (after DB enrichment) is defined in
``schemas/notification.py`` as ``EnrichedAssignmentEvent``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NotificationPayload:
    """Raw assignment payload as emitted by the PostgreSQL trigger.

    Fields mirror the ``jsonb_build_object(...)`` call inside
    ``handle_assignment_change()`` in the DB trigger. The payload is
    intentionally minimal (no incident join) — enrichment happens later
    in ``services/enricher.py``.

    Attributes:
        assignment_id: PK of the changed assignment row.
        adjuster_id: FK — used to route to adjuster SSE queues.
        incident_id: FK — used to route to incident SSE queues.
        status: New assignment status after the change.
        event_type: ``'assignment.created'`` or ``'assignment.updated'``.
        distance_km: Optimizer estimate, may be None before optimization runs.
        travel_time_minutes: Optimizer estimate, may be None.
        assigned_at: ISO-8601 string as stored in the DB.
        route_polyline: Encoded polyline, populated by the route-fetch job.
        route_distance_m: Route distance in metres from routing provider.
        route_duration_s: Route duration in seconds from routing provider.
        raw: Original dict from pg_notify — preserved for fallback/logging.
    """

    assignment_id: int
    adjuster_id: int
    incident_id: int
    status: str
    event_type: str
    distance_km: float | None = None
    travel_time_minutes: int | None = None
    assigned_at: str | None = None
    route_polyline: str | None = None
    route_distance_m: int | None = None
    route_duration_s: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NotificationPayload:
        """Parse a pg_notify JSON payload dict into a typed object.

        Unknown keys are ignored; the full original dict is stored in ``raw``
        for debugging purposes.

        Args:
            data: Parsed JSON dict from the pg_notify payload string.

        Returns:
            A typed ``NotificationPayload`` instance.

        Raises:
            KeyError: If any required field (assignment_id, adjuster_id,
                incident_id, status) is missing from ``data``.
        """
        return cls(
            assignment_id=int(data["assignment_id"]),
            adjuster_id=int(data["adjuster_id"]),
            incident_id=int(data["incident_id"]),
            status=data["status"],
            event_type=data.get("event", "assignment.updated"),
            distance_km=data.get("distance_km"),
            travel_time_minutes=data.get("travel_time_minutes"),
            assigned_at=data.get("assigned_at"),
            route_polyline=data.get("route_polyline"),
            route_distance_m=data.get("route_distance_m"),
            route_duration_s=data.get("route_duration_s"),
            raw=data,
        )
