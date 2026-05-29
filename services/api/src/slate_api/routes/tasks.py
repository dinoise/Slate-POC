"""Task routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..core.provider_registry import ProviderDep
from ..schemas.pagination import PaginatedResponse
from ..schemas.task import TaskCreate, TaskRead, TaskUpdate
from ..services.task_service import TaskService

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_task_service(db: DBSession) -> TaskService:
    return TaskService(db)


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


@router.post(
    "/",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new task",
)
async def create_task(
    data: TaskCreate,
    service: TaskServiceDep,
    provider: ProviderDep,
) -> TaskRead:
    task = await service.create_task(data, provider=provider)
    return TaskRead.model_validate(task)


@router.get(
    "/",
    response_model=PaginatedResponse[TaskRead],
    summary="Get all tasks",
)
async def get_tasks(
    service: TaskServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str | None = Query(None, alias="status"),
) -> PaginatedResponse[TaskRead]:
    items, total = await service.get_all_tasks(skip=skip, limit=limit, status=status_filter)
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(
        items=[TaskRead.model_validate(t) for t in items],
        total=total,
        page=page,
        size=limit,
    )


@router.get(
    "/{task_id}",
    response_model=TaskRead,
    summary="Get task by ID",
)
async def get_task(task_id: int, service: TaskServiceDep) -> TaskRead:
    task = await service.get_task(task_id)
    return TaskRead.model_validate(task)


@router.patch(
    "/{task_id}",
    response_model=TaskRead,
    summary="Update task",
)
async def update_task(task_id: int, data: TaskUpdate, service: TaskServiceDep) -> TaskRead:
    task = await service.update_task(task_id, data)
    return TaskRead.model_validate(task)


@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Cancel all active tasks",
)
async def cancel_all_tasks(service: TaskServiceDep) -> dict:
    cancelled = await service.cancel_all_active()
    return {"cancelled": cancelled}


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete task",
)
async def delete_task(task_id: int, service: TaskServiceDep) -> None:
    await service.soft_delete_task(task_id)


@router.get(
    "/nearby/",
    response_model=list[TaskRead],
    summary="Get nearby tasks",
)
async def get_nearby_tasks(
    service: TaskServiceDep,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=100),
    limit: int = Query(100, ge=1, le=1000),
) -> list[TaskRead]:
    tasks = await service.get_nearby_tasks(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )
    return [TaskRead.model_validate(t) for t in tasks]
