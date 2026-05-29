"""Dispatch routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..core.provider_registry import ProviderDep
from ..schemas.dispatch import (
    DispatchCreate,
    DispatchRead,
    DispatchStatusHistoryRead,
    DispatchUpdate,
    OptimizeRequest,
    OptimizeResponse,
    RouteResponse,
)
from ..schemas.dispatch_metrics import DispatchMetrics
from ..schemas.pagination import PaginatedResponse
from ..services.dispatch_metrics_service import DispatchMetricsService
from ..services.dispatch_service import DispatchService

router = APIRouter(prefix="/assignments", tags=["assignments"])


def get_dispatch_service(db: DBSession) -> DispatchService:
    return DispatchService(db)


DispatchServiceDep = Annotated[DispatchService, Depends(get_dispatch_service)]


def get_metrics_service(db: DBSession) -> DispatchMetricsService:
    return DispatchMetricsService(db)


MetricsServiceDep = Annotated[DispatchMetricsService, Depends(get_metrics_service)]


@router.get(
    "/metrics",
    response_model=DispatchMetrics,
    summary="Aggregated dispatch metrics for the analytics AI agent",
)
async def get_dispatch_metrics(
    service: MetricsServiceDep,
    window_hours: int = Query(8, ge=1, le=168),
) -> DispatchMetrics:
    return await service.get_metrics(window_hours=window_hours)


@router.post(
    "/",
    response_model=DispatchRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new dispatch",
)
async def create_dispatch(data: DispatchCreate, service: DispatchServiceDep) -> DispatchRead:
    dispatch = await service.create_dispatch(data)
    return DispatchRead.model_validate(dispatch)


@router.get(
    "/",
    response_model=PaginatedResponse[DispatchRead],
    summary="Get all dispatches",
)
async def get_dispatches(
    service: DispatchServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str | None = Query(None, alias="status"),
) -> PaginatedResponse[DispatchRead]:
    items, total = await service.get_all_dispatches(skip=skip, limit=limit, status=status_filter)
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(
        items=[DispatchRead.model_validate(d) for d in items],
        total=total,
        page=page,
        size=limit,
    )


@router.get(
    "/route",
    response_model=RouteResponse,
    summary="Compute a single point-to-point route",
)
async def compute_route(
    service: DispatchServiceDep,
    provider: ProviderDep,
    origin_lat: float = Query(..., ge=-90, le=90),
    origin_lon: float = Query(..., ge=-180, le=180),
    destination_lat: float = Query(..., ge=-90, le=90),
    destination_lon: float = Query(..., ge=-180, le=180),
) -> RouteResponse:
    return await service.compute_route(
        origin_lat, origin_lon, destination_lat, destination_lon, provider
    )


@router.get(
    "/by-task/{task_id}",
    response_model=list[DispatchRead],
    summary="Get dispatches for task",
)
async def get_dispatches_by_task(
    task_id: int,
    service: DispatchServiceDep,
    limit: int = Query(100, ge=1, le=1000),
    active: bool = Query(False),
) -> list[DispatchRead]:
    dispatches = await service.get_dispatches_by_task(task_id, limit, active_only=active)
    return [DispatchRead.model_validate(d) for d in dispatches]


@router.get(
    "/by-resource/{resource_id}",
    response_model=list[DispatchRead],
    summary="Get dispatches for resource",
)
async def get_dispatches_by_resource(
    resource_id: int,
    service: DispatchServiceDep,
    limit: int = Query(100, ge=1, le=1000),
    active: bool = Query(False),
) -> list[DispatchRead]:
    dispatches = await service.get_dispatches_by_resource(resource_id, limit, active_only=active)
    return [DispatchRead.model_validate(d) for d in dispatches]


@router.get(
    "/{dispatch_id}/history",
    response_model=list[DispatchStatusHistoryRead],
    summary="Get status history for a dispatch",
)
async def get_dispatch_history(
    dispatch_id: int,
    service: DispatchServiceDep,
) -> list[DispatchStatusHistoryRead]:
    history = await service.get_dispatch_history(dispatch_id)
    return [DispatchStatusHistoryRead.model_validate(entry) for entry in history]


@router.get(
    "/{dispatch_id}",
    response_model=DispatchRead,
    summary="Get dispatch by ID",
)
async def get_dispatch(dispatch_id: int, service: DispatchServiceDep) -> DispatchRead:
    dispatch = await service.get_dispatch(dispatch_id)
    return DispatchRead.model_validate(dispatch)


@router.patch(
    "/{dispatch_id}",
    response_model=DispatchRead,
    summary="Update dispatch",
)
async def update_dispatch(
    dispatch_id: int, data: DispatchUpdate, service: DispatchServiceDep
) -> DispatchRead:
    dispatch = await service.update_dispatch(dispatch_id, data)
    return DispatchRead.model_validate(dispatch)


@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Optimize resource-to-task dispatches",
)
async def optimize_dispatches(
    data: OptimizeRequest,
    service: DispatchServiceDep,
    provider: ProviderDep,
) -> OptimizeResponse:
    return await service.optimize_dispatches(data, provider)
