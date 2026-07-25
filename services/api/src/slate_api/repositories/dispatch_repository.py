"""Repository for Dispatch model."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.enums import ACTIVE_DISPATCH_STATUSES
from ..models import Dispatch, DispatchStatusHistory
from .base_repository import BaseRepository


class DispatchRepository(BaseRepository[Dispatch]):
    """Repository for Dispatch operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, Dispatch)

    async def get_by_task(self, task_id: int, limit: int = 100) -> list[Dispatch]:
        query = select(Dispatch).where(Dispatch.task_id == task_id).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_task(self, task_id: int) -> list[Dispatch]:
        query = select(Dispatch).where(
            Dispatch.task_id == task_id,
            Dispatch.status.in_(ACTIVE_DISPATCH_STATUSES),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_resource(self, resource_id: int, limit: int = 100) -> list[Dispatch]:
        query = select(Dispatch).where(Dispatch.resource_id == resource_id).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_resource(self, resource_id: int) -> list[Dispatch]:
        query = select(Dispatch).where(
            Dispatch.resource_id == resource_id,
            Dispatch.status.in_(ACTIVE_DISPATCH_STATUSES),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_status(self, status: str, limit: int = 100) -> list[Dispatch]:
        query = select(Dispatch).where(Dispatch.status == status).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def save_route(
        self,
        dispatch_id: int,
        *,
        polyline: str,
        provider: str,
        distance_m: int,
        duration_s: int,
        traffic_segments: list | None = None,
    ) -> Dispatch | None:
        """Persist route data onto an existing dispatch."""
        dispatch = await self.get_by_id(dispatch_id)
        if dispatch is None:
            return None
        dispatch.route_polyline = polyline
        dispatch.route_provider = provider
        dispatch.route_distance_m = distance_m
        dispatch.route_duration_s = duration_s
        dispatch.route_fetched_at = datetime.now(UTC)
        dispatch.route_traffic_segments = traffic_segments or None
        await self.db.flush()
        return dispatch

    async def get_status_history(self, dispatch_id: int) -> list[DispatchStatusHistory]:
        """Return the status-change audit trail for a dispatch, oldest-first."""
        query = (
            select(DispatchStatusHistory)
            .where(DispatchStatusHistory.dispatch_id == dispatch_id)
            .order_by(DispatchStatusHistory.changed_at)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
