"""Repository for enriched assignment queries in the notifications service."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from slate_core.models import Assignment, Incident


@dataclass
class EnrichedAssignment:
    """Flat projection of assignment + incident data for SSE payloads."""

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


class AssignmentRepository:
    """Queries for the notifications service — read-only, enriched projections."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_enriched(self, assignment_id: int) -> EnrichedAssignment | None:
        """Return a flat assignment+incident projection for SSE enrichment.

        Replaces the raw SQL JOIN that was previously hardcoded in stream.py.
        """
        result = await self.db.execute(
            select(Assignment, Incident)
            .join(Incident, Incident.id == Assignment.incident_id)
            .where(Assignment.id == assignment_id)
        )
        row = result.first()
        if row is None:
            return None

        assignment, incident = row
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
        )
