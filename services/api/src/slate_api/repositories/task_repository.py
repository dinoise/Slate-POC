"""Repository for Task model with geospatial queries."""

from collections.abc import Collection

from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Task
from .base_repository import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for Task with geospatial operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Task)

    async def get_by_external_id(self, external_id: str) -> Task | None:
        result = await self.db.execute(select(Task).where(Task.external_id == external_id))
        return result.scalar_one_or_none()

    async def get_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        limit: int = 100,
    ) -> list[Task]:
        radius_m = radius_km * 1000
        point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
        query = select(Task).where(ST_DWithin(Task.location, point, radius_m)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: str, limit: int = 100) -> list[Task]:
        query = select(Task).where(Task.status == status).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_statuses(self, statuses: Collection[str], limit: int = 1000) -> list[Task]:
        query = select(Task).where(Task.status.in_(statuses)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_by_status(self, status: str) -> int:
        query = select(func.count(Task.id)).where(Task.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()
