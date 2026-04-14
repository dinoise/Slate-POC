"""Repository for Adjuster model with availability queries."""
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID, ST_GeogFromWKB
from sqlalchemy import cast
from geoalchemy2.types import Geography
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import Adjuster
from ..models.adjuster_position import AdjusterPosition
from .base_repository import BaseRepository


class AdjusterRepository(BaseRepository[Adjuster]):
    """Repository for Adjuster with availability operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(db, Adjuster)

    async def get_by_external_id(self, external_id: str) -> Adjuster | None:
        """
        Get adjuster by external ID.

        Args:
            external_id: External adjuster ID

        Returns:
            Adjuster or None
        """
        result = await self.db.execute(
            select(Adjuster).where(Adjuster.external_id == external_id)
        )
        return result.scalar_one_or_none()

    async def get_available(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 50.0,
        limit: int = 100,
        scenario: str = "initial",
    ) -> list[tuple[Adjuster, float | None, float | None]]:
        """Get available adjusters with their current working position.

        Performs a LEFT JOIN against ``adjuster_positions`` for the given
        scenario so that the geospatial filter and the returned coordinates
        reflect where the adjuster *is* right now, not where they live.

        When no position row exists for a scenario the home_location is used
        as fallback for the distance filter, and current_lat/lon are None.

        Args:
            latitude: Center point latitude for radius filter.
            longitude: Center point longitude for radius filter.
            radius_km: Search radius in kilometres.
            limit: Maximum results.
            scenario: Scenario name to join against (default ``"initial"``).

        Returns:
            List of ``(Adjuster, current_lat, current_lon)`` tuples.
            ``current_lat/lon`` are ``None`` when no position row was found.
        """
        pos = aliased(AdjusterPosition)

        # LEFT JOIN on adjuster_id + scenario so every available adjuster
        # is returned even if they have no position in this scenario.
        query = (
            select(Adjuster, pos.lat, pos.lon)
            .outerjoin(
                pos,
                (pos.adjuster_id == Adjuster.id) & (pos.scenario == scenario),
            )
            .where(
                Adjuster.is_active.is_(True),
                Adjuster.status == "available",
            )
        )

        if latitude is not None and longitude is not None:
            radius_m = radius_km * 1000
            # Cast to geography so ST_DWithin measures in metres, not degrees.
            point_geog = cast(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                Geography,
            )
            from sqlalchemy import case
            current_location = case(
                (pos.location.isnot(None), pos.location),
                else_=Adjuster.home_location,
            )
            query = query.where(
                ST_DWithin(cast(current_location, Geography), point_geog, radius_m)
            )

        query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.all()
        return [(adjuster, lat, lon) for adjuster, lat, lon in rows]

    async def get_by_skills(
        self,
        skills: list[str],
        limit: int = 100,
    ) -> list[Adjuster]:
        """
        Get adjusters with specific skills.

        Args:
            skills: List of required skills
            limit: Maximum results

        Returns:
            List of adjusters
        """
        query = (
            select(Adjuster)
            .where(
                Adjuster.is_active.is_(True),
                Adjuster.skills.contains(skills),
            )
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
