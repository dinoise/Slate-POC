"""Internal event types for the notification pipeline.

These are the raw payloads that travel from the PostgreSQL trigger
through pg_notify and the broadcaster queues, before enrichment.
They are internal domain objects — not part of the public HTTP contract.

The public SSE payload (after DB enrichment) is defined in
``schemas/notification.py`` as ``EnrichedAssignmentEvent``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class NotificationPayload:
    """Raw dispatch payload as emitted by the PostgreSQL trigger.

    Fields mirror the ``jsonb_build_object(...)`` call inside
    ``handle_dispatch_change()`` in the DB trigger.
    """

    dispatch_id: int
    resource_id: int
    task_id: int
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
        """Parse a pg_notify JSON payload dict into a typed object."""
        return cls(
            dispatch_id=int(data["dispatch_id"]),
            resource_id=int(data["resource_id"]),
            task_id=int(data["task_id"]),
            status=data["status"],
            event_type=data.get("event", "dispatch.updated"),
            distance_km=data.get("distance_km"),
            travel_time_minutes=data.get("travel_time_minutes"),
            assigned_at=data.get("assigned_at"),
            route_polyline=data.get("route_polyline"),
            route_distance_m=data.get("route_distance_m"),
            route_duration_s=data.get("route_duration_s"),
            raw=data,
        )
