"""Routes for resource positioning scenarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..core import DBSession
from ..repositories.resource_position_repository import ResourcePositionRepository
from ..schemas.resource_position import ResourcePositionRead
from ..services.resource_position_service import ResourcePositionService

router = APIRouter(prefix="/adjuster-positions", tags=["adjuster-positions"])


def get_service(db: DBSession) -> ResourcePositionService:
    return ResourcePositionService(ResourcePositionRepository(db))


ServiceDep = Annotated[ResourcePositionService, Depends(get_service)]


def _to_read(pos) -> ResourcePositionRead:
    data = ResourcePositionRead.model_validate(pos)
    if pos.resource:
        data.resource_name = pos.resource.full_name
    return data


@router.get(
    "/scenarios",
    response_model=list[str],
    summary="List available positioning scenarios",
)
async def list_scenarios(service: ServiceDep) -> list[str]:
    return await service.list_scenarios()


@router.get(
    "/scenarios/{scenario}",
    response_model=list[ResourcePositionRead],
    summary="Get resource positions for a scenario",
)
async def get_scenario(scenario: str, service: ServiceDep) -> list[ResourcePositionRead]:
    positions = await service.get_scenario(scenario)
    if not positions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario}' not found or has no positions",
        )
    return [_to_read(p) for p in positions]
