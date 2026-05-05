"""Repository for Assignment model."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.enums import ACTIVE_ASSIGNMENT_STATUSES
from ..models import Assignment, AssignmentStatusHistory
from .base_repository import BaseRepository


class AssignmentRepository(BaseRepository[Assignment]):
    """Repository for Assignment operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(db, Assignment)

    async def get_by_incident(
        self,
        incident_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments for an incident.

        Args:
            incident_id: Incident ID
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = select(Assignment).where(Assignment.incident_id == incident_id).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_incident(
        self,
        incident_id: int,
    ) -> list[Assignment]:
        """Get non-terminal assignments for an incident."""
        query = select(Assignment).where(
            Assignment.incident_id == incident_id,
            Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_adjuster(
        self,
        adjuster_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments for an adjuster.

        Args:
            adjuster_id: Adjuster ID
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = select(Assignment).where(Assignment.adjuster_id == adjuster_id).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_adjuster(
        self,
        adjuster_id: int,
    ) -> list[Assignment]:
        """
        Get active assignments for an adjuster.

        Args:
            adjuster_id: Adjuster ID

        Returns:
            List of active assignments
        """
        query = select(Assignment).where(
            Assignment.adjuster_id == adjuster_id,
            Assignment.status.in_(ACTIVE_ASSIGNMENT_STATUSES),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments by status.

        Args:
            status: Assignment status
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = select(Assignment).where(Assignment.status == status).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_route(
        self,
        assignment_id: int,
        *,
        polyline: str,
        provider: str,
        distance_m: int,
        duration_s: int,
        traffic_segments: list | None = None,
    ) -> Assignment | None:
        """Persist route data onto an existing assignment.

        Args:
            assignment_id: Target assignment.
            polyline: Precision-5 encoded polyline.
            provider: Routing provider name (e.g. "osrm", "google").
            distance_m: Route distance in metres.
            duration_s: Route duration in seconds.
            traffic_segments: Optional list of speed-classified polyline
                segments from a traffic-aware provider. Each entry is a dict
                with keys start_index, end_index, speed.

        Returns:
            Updated Assignment, or None if not found.
        """
        assignment = await self.get_by_id(assignment_id)
        if assignment is None:
            return None
        assignment.route_polyline = polyline
        assignment.route_provider = provider
        assignment.route_distance_m = distance_m
        assignment.route_duration_s = duration_s
        assignment.route_fetched_at = datetime.now(UTC)
        assignment.route_traffic_segments = traffic_segments or None
        await self.db.flush()
        return assignment

    async def get_status_history(
        self,
        assignment_id: int,
    ) -> list[AssignmentStatusHistory]:
        """Return the status-change audit trail for an assignment, oldest-first."""
        query = (
            select(AssignmentStatusHistory)
            .where(AssignmentStatusHistory.assignment_id == assignment_id)
            .order_by(AssignmentStatusHistory.changed_at)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
