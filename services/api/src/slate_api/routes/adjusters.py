"""Adjuster routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..schemas.adjuster import AdjusterCreate, AdjusterRead, AdjusterUpdate
from ..schemas.pagination import PaginatedResponse
from ..services.adjuster_service import AdjusterService

router = APIRouter(prefix="/adjusters", tags=["adjusters"])


def get_adjuster_service(db: DBSession) -> AdjusterService:
    """Get adjuster service dependency."""
    return AdjusterService(db)


AdjusterServiceDep = Annotated[AdjusterService, Depends(get_adjuster_service)]


@router.post(
    "/",
    response_model=AdjusterRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new adjuster",
)
async def create_adjuster(
    data: AdjusterCreate,
    service: AdjusterServiceDep,
) -> AdjusterRead:
    """Create a new adjuster."""
    adjuster = await service.create_adjuster(data)
    return AdjusterRead.model_validate(adjuster)


@router.get(
    "/",
    response_model=PaginatedResponse[AdjusterRead],
    summary="Get all adjusters",
)
async def get_adjusters(
    service: AdjusterServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: bool | None = Query(None),
) -> PaginatedResponse[AdjusterRead]:
    """Get all adjusters, optionally filtered by active status."""
    items, total = await service.get_all_adjusters(skip=skip, limit=limit, is_active=is_active)
    page = (skip // limit) + 1 if limit else 1
    return PaginatedResponse(
        items=[AdjusterRead.model_validate(adj) for adj in items],
        total=total,
        page=page,
        size=limit,
    )


@router.get(
    "/available",
    response_model=list[AdjusterRead],
    summary="Get available adjusters",
)
async def get_available_adjusters(
    service: AdjusterServiceDep,
    latitude: float | None = Query(None, ge=-90, le=90),
    longitude: float | None = Query(None, ge=-180, le=180),
    radius_km: float = Query(50.0, gt=0, le=200),
    limit: int = Query(100, ge=1, le=1000),
    scenario: str = Query(
        "initial", description="Positioning scenario to use for current location."
    ),
) -> list[AdjusterRead]:
    """Get available adjusters with their current working position.

    Distance filter and returned coordinates use ``adjuster_positions``
    for the given scenario.  Falls back to ``home_location`` when no
    position row exists.

    Must be declared before /{adjuster_id} so FastAPI does not try to
    parse "available" as an integer path parameter.
    """
    return await service.get_available_adjusters(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
        scenario=scenario,
    )


@router.post(
    "/reset-status",
    status_code=status.HTTP_200_OK,
    summary="Reset all adjusters to available",
)
async def reset_adjusters_status(
    service: AdjusterServiceDep,
) -> dict:
    """Set all busy/en_route/on_site active adjusters back to available.

    Used by the demo reset flow (load initial state).
    """
    reset = await service.reset_all_to_available()
    return {"reset": reset}


@router.get(
    "/{adjuster_id}",
    response_model=AdjusterRead,
    summary="Get adjuster by ID",
)
async def get_adjuster(
    adjuster_id: int,
    service: AdjusterServiceDep,
) -> AdjusterRead:
    """Get a specific adjuster by ID."""
    adjuster = await service.get_adjuster(adjuster_id)
    return AdjusterRead.model_validate(adjuster)


@router.patch(
    "/{adjuster_id}",
    response_model=AdjusterRead,
    summary="Update adjuster",
)
async def update_adjuster(
    adjuster_id: int,
    data: AdjusterUpdate,
    service: AdjusterServiceDep,
) -> AdjusterRead:
    """Update an adjuster."""
    adjuster = await service.update_adjuster(adjuster_id, data)
    return AdjusterRead.model_validate(adjuster)


@router.delete(
    "/{adjuster_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete adjuster",
)
async def delete_adjuster(
    adjuster_id: int,
    service: AdjusterServiceDep,
) -> None:
    """Soft-delete an adjuster (sets is_active=False, status=offline)."""
    await service.soft_delete_adjuster(adjuster_id)
