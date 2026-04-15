"""Repository for Incident model with geospatial queries."""

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Incident
from .base_repository import BaseRepository


class IncidentRepository(BaseRepository[Incident]):
    """Repository for Incident with geospatial operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(db, Incident)

    async def get_by_external_id(self, external_id: str) -> Incident | None:
        """
        Get incident by external ID.

        Args:
            external_id: External incident ID

        Returns:
            Incident or None
        """
        result = await self.db.execute(select(Incident).where(Incident.external_id == external_id))
        return result.scalar_one_or_none()

    async def get_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        limit: int = 100,
    ) -> list[Incident]:
        """
        Get incidents within radius of a point.

        Args:
            latitude: Center point latitude
            longitude: Center point longitude
            radius_km: Search radius in kilometers
            limit: Maximum results

        Returns:
            List of nearby incidents
        """
        # Convert km to meters for PostGIS
        radius_m = radius_km * 1000

        # Create point from lat/lon
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)

        # Query incidents within radius
        query = select(Incident).where(ST_DWithin(Incident.location, point, radius_m)).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: str, limit: int = 100) -> list[Incident]:
        """
        Get incidents by status.

        Args:
            status: Incident status
            limit: Maximum results

        Returns:
            List of incidents
        """
        query = select(Incident).where(Incident.status == status).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self, status: str) -> int:
        """
        Count incidents by status.

        Args:
            status: Incident status

        Returns:
            Count of incidents
        """
        query = select(func.count(Incident.id)).where(Incident.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()
