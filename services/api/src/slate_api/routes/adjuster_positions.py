"""Routes for adjuster positioning scenarios."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..core import DBSession
from ..repositories.adjuster_position_repository import AdjusterPositionRepository
from ..schemas.adjuster_position import AdjusterPositionRead
from ..services.adjuster_position_service import AdjusterPositionService

router = APIRouter(prefix="/adjuster-positions", tags=["adjuster-positions"])


def get_service(db: DBSession) -> AdjusterPositionService:
    return AdjusterPositionService(AdjusterPositionRepository(db))


ServiceDep = Annotated[AdjusterPositionService, Depends(get_service)]


def _to_read(pos) -> AdjusterPositionRead:
    data = AdjusterPositionRead.model_validate(pos)
    if pos.adjuster:
        data.adjuster_name = pos.adjuster.full_name
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
    response_model=list[AdjusterPositionRead],
    summary="Get adjuster positions for a scenario",
)
async def get_scenario(scenario: str, service: ServiceDep) -> list[AdjusterPositionRead]:
    positions = await service.get_scenario(scenario)
    if not positions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{scenario}' not found or has no positions",
        )
    return [_to_read(p) for p in positions]
