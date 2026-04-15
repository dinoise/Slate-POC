"""Incident routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..core.provider_registry import ProviderDep
from ..schemas.incident import IncidentCreate, IncidentRead, IncidentUpdate
from ..services.incident_service import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_incident_service(db: DBSession) -> IncidentService:
    """Get incident service dependency."""
    return IncidentService(db)


IncidentServiceDep = Annotated[IncidentService, Depends(get_incident_service)]


@router.post(
    "/",
    response_model=IncidentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create new incident",
)
async def create_incident(
    data: IncidentCreate,
    service: IncidentServiceDep,
    provider: ProviderDep,
) -> IncidentRead:
    """Create a new incident and schedule automatic adjuster assignment."""
    incident = await service.create_incident(data, provider=provider)
    return IncidentRead.model_validate(incident)


@router.get(
    "/",
    response_model=list[IncidentRead],
    summary="Get all incidents",
)
async def get_incidents(
    service: IncidentServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status_filter: str | None = Query(None, alias="status"),
) -> list[IncidentRead]:
    """Get all incidents with optional filtering."""
    incidents = await service.get_all_incidents(
        skip=skip,
        limit=limit,
        status=status_filter,
    )
    return [IncidentRead.model_validate(inc) for inc in incidents]


@router.get(
    "/{incident_id}",
    response_model=IncidentRead,
    summary="Get incident by ID",
)
async def get_incident(
    incident_id: int,
    service: IncidentServiceDep,
) -> IncidentRead:
    """Get a specific incident by ID."""
    incident = await service.get_incident(incident_id)
    return IncidentRead.model_validate(incident)


@router.patch(
    "/{incident_id}",
    response_model=IncidentRead,
    summary="Update incident",
)
async def update_incident(
    incident_id: int,
    data: IncidentUpdate,
    service: IncidentServiceDep,
) -> IncidentRead:
    """Update an incident."""
    incident = await service.update_incident(incident_id, data)
    return IncidentRead.model_validate(incident)


@router.delete(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Cancel all active incidents",
)
async def cancel_all_incidents(
    service: IncidentServiceDep,
) -> dict:
    """Cancel all active incidents and release their assigned adjusters.

    Used by the demo reset flow (load initial state).
    """
    cancelled = await service.cancel_all_active()
    return {"cancelled": cancelled}


@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete incident",
)
async def delete_incident(
    incident_id: int,
    service: IncidentServiceDep,
) -> None:
    """Soft-delete an incident (sets status to cancelled)."""
    await service.soft_delete_incident(incident_id)


@router.get(
    "/nearby/",
    response_model=list[IncidentRead],
    summary="Get nearby incidents",
)
async def get_nearby_incidents(
    service: IncidentServiceDep,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=100),
    limit: int = Query(100, ge=1, le=1000),
) -> list[IncidentRead]:
    """Get incidents near a location."""
    incidents = await service.get_nearby_incidents(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
        limit=limit,
    )
    return [IncidentRead.model_validate(inc) for inc in incidents]
