"""Payload enricher — hydrates raw pg_notify payloads with DB data.

Responsibilities (single):
    Given a raw payload dict from the broadcaster queue, query the DB
    to join assignment and incident data, and return a typed
    ``EnrichedAssignmentEvent`` schema ready for JSON serialisation.

Why enrichment happens here (not in the trigger):
    The PostgreSQL trigger payload is intentionally minimal (only
    assignment row fields) to stay well under the 8 KB pg_notify limit.
    Incident data (address, lat/lon, type) is added here via a JOIN.

Fallback behaviour:
    If the DB query fails (e.g. transient connection error), the enricher
    falls back to returning the raw payload fields wrapped in the schema.
    The SSE event is still delivered — just without incident metadata.

Usage (injected into route handlers via FastAPI ``Depends``):
    >>> async def adjuster_stream(
    ...     adjuster_id: int,
    ...     db: AsyncSession = Depends(get_db),
    ... ):
    ...     enricher = Enricher(db)
    ...     event = await enricher.enrich(payload)
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.assignment_repository import AssignmentRepository
from ..schemas.notification import EnrichedAssignmentEvent

logger = logging.getLogger(__name__)


class Enricher:
    """Joins raw broadcaster payloads with DB data to produce SSE events.

    Instantiated per-request (one per SSE connection) so each client has
    its own DB session.  The repository is re-used for the lifetime of the
    connection.

    Attributes:
        _repo: Read-only repository for enriched assignment projections.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._repo = AssignmentRepository(db)

    async def enrich(self, payload: dict) -> EnrichedAssignmentEvent:
        """Hydrate a raw broadcaster payload into a full SSE event schema.

        Attempts a DB JOIN to add incident fields.  Falls back to building
        the schema from the payload alone if the DB lookup fails or returns
        no rows.

        Args:
            payload: Raw dict from the broadcaster queue.  Must contain at
                minimum ``assignment_id``, ``adjuster_id``, ``incident_id``,
                and ``status``.

        Returns:
            A fully populated ``EnrichedAssignmentEvent`` ready for
            JSON serialisation and SSE delivery.
        """
        try:
            enriched = await self._repo.get_enriched(int(payload["assignment_id"]))
            if enriched is not None:
                return EnrichedAssignmentEvent(
                    assignment_id=enriched.assignment_id,
                    adjuster_id=enriched.adjuster_id,
                    incident_id=enriched.incident_id,
                    status=enriched.status,
                    event_type=payload.get("event", "assignment.updated"),
                    distance_km=enriched.distance_km,
                    travel_time_minutes=enriched.travel_time_minutes,
                    assigned_at=enriched.assigned_at,
                    route_polyline=enriched.route_polyline,
                    route_provider=enriched.route_provider,
                    route_distance_m=enriched.route_distance_m,
                    route_duration_s=enriched.route_duration_s,
                    incident_type=enriched.incident_type,
                    severity=enriched.severity,
                    description=enriched.description,
                    address=enriched.address,
                    latitude=enriched.latitude,
                    longitude=enriched.longitude,
                )
        except Exception:
            logger.exception(
                "Enrichment failed for assignment_id=%s — falling back to raw payload",
                payload.get("assignment_id"),
            )

        # Fallback: build from raw payload fields (no incident join)
        return EnrichedAssignmentEvent(
            assignment_id=int(payload["assignment_id"]),
            adjuster_id=int(payload["adjuster_id"]),
            incident_id=int(payload["incident_id"]),
            status=payload["status"],
            event_type=payload.get("event", "assignment.updated"),
            distance_km=payload.get("distance_km"),
            travel_time_minutes=payload.get("travel_time_minutes"),
            assigned_at=payload.get("assigned_at"),
            route_polyline=payload.get("route_polyline"),
            route_provider=payload.get("route_provider"),
            route_distance_m=payload.get("route_distance_m"),
            route_duration_s=payload.get("route_duration_s"),
            incident_type=payload.get("incident_type", "unknown"),
            severity=int(payload.get("severity", 0)),
            description=payload.get("description"),
            address=payload.get("address"),
            latitude=float(payload.get("latitude", 0.0)),
            longitude=float(payload.get("longitude", 0.0)),
        )
