"""Resource routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..schemas.pagination import PaginatedResponse
from ..schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate
from ..services.resource_service import ResourceService

router = APIRouter(prefix="/adjusters", tags=["adjusters"])


def get_resource_service(db: DBSession) -> ResourceService:
    return ResourceService(db)


ResourceServiceDep = Annotated[ResourceService, Depends(get_resource_service)]


@router.post(
    "/",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new resource",
)
async def create_resource(data: ResourceCreate, service: ResourceServiceDep) -> ResourceRead:
    resource = await service.create_resource(data)
    return ResourceRead.model_validate(resource)


@router.get(
    "/",
    response_model=PaginatedResponse[ResourceRead],
    summary="Get all resources",
)
async def get_resources(
    service: ResourceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool | None = Query(None),
) -> PaginatedResponse[ResourceRead]:
    items, total = await service.get_all_resources(skip=skip, limit=limit, is_active=is_active)
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(
        items=[ResourceRead.model_validate(r) for r in items],
        total=total,
        page=page,
        size=limit,
    )


@router.get(
    "/available",
    response_model=list[ResourceRead],
    summary="Get available resources",
)
async def get_available_resources(
    service: ResourceServiceDep,
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(50.0, gt=0, le=200),
    limit: int = Query(100, ge=1, le=1000),
    scenario: str = Query("initial"),
) -> list[ResourceRead]:
    return await service.get_available_resources(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        scenario=scenario,
    )


@router.post(
    "/reset-status",
    status_code=status.HTTP_200_OK,
    summary="Reset all resources to available",
)
async def reset_resources_status(service: ResourceServiceDep) -> dict:
    reset = await service.reset_all_to_available()
    return {"reset": reset}


@router.get(
    "/{resource_id}",
    response_model=ResourceRead,
    summary="Get resource by ID",
)
async def get_resource(resource_id: int, service: ResourceServiceDep) -> ResourceRead:
    resource = await service.get_resource(resource_id)
    return ResourceRead.model_validate(resource)


@router.patch(
    "/{resource_id}",
    response_model=ResourceRead,
    summary="Update resource",
)
async def update_resource(
    resource_id: int, data: ResourceUpdate, service: ResourceServiceDep
) -> ResourceRead:
    resource = await service.update_resource(resource_id, data)
    return ResourceRead.model_validate(resource)


@router.delete(
    "/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete resource",
)
async def delete_resource(resource_id: int, service: ResourceServiceDep) -> None:
    await service.soft_delete_resource(resource_id)
