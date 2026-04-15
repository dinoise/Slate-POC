"""Business logic for DemandPrediction queries."""

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ValidationError
from ..models.demand_prediction import DemandPrediction
from ..repositories.demand_prediction_repository import DemandPredictionRepository

MAX_LIMIT = 5000


class DemandPredictionService:
    """Service for demand prediction queries."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize service."""
        self.repository = DemandPredictionRepository(db)

    async def get_available_slots(self) -> list[dict]:
        """Return all (dia_semana_num, hora_num) pairs that have predictions."""
        return await self.repository.get_available_slots()

    async def get_by_slot_and_bbox(
        self,
        hora_num: int,
        dia_semana_num: int,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        limit: int = MAX_LIMIT,
    ) -> list[DemandPrediction]:
        """
        Get demand predictions for a time slot within a bounding box.

        Args:
            hora_num: Hour of day (0-23)
            dia_semana_num: Day of week (0-6)
            min_lat: South bound latitude
            min_lon: West bound longitude
            max_lat: North bound latitude
            max_lon: East bound longitude
            limit: Max results (capped at MAX_LIMIT)

        Returns:
            List of DemandPrediction instances

        Raises:
            AppException: If bbox coordinates are invalid
        """
        if min_lat >= max_lat:
            raise ValidationError("min_lat must be less than max_lat")
        if min_lon >= max_lon:
            raise ValidationError("min_lon must be less than max_lon")

        limit = min(limit, MAX_LIMIT)

        return await self.repository.get_by_slot_and_bbox(
            hora_num=hora_num,
            dia_semana_num=dia_semana_num,
            min_lat=min_lat,
            min_lon=min_lon,
            max_lat=max_lat,
            max_lon=max_lon,
            limit=limit,
        )
