"""Repository for enriched assignment queries in the notifications service."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from slate_core.models import Assignment, Incident
from slate_core.models.adjuster import Adjuster

# Active statuses — assignments that should appear on the observatory map.
# Mirrors slate_api/core/enums.py:ACTIVE_ASSIGNMENT_STATUSES; each service
# owns its own copy to avoid cross-service imports.
_ACTIVE_STATUSES = frozenset({"assigned", "accepted", "en_route", "arrived", "in_progress"})


@dataclass
class EnrichedAssignment:
    """Flat projection of assignment + incident + adjuster location for SSE payloads."""

    assignment_id: int
    adjuster_id: int
    incident_id: int
    status: str
    distance_km: float | None
    travel_time_minutes: int | None
    assigned_at: datetime | None
    route_polyline: str | None
    route_provider: str | None
    route_distance_m: int | None
    route_duration_s: int | None
    route_traffic_segments: list | None
    incident_type: str
    severity: int
    description: str | None
    address: str | None
    latitude: float
    longitude: float
    # Adjuster home location — always present (non-nullable in adjusters table)
    adjuster_lat: float
    adjuster_lon: float


class AssignmentRepository:
    """Queries for the notifications service — read-only, enriched projections."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_enriched(self, assignment_id: int) -> EnrichedAssignment | None:
        """Return a flat assignment + incident + adjuster location projection.

        JOINs adjusters to include home_latitude/home_longitude — always
        populated, unlike adjuster_positions which requires a positioning
        job to have run first.
        """
        result = await self.db.execute(
            select(Assignment, Incident, Adjuster)
            .join(Incident, Incident.id == Assignment.incident_id)
            .join(Adjuster, Adjuster.id == Assignment.adjuster_id)
            .where(Assignment.id == assignment_id)
        )
        row = result.first()
        if row is None:
            return None

        assignment, incident, adjuster = row
        return EnrichedAssignment(
            assignment_id=assignment.id,
            adjuster_id=assignment.adjuster_id,
            incident_id=assignment.incident_id,
            status=assignment.status,
            distance_km=assignment.distance_km,
            travel_time_minutes=assignment.travel_time_minutes,
            assigned_at=assignment.assigned_at,
            route_polyline=assignment.route_polyline,
            route_provider=assignment.route_provider,
            route_distance_m=assignment.route_distance_m,
            route_duration_s=assignment.route_duration_s,
            route_traffic_segments=assignment.route_traffic_segments,
            incident_type=incident.incident_type,
            severity=incident.severity,
            description=incident.description,
            address=incident.address,
            latitude=incident.latitude,
            longitude=incident.longitude,
            adjuster_lat=adjuster.home_latitude,
            adjuster_lon=adjuster.home_longitude,
        )

    async def get_by_incident(self, incident_id: int) -> list[EnrichedAssignment]:
        """Return enriched projections for all currently active assignments
        belonging to a specific incident.

        Same three-table JOIN as ``get_all_active_enriched`` but filtered to
        ``Assignment.incident_id == incident_id`` in addition to the
        active-status constraint.

        Used by the incident snapshot endpoint to populate the incident detail
        map on initial load, before the SSE stream has delivered any events.
        Typically returns 0 or 1 items — an incident has at most one active
        assignment at a time under current business rules.

        Args:
            incident_id: PK of the incident to query.

        Returns:
            List of ``EnrichedAssignment`` dataclasses ordered by
            ``assigned_at`` descending.  Empty list when the incident has no
            active assignments.
        """
        result = await self.db.execute(
            select(Assignment, Incident, Adjuster)
            .join(Incident, Incident.id == Assignment.incident_id)
            .join(Adjuster, Adjuster.id == Assignment.adjuster_id)
            .where(
                Assignment.incident_id == incident_id,
                Assignment.status.in_(_ACTIVE_STATUSES),
            )
            .order_by(Assignment.assigned_at.desc())
        )
        rows = result.all()
        return [
            EnrichedAssignment(
                assignment_id=a.id,
                adjuster_id=a.adjuster_id,
                incident_id=a.incident_id,
                status=a.status,
                distance_km=a.distance_km,
                travel_time_minutes=a.travel_time_minutes,
                assigned_at=a.assigned_at,
                route_polyline=a.route_polyline,
                route_provider=a.route_provider,
                route_distance_m=a.route_distance_m,
                route_duration_s=a.route_duration_s,
                route_traffic_segments=a.route_traffic_segments,
                incident_type=inc.incident_type,
                severity=inc.severity,
                description=inc.description,
                address=inc.address,
                latitude=inc.latitude,
                longitude=inc.longitude,
                adjuster_lat=adj.home_latitude,
                adjuster_lon=adj.home_longitude,
            )
            for a, inc, adj in rows
        ]

    async def get_all_active_enriched(self) -> list[EnrichedAssignment]:
        """Return enriched projections for all currently active assignments.

        Same three-table JOIN as ``get_enriched`` but without the
        ``WHERE id = ?`` filter — returns every assignment whose status
        is considered active (assigned, accepted, en_route, arrived,
        in_progress).

        Used by the snapshot endpoint to populate the observatory map on
        initial load, before the SSE stream has delivered any events.

        Returns:
            List of ``EnrichedAssignment`` dataclasses, one per active
            assignment.  Empty list when no active assignments exist.
        """
        result = await self.db.execute(
            select(Assignment, Incident, Adjuster)
            .join(Incident, Incident.id == Assignment.incident_id)
            .join(Adjuster, Adjuster.id == Assignment.adjuster_id)
            .where(Assignment.status.in_(_ACTIVE_STATUSES))
            .order_by(Assignment.assigned_at.desc())
        )
        rows = result.all()
        return [
            EnrichedAssignment(
                assignment_id=a.id,
                adjuster_id=a.adjuster_id,
                incident_id=a.incident_id,
                status=a.status,
                distance_km=a.distance_km,
                travel_time_minutes=a.travel_time_minutes,
                assigned_at=a.assigned_at,
                route_polyline=a.route_polyline,
                route_provider=a.route_provider,
                route_distance_m=a.route_distance_m,
                route_duration_s=a.route_duration_s,
                route_traffic_segments=a.route_traffic_segments,
                incident_type=inc.incident_type,
                severity=inc.severity,
                description=inc.description,
                address=inc.address,
                latitude=inc.latitude,
                longitude=inc.longitude,
                adjuster_lat=adj.home_latitude,
                adjuster_lon=adj.home_longitude,
            )
            for a, inc, adj in rows
        ]
