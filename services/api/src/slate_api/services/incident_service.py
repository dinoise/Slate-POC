"""Business logic for Incident operations."""

import asyncio

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from slate_core.geospatial.base import RoutingProvider

from ..core.database import async_session_maker
from ..core.enums import (
    ACTIVE_ASSIGNMENT_STATUSES,
    ACTIVE_INCIDENT_STATUSES,
    AdjusterStatus,
    AssignmentStatus,
    IncidentStatus,
)
from ..core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from ..core.logging import get_logger
from ..models import Incident
from ..repositories.adjuster_repository import AdjusterRepository
from ..repositories.assignment_repository import AssignmentRepository
from ..repositories.incident_repository import IncidentRepository
from ..schemas.assignment import AdjusterCoord, IncidentCoord, OptimizeRequest
from ..schemas.incident import IncidentCreate, IncidentUpdate
from .assignment_service import AssignmentService

logger = get_logger(__name__)


class IncidentService:
    """Service for Incident business logic."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service."""
        self.repository = IncidentRepository(db)
        self.assignment_repository = AssignmentRepository(db)
        self.adjuster_repository = AdjusterRepository(db)

    async def create_incident(
        self,
        data: IncidentCreate,
        provider: RoutingProvider | None = None,
    ) -> Incident:
        """
        Create new incident.

        If *provider* is supplied, schedules an automatic background assignment
        immediately after creation using the nearest available adjuster.
        The HTTP response is returned before the routing call completes.

        Args:
            data: Incident creation data
            provider: Optional routing provider for auto-assignment

        Returns:
            Created incident

        Raises:
            ConflictError: If incident with external_id already exists
        """
        # Check if incident with external_id already exists
        existing = await self.repository.get_by_external_id(data.external_id)
        if existing:
            raise ConflictError(f"Incident with external_id '{data.external_id}' already exists")

        # Create geospatial point
        location = ST_MakePoint(data.longitude, data.latitude)

        # Create incident
        incident = await self.repository.create(
            external_id=data.external_id,
            incident_type=data.incident_type,
            severity=data.severity,
            description=data.description,
            latitude=data.latitude,
            longitude=data.longitude,
            location=location,
            address=data.address,
            incident_datetime=data.incident_datetime,
            reported_by_user_id=data.reported_by_user_id,
            status=IncidentStatus.PENDING,
        )

        if provider is not None:
            # Fire-and-forget — does not block the HTTP response.
            # Uses its own DB session because the request session closes
            # as soon as this coroutine returns.
            asyncio.create_task(
                _auto_assign(incident.id, incident.latitude, incident.longitude, provider),
                name=f"auto_assign_incident_{incident.id}",
            )
            logger.info("Auto-assignment scheduled for incident %d", incident.id)

        return incident

    async def get_incident(self, incident_id: int) -> Incident:
        """
        Get incident by ID.

        Args:
            incident_id: Incident ID

        Returns:
            Incident

        Raises:
            NotFoundError: If incident not found
        """
        incident = await self.repository.get_by_id(incident_id)
        if not incident:
            raise NotFoundError(f"Incident with id {incident_id} not found")
        return incident

    async def get_all_incidents(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[Incident], int]:
        """Get paginated incidents with total count.

        Args:
            skip: Records to skip
            limit: Maximum records
            status: Optional status filter

        Returns:
            Tuple of (items, total)
        """
        if status:
            items = await self.repository.get_by_status(status, limit)
            return items, len(items)
        return await self.repository.get_all_paginated(skip=skip, limit=limit)

    async def update_incident(
        self,
        incident_id: int,
        data: IncidentUpdate,
    ) -> Incident:
        """
        Update incident.

        Args:
            incident_id: Incident ID
            data: Update data

        Returns:
            Updated incident

        Raises:
            NotFoundError: If incident not found
        """
        # Check if exists
        await self.get_incident(incident_id)

        # Update
        updated = await self.repository.update(
            incident_id,
            **data.model_dump(exclude_unset=True),
        )

        if not updated:
            raise NotFoundError(f"Incident with id {incident_id} not found")

        return updated

    async def soft_delete_incident(self, incident_id: int) -> Incident:
        """
        Soft-delete an incident by setting status to cancelled.

        Also releases the assigned adjuster back to available if one exists.

        Raises:
            NotFoundError: If incident not found
        """
        await self.get_incident(incident_id)

        # Release adjuster if there is an active assignment for this incident
        assignments = await self.assignment_repository.get_by_incident(incident_id)
        for assignment in assignments:
            if assignment.status in ACTIVE_ASSIGNMENT_STATUSES:
                await self.assignment_repository.update(
                    assignment.id, status=AssignmentStatus.CANCELLED
                )
                await self.adjuster_repository.update(
                    assignment.adjuster_id, status=AdjusterStatus.AVAILABLE
                )

        updated = await self.repository.update(incident_id, status=IncidentStatus.CANCELLED)
        if not updated:
            raise NotFoundError(f"Incident with id {incident_id} not found")
        return updated

    async def cancel_all_active(self) -> int:
        """Cancel all active incidents and release their assigned adjusters.

        Returns:
            Number of incidents cancelled.
        """
        incidents = await self.repository.get_by_statuses(ACTIVE_INCIDENT_STATUSES, limit=1000)
        for incident in incidents:
            assignments = await self.assignment_repository.get_by_incident(incident.id)
            for assignment in assignments:
                if assignment.status in ACTIVE_ASSIGNMENT_STATUSES:
                    await self.assignment_repository.update(
                        assignment.id, status=AssignmentStatus.CANCELLED
                    )
                    await self.adjuster_repository.update(
                        assignment.adjuster_id, status=AdjusterStatus.AVAILABLE
                    )
            await self.repository.update(incident.id, status=IncidentStatus.CANCELLED)
        return len(incidents)

    async def get_nearby_incidents(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        limit: int = 100,
    ) -> list[Incident]:
        """
        Get incidents near a location.

        Args:
            latitude: Latitude
            longitude: Longitude
            radius_km: Search radius in km
            limit: Maximum results

        Returns:
            List of nearby incidents
        """
        return await self.repository.get_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )


# ── Auto-assignment background task ──────────────────────────────────────────


async def _auto_assign(
    incident_id: int,
    incident_lat: float,
    incident_lon: float,
    provider: RoutingProvider,
    radius_km: float = 50.0,
    search_limit: int = 20,
) -> None:
    """
    Find the nearest available adjuster and create an assignment.

    Delegates to AssignmentService.optimize_assignments with use_db=False,
    persist=True — passing explicit coords for the one incident and the
    nearby available adjusters fetched from the DB.

    Runs as a fire-and-forget asyncio task — owns its own DB session so it
    is completely decoupled from the originating HTTP request lifecycle.

    Args:
        incident_id: ID of the newly created incident.
        incident_lat / incident_lon: Coordinates for the routing query.
        provider: Active routing provider (OSRM / Valhalla / Google).
        radius_km: Search radius for candidate adjusters.
        search_limit: Max candidates to fetch from DB before routing.
    """
    try:
        async with async_session_maker() as db:
            adj_repo = AdjusterRepository(db)
            inc_repo = IncidentRepository(db)

            # 1. Verify incident is still pending (could have been cancelled)
            incident = await inc_repo.get_by_id(incident_id)
            if not incident or incident.status != "pending":
                logger.info(
                    "Auto-assign skipped for incident %d (status=%s)",
                    incident_id,
                    incident.status if incident else "not found",
                )
                return

            # 2. Fetch available adjusters near the incident
            candidates = await adj_repo.get_available(
                latitude=incident_lat,
                longitude=incident_lon,
                radius_km=radius_km,
                limit=search_limit,
            )

            if not candidates:
                logger.warning(
                    "Auto-assign: no available adjusters within %.0f km of incident %d",
                    radius_km,
                    incident_id,
                )
                return

            # 3. Build OptimizeRequest and delegate to AssignmentService
            inc_coord = IncidentCoord(
                incident_id=incident_id,
                latitude=incident_lat,
                longitude=incident_lon,
            )
            adj_coords = [
                AdjusterCoord(
                    adjuster_id=adj.id,
                    latitude=cur_lat if cur_lat is not None else adj.home_latitude,
                    longitude=cur_lon if cur_lon is not None else adj.home_longitude,
                )
                for adj, cur_lat, cur_lon in candidates
            ]

            optimize_request = OptimizeRequest(
                incidents=[inc_coord],
                adjusters=adj_coords,
                use_db=False,
                persist=True,
            )

            response = await AssignmentService(db).optimize_assignments(optimize_request, provider)

            if response.assignments:
                best = response.assignments[0]
                logger.info(
                    "Auto-assign: incident %d → adjuster %d (~%d min)",
                    incident_id,
                    best.adjuster_id,
                    round(best.travel_time_min),
                )
            else:
                logger.warning("Auto-assign: no reachable adjuster for incident %d", incident_id)

    except ServiceUnavailableError as exc:
        logger.warning(
            "Auto-assign: routing provider unavailable for incident %d: %s", incident_id, exc
        )
    except Exception:
        logger.exception("Auto-assign failed for incident %d", incident_id)
