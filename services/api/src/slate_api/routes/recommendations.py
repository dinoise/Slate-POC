"""Routes for positioning recommendations."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..core import DBSession
from ..schemas.recommendation import RecommendationRequest, RecommendationResponse
from ..services.positioning_service import PositioningService

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def get_service(db: DBSession) -> PositioningService:
    return PositioningService(db)


ServiceDep = Annotated[PositioningService, Depends(get_service)]


@router.post(
    "/",
    response_model=RecommendationResponse,
    summary="Generate greedy positioning recommendations",
)
async def generate_recommendations(
    req: RecommendationRequest,
    service: ServiceDep,
) -> RecommendationResponse:
    """Run the greedy positioning algorithm for a given time slot.

    - Reads adjuster positions from the specified `scenario`.
    - Loads demand predictions for `hora_num` × `dia_semana_num`.
    - Returns recommendations (adjusters to move + destination hex).
    - If `save_as_scenario` is set, persists the result as a new scenario.
    """
    try:
        return await service.recommend(req)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
