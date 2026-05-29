"""Business logic for Dispatch operations."""

import asyncio
import time
from datetime import UTC, datetime

import numpy as np
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from slate_core.geospatial.base import RoutingProvider
from slate_core.optimization import assignment_solver

from ..core.database import async_session_maker
from ..core.enums import DispatchStatus, ResourceStatus, TaskStatus
from ..core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from ..core.logging import get_logger
from ..models import Dispatch, DispatchStatusHistory
from ..repositories.dispatch_repository import DispatchRepository
from ..repositories.resource_repository import ResourceRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.dispatch import (
    CandidateResult,
    DispatchCreate,
    DispatchUpdate,
    OptimizedDispatch,
    OptimizeRequest,
    OptimizeResponse,
    ResourceCoord,
    RouteResponse,
    TaskCoord,
)

logger = get_logger(__name__)


class DispatchService:
    """Service for Dispatch business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = DispatchRepository(db)
        self.task_repository = TaskRepository(db)
        self.resource_repository = ResourceRepository(db)

    async def create_dispatch(self, data: DispatchCreate) -> Dispatch:
        task = await self.task_repository.get_by_id(data.task_id)
        if not task:
            raise NotFoundError(f"Task with id {data.task_id} not found")

        resource = await self.resource_repository.get_by_id(data.resource_id)
        if not resource:
            raise NotFoundError(f"Resource with id {data.resource_id} not found")

        if not resource.is_active:
            raise ValidationError(f"Resource {resource.id} is not active")

        if resource.status != "available":
            raise ValidationError(f"Resource {resource.id} is not available")

        active_dispatches = await self.repository.get_active_by_resource(data.resource_id)
        if len(active_dispatches) >= resource.max_cases_per_day:
            raise ValidationError(
                f"Resource {resource.id} has reached max cases per day ({resource.max_cases_per_day})"
            )

        dispatch = await self.repository.create(
            task_id=data.task_id,
            resource_id=data.resource_id,
            assigned_at=data.assigned_at,
            notes=data.notes,
            status=DispatchStatus.ASSIGNED,
        )

        await self.task_repository.update(data.task_id, status=TaskStatus.ASSIGNED)
        await self.resource_repository.update(data.resource_id, status=ResourceStatus.BUSY)

        return dispatch

    async def get_dispatch(self, dispatch_id: int) -> Dispatch:
        dispatch = await self.repository.get_by_id(dispatch_id)
        if not dispatch:
            raise NotFoundError(f"Dispatch with id {dispatch_id} not found")
        return dispatch

    async def get_all_dispatches(
        self,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> tuple[list[Dispatch], int]:
        if status:
            items = await self.repository.get_by_status(status, limit)
            return items, len(items)
        return await self.repository.get_all_paginated(skip=skip, limit=limit)

    async def update_dispatch(self, dispatch_id: int, data: DispatchUpdate) -> Dispatch:
        dispatch = await self.get_dispatch(dispatch_id)

        updated = await self.repository.update(dispatch_id, **data.model_dump(exclude_unset=True))
        if not updated:
            raise NotFoundError(f"Dispatch with id {dispatch_id} not found")

        if data.status == DispatchStatus.CANCELLED:
            await self.resource_repository.update(
                dispatch.resource_id, status=ResourceStatus.AVAILABLE
            )
            task = await self.task_repository.get_by_id(dispatch.task_id)
            if task and task.status != TaskStatus.CANCELLED:
                await self.task_repository.update(dispatch.task_id, status=TaskStatus.CANCELLED)

        elif data.status == DispatchStatus.COMPLETED:
            await self.resource_repository.update(
                dispatch.resource_id, status=ResourceStatus.AVAILABLE
            )
            await self.task_repository.update(dispatch.task_id, status=TaskStatus.COMPLETED)

        return updated

    async def get_dispatches_by_task(
        self, task_id: int, limit: int = 100, active_only: bool = False
    ) -> list[Dispatch]:
        if active_only:
            return await self.repository.get_active_by_task(task_id)
        return await self.repository.get_by_task(task_id, limit)

    async def get_dispatches_by_resource(
        self, resource_id: int, limit: int = 100, active_only: bool = False
    ) -> list[Dispatch]:
        if active_only:
            return await self.repository.get_active_by_resource(resource_id)
        return await self.repository.get_by_resource(resource_id, limit)

    async def get_dispatch_history(self, dispatch_id: int) -> list[DispatchStatusHistory]:
        dispatch = await self.repository.get_by_id(dispatch_id)
        if not dispatch:
            raise NotFoundError(f"Dispatch with id {dispatch_id} not found")
        return await self.repository.get_status_history(dispatch_id)

    async def compute_route(
        self,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        provider: RoutingProvider,
    ) -> RouteResponse:
        try:
            result = await provider.route(
                origin=(origin_lat, origin_lon),
                destination=(destination_lat, destination_lon),
            )
        except Exception as exc:
            raise ServiceUnavailableError(
                f"Routing provider '{provider.provider_name}' failed: {exc}"
            ) from exc

        return RouteResponse(
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=destination_lat,
            destination_lon=destination_lon,
            duration_s=result.duration_s,
            distance_m=result.distance_m,
            polyline=result.polyline,
            provider=result.provider,
            traffic_segments=[
                {"start_index": s.start_index, "end_index": s.end_index, "speed": s.speed}
                for s in result.traffic_segments
            ],
        )

    @staticmethod
    async def _fetch_and_save_route(
        dispatch_id: int,
        res_lat: float,
        res_lon: float,
        task_lat: float,
        task_lon: float,
        provider: RoutingProvider,
    ) -> None:
        try:
            result = await provider.route(
                origin=(res_lat, res_lon),
                destination=(task_lat, task_lon),
            )
        except Exception as exc:
            logger.warning(
                "Route fetch failed for dispatch %d (provider=%s): %s",
                dispatch_id,
                provider.provider_name,
                exc,
            )
            return

        traffic_segments: list | None = None
        if provider.supports_traffic and result.traffic_segments:
            traffic_segments = [
                {"start_index": s.start_index, "end_index": s.end_index, "speed": s.speed}
                for s in result.traffic_segments
            ]

        try:
            async with async_session_maker() as db:
                repo = DispatchRepository(db)
                await repo.save_route(
                    dispatch_id,
                    polyline=result.polyline,
                    provider=result.provider,
                    distance_m=result.distance_m,
                    duration_s=result.duration_s,
                    traffic_segments=traffic_segments,
                )
                await db.commit()
        except Exception as exc:
            logger.warning("Could not persist route for dispatch %d: %s", dispatch_id, exc)

    async def optimize_dispatches(
        self, request: OptimizeRequest, provider: RoutingProvider
    ) -> OptimizeResponse:
        """Run OR-Tools LinearSumAssignment to optimally dispatch resources to tasks."""
        if request.use_db:
            db_tasks = await self.task_repository.get_by_status("pending", limit=500)
            db_resource_rows = await self.resource_repository.get_available(limit=200)
            tasks = [
                TaskCoord(task_id=t.id, latitude=t.latitude, longitude=t.longitude)
                for t in db_tasks
            ]
            resources = [
                ResourceCoord(
                    resource_id=res.id,
                    latitude=cur_lat if cur_lat is not None else res.home_latitude,
                    longitude=cur_lon if cur_lon is not None else res.home_longitude,
                )
                for res, cur_lat, cur_lon in db_resource_rows
            ]
        else:
            tasks = request.tasks
            resources = request.resources

        if not tasks or not resources:
            return OptimizeResponse(
                dispatches=[],
                candidates=[],
                unassigned_task_ids=[t.task_id for t in tasks],
                total_travel_min=0.0,
                median_travel_min=0.0,
                p90_travel_min=0.0,
                solver_time_s=0.0,
                routing_provider=provider.provider_name,
                traffic_aware=False,
                n_tasks=len(tasks),
                n_resources=len(resources),
            )

        res_coords = [(r.latitude, r.longitude) for r in resources]
        task_coords = [(t.latitude, t.longitude) for t in tasks]

        logger.info(
            "Building time matrix: %d resources × %d tasks (provider=%s)",
            len(resources),
            len(tasks),
            provider.provider_name,
        )
        try:
            time_matrix = await provider.table(res_coords, task_coords)
        except Exception as exc:
            logger.error("Routing provider '%s' failed: %s", provider.provider_name, exc)
            raise ServiceUnavailableError(
                f"Routing provider '{provider.provider_name}' is not reachable"
            ) from exc

        max_travel_s = request.max_travel_min * 60
        capped = np.isinf(time_matrix) | (time_matrix > max_travel_s)
        if capped.any():
            time_matrix = np.where(capped, np.inf, time_matrix)

        t0 = time.perf_counter()
        results, unassigned_indices = assignment_solver.solve(time_matrix)
        solver_time_s = time.perf_counter() - t0

        all_candidates: list[CandidateResult] = []
        if request.top_k > 1:
            for task_idx, task in enumerate(tasks):
                col = time_matrix[:, task_idx]
                ranked = sorted(
                    (i for i in range(len(resources)) if not np.isinf(col[i])),
                    key=lambda i: col[i],
                )
                for rank, res_idx in enumerate(ranked[: request.top_k], start=1):
                    t_s = float(col[res_idx])
                    all_candidates.append(
                        CandidateResult(
                            task_id=task.task_id,
                            resource_id=resources[res_idx].resource_id,
                            travel_time_s=t_s,
                            travel_time_min=t_s / 60,
                            rank=rank,
                        )
                    )

        optimized: list[OptimizedDispatch] = []
        for r in results:
            resource = resources[r.adjuster_idx]
            task = tasks[r.claim_idx]
            db_id: int | None = None

            if request.persist:
                travel_min = round(r.travel_time_s / 60)
                try:
                    dispatch = await self.repository.create(
                        task_id=task.task_id,
                        resource_id=resource.resource_id,
                        assigned_at=datetime.now(UTC),
                        travel_time_minutes=travel_min,
                        status=DispatchStatus.ASSIGNED,
                    )
                except IntegrityError:
                    logger.warning(
                        "Skipping duplicate dispatch for task_id=%d (already dispatched)",
                        task.task_id,
                    )
                    continue
                db_id = dispatch.id
                await self.task_repository.update(task.task_id, status=TaskStatus.ASSIGNED)
                await self.resource_repository.update(
                    resource.resource_id, status=ResourceStatus.BUSY
                )
                asyncio.create_task(
                    self._fetch_and_save_route(
                        db_id,
                        resource.latitude,
                        resource.longitude,
                        task.latitude,
                        task.longitude,
                        provider,
                    )
                )

            optimized.append(
                OptimizedDispatch(
                    resource_id=resource.resource_id,
                    task_id=task.task_id,
                    travel_time_s=r.travel_time_s,
                    travel_time_min=r.travel_time_min,
                    dispatch_id=db_id,
                )
            )

        unassigned_ids = [tasks[i].task_id for i in unassigned_indices]
        travel_mins = np.array([d.travel_time_min for d in optimized])

        logger.info(
            "Optimization complete: dispatched=%d, unassigned=%d, solver_time=%.2fs",
            len(optimized),
            len(unassigned_ids),
            solver_time_s,
        )

        return OptimizeResponse(
            dispatches=optimized,
            candidates=all_candidates,
            unassigned_task_ids=unassigned_ids,
            total_travel_min=float(travel_mins.sum()) if len(travel_mins) else 0.0,
            median_travel_min=float(np.median(travel_mins)) if len(travel_mins) else 0.0,
            p90_travel_min=float(np.percentile(travel_mins, 90)) if len(travel_mins) else 0.0,
            solver_time_s=solver_time_s,
            n_tasks=len(tasks),
            n_resources=len(resources),
            routing_provider=provider.provider_name,
            traffic_aware=provider.supports_traffic,
        )
