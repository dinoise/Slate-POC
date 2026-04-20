"""Business logic for Adjuster operations."""

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ConflictError, NotFoundError
from ..models import Adjuster
from ..repositories.adjuster_repository import AdjusterRepository
from ..schemas.adjuster import AdjusterCreate, AdjusterRead, AdjusterUpdate


class AdjusterService:
    """Service for Adjuster business logic."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service."""
        self.repository = AdjusterRepository(db)

    async def create_adjuster(self, data: AdjusterCreate) -> Adjuster:
        """
        Create new adjuster.

        Args:
            data: Adjuster creation data

        Returns:
            Created adjuster

        Raises:
            ConflictError: If adjuster with external_id or email already exists
        """
        # Check if adjuster with external_id already exists
        existing = await self.repository.get_by_external_id(data.external_id)
        if existing:
            raise ConflictError(f"Adjuster with external_id '{data.external_id}' already exists")

        # Create geospatial point for home location
        home_location = ST_MakePoint(data.home_longitude, data.home_latitude)

        # Create adjuster
        adjuster = await self.repository.create(
            external_id=data.external_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            home_latitude=data.home_latitude,
            home_longitude=data.home_longitude,
            home_location=home_location,
            skills=data.skills,
            max_cases_per_day=data.max_cases_per_day,
            is_active=True,
            status="available",
        )

        return adjuster

    async def get_adjuster(self, adjuster_id: int) -> Adjuster:
        """
        Get adjuster by ID.

        Args:
            adjuster_id: Adjuster ID

        Returns:
            Adjuster

        Raises:
            NotFoundError: If adjuster not found
        """
        adjuster = await self.repository.get_by_id(adjuster_id)
        if not adjuster:
            raise NotFoundError(f"Adjuster with id {adjuster_id} not found")
        return adjuster

    async def get_all_adjusters(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> tuple[list[Adjuster], int]:
        """
        Get paginated adjusters with total count.

        Returns:
            Tuple of (items, total)
        """
        filters = {}
        if is_active is not None:
            filters["is_active"] = is_active
        items, total = await self.repository.get_all_paginated(skip=skip, limit=limit, **filters)
        return items, total

    async def update_adjuster(
        self,
        adjuster_id: int,
        data: AdjusterUpdate,
    ) -> Adjuster:
        """
        Update adjuster.

        Args:
            adjuster_id: Adjuster ID
            data: Update data

        Returns:
            Updated adjuster

        Raises:
            NotFoundError: If adjuster not found
        """
        # Check if exists
        await self.get_adjuster(adjuster_id)

        # Update
        updated = await self.repository.update(
            adjuster_id,
            **data.model_dump(exclude_unset=True),
        )

        if not updated:
            raise NotFoundError(f"Adjuster with id {adjuster_id} not found")

        return updated

    async def soft_delete_adjuster(self, adjuster_id: int) -> Adjuster:
        """
        Soft-delete an adjuster by setting is_active=False and status=offline.

        Raises:
            NotFoundError: If adjuster not found
        """
        await self.get_adjuster(adjuster_id)
        updated = await self.repository.update(adjuster_id, is_active=False, status="offline")
        if not updated:
            raise NotFoundError(f"Adjuster with id {adjuster_id} not found")
        return updated

    async def get_available_adjusters(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 50.0,
        skills: list[str] | None = None,
        limit: int = 100,
        scenario: str = "initial",
    ) -> list[AdjusterRead]:
        """Get available adjusters with their current working position.

        Returns ``AdjusterRead`` objects enriched with ``current_latitude`` /
        ``current_longitude`` from ``adjuster_positions`` for the given
        scenario.  Falls back to ``home_latitude/longitude`` when no position
        row exists.

        Args:
            latitude: Optional center point for radius filter.
            longitude: Optional center point for radius filter.
            radius_km: Search radius in km.
            skills: Optional required skills filter.
            limit: Maximum results.
            scenario: Positioning scenario to join (default ``"initial"``).

        Returns:
            List of AdjusterRead with current_latitude/longitude populated.
        """
        if skills:
            plain_adjs = await self.repository.get_by_skills(skills, limit)
            return [AdjusterRead.model_validate(a) for a in plain_adjs]

        rows = await self.repository.get_available(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
            scenario=scenario,
        )

        result = []
        for adjuster, cur_lat, cur_lon in rows:
            read = AdjusterRead.model_validate(adjuster)
            read.current_latitude = cur_lat
            read.current_longitude = cur_lon
            result.append(read)
        return result

    async def reset_all_to_available(self) -> int:
        """Set all active (non-offline) adjusters back to status=available.

        Used by the demo reset flow to clear any busy/en_route state
        left over from previous incident assignments.

        Returns:
            Number of adjusters reset.
        """
        busy_statuses = ["busy", "en_route", "on_site"]
        reset = 0
        for s in busy_statuses:
            adjusters = await self.repository.get_all(limit=1000, status=s, is_active=True)
            for adjuster in adjusters:
                await self.repository.update(adjuster.id, status="available")
                reset += 1
        return reset
