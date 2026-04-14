"""Demand prediction routes."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core import DBSession
from ..schemas.demand_prediction import DemandPredictionRead
from ..services.demand_prediction_service import MAX_LIMIT, DemandPredictionService

router = APIRouter(prefix="/demand-predictions", tags=["demand-predictions"])


def get_demand_prediction_service(db: DBSession) -> DemandPredictionService:
    """Get demand prediction service dependency."""
    return DemandPredictionService(db)


DemandPredictionServiceDep = Annotated[
    DemandPredictionService, Depends(get_demand_prediction_service)
]


@router.get(
    "/available-slots",
    response_model=list[dict],
    summary="Get available time slots that have demand predictions",
)
async def get_available_slots(service: DemandPredictionServiceDep) -> list[dict]:
    """Return all (dia_semana_num, hora_num) pairs that have demand predictions."""
    return await service.get_available_slots()


@router.get(
    "/",
    response_model=list[DemandPredictionRead],
    summary="Get demand predictions by time slot and viewport bbox",
)
async def get_demand_predictions(
    service: DemandPredictionServiceDep,
    hora_num: int = Query(..., ge=0, le=23, description="Hour of day (0-23)"),
    dia_semana_num: int = Query(..., ge=0, le=6, description="Day of week (0=Mon, 6=Sun)"),
    bbox: str = Query(
        ...,
        description="Bounding box as 'min_lat,min_lon,max_lat,max_lon'",
        example="19.2,-99.4,19.6,-99.0",
    ),
    limit: int = Query(MAX_LIMIT, ge=1, le=MAX_LIMIT),
) -> list[DemandPredictionRead]:
    """
    Get demand predictions for a time slot filtered by viewport bounding box.

    bbox format: min_lat,min_lon,max_lat,max_lon
    """
    # Parse bbox
    try:
        parts = bbox.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must have exactly 4 comma-separated values")
        min_lat, min_lon, max_lat, max_lon = (float(p) for p in parts)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid bbox: {exc}",
        ) from exc

    predictions = await service.get_by_slot_and_bbox(
        hora_num=hora_num,
        dia_semana_num=dia_semana_num,
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        limit=limit,
    )
    return [DemandPredictionRead.model_validate(p) for p in predictions]
