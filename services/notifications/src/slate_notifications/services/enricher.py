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
    The SSE event is still delivered — just without incident metadata,
    and with ``adjuster`` set to ``None``.

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

from ..repositories.dispatch_repository import DispatchRepository, EnrichedDispatch
from ..schemas.notification import (
    AdjusterInfo,
    EnrichedAssignmentEvent,
    IncidentInfo,
    RouteInfo,
)

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
        self._repo = DispatchRepository(db)

    @staticmethod
    def build_from_enriched(
        enriched: EnrichedDispatch,
        event_type: str = "assignment.updated",
    ) -> EnrichedAssignmentEvent:
        """Build an ``EnrichedAssignmentEvent`` from a pre-joined DB projection.

        Pure function — no DB access, no async.  Shared by the per-event
        stream path (``enrich``) and the bulk snapshot endpoint so both
        always produce identical output shapes.

        Args:
            enriched: Flat projection returned by ``AssignmentRepository``.
            event_type: Discriminator string; defaults to
                ``'assignment.updated'``.

        Returns:
            A fully populated ``EnrichedAssignmentEvent``.
        """
        route = None
        if enriched.route_polyline is not None:
            route = RouteInfo(
                polyline=enriched.route_polyline,
                provider=enriched.route_provider,
                distance_m=enriched.route_distance_m,
                duration_s=enriched.route_duration_s,
                traffic_segments=enriched.route_traffic_segments,
            )
        return EnrichedAssignmentEvent(
            assignment_id=enriched.dispatch_id,
            status=enriched.status,
            event_type=event_type,
            distance_km=enriched.distance_km,
            travel_time_minutes=enriched.travel_time_minutes,
            assigned_at=enriched.assigned_at,
            incident=IncidentInfo(
                id=enriched.task_id,
                type=enriched.incident_type,
                severity=enriched.severity,
                description=enriched.description,
                address=enriched.address,
                latitude=enriched.latitude,
                longitude=enriched.longitude,
            ),
            adjuster=AdjusterInfo(
                id=enriched.resource_id,
                latitude=enriched.resource_lat,
                longitude=enriched.resource_lon,
            ),
            route=route,
        )

    async def enrich(self, payload: dict) -> EnrichedAssignmentEvent:
        """Hydrate a raw broadcaster payload into a full SSE event schema.

        Attempts a DB JOIN to add incident and adjuster fields.  Falls back
        to building the schema from the payload alone if the DB lookup fails
        or returns no rows (``adjuster`` will be ``None`` in that case).

        Args:
            payload: Raw dict from the broadcaster queue.  Must contain at
                minimum ``assignment_id``, ``adjuster_id``, ``incident_id``,
                and ``status``.

        Returns:
            A fully populated ``EnrichedAssignmentEvent`` ready for
            JSON serialisation and SSE delivery.
        """
        try:
            enriched = await self._repo.get_enriched(int(payload["dispatch_id"]))
            if enriched is not None:
                return self.build_from_enriched(
                    enriched,
                    event_type=payload.get("event", "assignment.updated"),
                )
        except Exception:
            logger.exception(
                "Enrichment failed for dispatch_id=%s — falling back to raw payload",
                payload.get("dispatch_id"),
            )

        # Fallback: build from raw payload fields (no task/resource join).
        raw_polyline = payload.get("route_polyline")
        route = None
        if raw_polyline is not None:
            route = RouteInfo(
                polyline=raw_polyline,
                provider=payload.get("route_provider"),
                distance_m=payload.get("route_distance_m"),
                duration_s=payload.get("route_duration_s"),
                traffic_segments=payload.get("route_traffic_segments"),
            )
        return EnrichedAssignmentEvent(
            assignment_id=int(payload["dispatch_id"]),
            status=payload["status"],
            event_type=payload.get("event", "assignment.updated"),
            distance_km=payload.get("distance_km"),
            travel_time_minutes=payload.get("travel_time_minutes"),
            assigned_at=payload.get("assigned_at"),
            incident=IncidentInfo(
                id=int(payload.get("task_id", 0)),
                type=payload.get("incident_type", "unknown"),
                severity=int(payload.get("severity", 0)),
                description=payload.get("description"),
                address=payload.get("address"),
                latitude=float(payload.get("latitude", 0.0)),
                longitude=float(payload.get("longitude", 0.0)),
            ),
            adjuster=None,
            route=route,
        )
