"""Repository for Resource model with availability queries."""

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from geoalchemy2.types import Geography
from sqlalchemy import case, cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import Resource, ResourcePosition
from .base_repository import BaseRepository


class ResourceRepository(BaseRepository[Resource]):
    """Repository for Resource with availability operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Resource)

    async def get_by_external_id(self, external_id: str) -> Resource | None:
        result = await self.db.execute(select(Resource).where(Resource.external_id == external_id))
        return result.scalar_one_or_none()

    async def get_available(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 50.0,
        limit: int = 100,
        scenario: str = "initial",
    ) -> list[tuple[Resource, float | None, float | None]]:
        """Get available resources with their current working position.

        Returns list of (Resource, current_lat, current_lon) tuples.
        current_lat/lon are None when no position row was found.
        """
        pos = aliased(ResourcePosition)

        query = (
            select(Resource, pos.lat, pos.lon)
            .outerjoin(
                pos,
                (pos.resource_id == Resource.id) & (pos.scenario == scenario),
            )
            .where(
                Resource.is_active.is_(True),
                Resource.status == "available",
            )
        )

        if latitude is not None and longitude is not None:
            radius_m = radius_km * 1000
            point_geog = cast(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326),
                Geography,
            )
            current_location = case(
                (pos.location.isnot(None), pos.location),
                else_=Resource.home_location,
            )
            query = query.where(ST_DWithin(cast(current_location, Geography), point_geog, radius_m))

        query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.all()
        return [(resource, lat, lon) for resource, lat, lon in rows]

    async def get_by_skills(self, skills: list[str], limit: int = 100) -> list[Resource]:
        query = (
            select(Resource)
            .where(Resource.is_active.is_(True), Resource.skills.contains(skills))
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
