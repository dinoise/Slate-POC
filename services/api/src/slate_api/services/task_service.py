"""Business logic for Task operations."""

import asyncio

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from slate_core.geospatial.base import RoutingProvider

from ..core.database import async_session_maker
from ..core.enums import (
    ACTIVE_DISPATCH_STATUSES,
    ACTIVE_TASK_STATUSES,
    DispatchStatus,
    ResourceStatus,
    TaskStatus,
)
from ..core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from ..core.logging import get_logger
from ..models import Task
from ..repositories.dispatch_repository import DispatchRepository
from ..repositories.resource_repository import ResourceRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.dispatch import OptimizeRequest, ResourceCoord, TaskCoord
from ..schemas.task import TaskCreate, TaskUpdate
from .dispatch_service import DispatchService

logger = get_logger(__name__)


class TaskService:
    """Service for Task business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = TaskRepository(db)
        self.dispatch_repository = DispatchRepository(db)
        self.resource_repository = ResourceRepository(db)

    async def create_task(
        self,
        data: TaskCreate,
        provider: RoutingProvider | None = None,
    ) -> Task:
        """Create a new task, optionally triggering auto-dispatch."""
        existing = await self.repository.get_by_external_id(data.external_id)
        if existing:
            raise ConflictError(f"Task with external_id '{data.external_id}' already exists")

        location = ST_MakePoint(data.longitude, data.latitude)

        task = await self.repository.create(
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
            status=TaskStatus.PENDING,
        )

        if provider is not None:
            asyncio.create_task(
                _auto_dispatch(task.id, task.latitude, task.longitude, provider),
                name=f"auto_dispatch_task_{task.id}",
            )
            logger.info("Auto-dispatch scheduled for task %d", task.id)

        return task

    async def get_task(self, task_id: int) -> Task:
        task = await self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundError(f"Task with id {task_id} not found")
        return task

    async def get_all_tasks(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[Task], int]:
        if status:
            items = await self.repository.get_by_status(status, limit)
            return items, len(items)
        return await self.repository.get_all_paginated(skip=skip, limit=limit)

    async def update_task(self, task_id: int, data: TaskUpdate) -> Task:
        await self.get_task(task_id)

        updated = await self.repository.update(task_id, **data.model_dump(exclude_unset=True))
        if not updated:
            raise NotFoundError(f"Task with id {task_id} not found")
        return updated

    async def soft_delete_task(self, task_id: int) -> Task:
        """Cancel a task and release any active dispatches."""
        await self.get_task(task_id)

        dispatches = await self.dispatch_repository.get_by_task(task_id)
        for dispatch in dispatches:
            if dispatch.status in ACTIVE_DISPATCH_STATUSES:
                await self.dispatch_repository.update(dispatch.id, status=DispatchStatus.CANCELLED)
                await self.resource_repository.update(
                    dispatch.resource_id, status=ResourceStatus.AVAILABLE
                )

        updated = await self.repository.update(task_id, status=TaskStatus.CANCELLED)
        if not updated:
            raise NotFoundError(f"Task with id {task_id} not found")
        return updated

    async def cancel_all_active(self) -> int:
        """Cancel all active tasks and release their dispatched resources."""
        tasks = await self.repository.get_by_statuses(ACTIVE_TASK_STATUSES, limit=1000)
        for task in tasks:
            dispatches = await self.dispatch_repository.get_by_task(task.id)
            for dispatch in dispatches:
                if dispatch.status in ACTIVE_DISPATCH_STATUSES:
                    await self.dispatch_repository.update(
                        dispatch.id, status=DispatchStatus.CANCELLED
                    )
                    await self.resource_repository.update(
                        dispatch.resource_id, status=ResourceStatus.AVAILABLE
                    )
            await self.repository.update(task.id, status=TaskStatus.CANCELLED)
        return len(tasks)

    async def get_nearby_tasks(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        limit: int = 100,
    ) -> list[Task]:
        return await self.repository.get_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
        )


# ── Auto-dispatch background task ────────────────────────────────────────────


async def _auto_dispatch(
    task_id: int,
    task_lat: float,
    task_lon: float,
    provider: RoutingProvider,
    radius_km: float = 50.0,
    search_limit: int = 20,
) -> None:
    """Find the nearest available resource and create a dispatch."""
    try:
        async with async_session_maker() as db:
            res_repo = ResourceRepository(db)
            task_repo = TaskRepository(db)

            task = await task_repo.get_by_id(task_id)
            if not task or task.status != "pending":
                logger.info(
                    "Auto-dispatch skipped for task %d (status=%s)",
                    task_id,
                    task.status if task else "not found",
                )
                return

            candidates = await res_repo.get_available(
                latitude=task_lat,
                longitude=task_lon,
                radius_km=radius_km,
                limit=search_limit,
            )

            if not candidates:
                logger.warning(
                    "Auto-dispatch: no available resources within %.0f km of task %d",
                    radius_km,
                    task_id,
                )
                return

            task_coord = TaskCoord(task_id=task_id, latitude=task_lat, longitude=task_lon)
            res_coords = [
                ResourceCoord(
                    resource_id=res.id,
                    latitude=cur_lat if cur_lat is not None else res.home_latitude,
                    longitude=cur_lon if cur_lon is not None else res.home_longitude,
                )
                for res, cur_lat, cur_lon in candidates
            ]

            optimize_request = OptimizeRequest(
                tasks=[task_coord],
                resources=res_coords,
                use_db=False,
                persist=True,
            )

            response = await DispatchService(db).optimize_dispatches(optimize_request, provider)

            if response.dispatches:
                best = response.dispatches[0]
                logger.info(
                    "Auto-dispatch: task %d → resource %d (~%d min)",
                    task_id,
                    best.resource_id,
                    round(best.travel_time_min),
                )
            else:
                logger.warning("Auto-dispatch: no reachable resource for task %d", task_id)

    except ServiceUnavailableError as exc:
        logger.warning("Auto-dispatch: routing provider unavailable for task %d: %s", task_id, exc)
    except Exception:
        logger.exception("Auto-dispatch failed for task %d", task_id)
