"""Repository for DemandPrediction geo queries."""

from geoalchemy2.functions import ST_MakeEnvelope, ST_Within
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.demand_prediction import DemandPrediction
from .base_repository import BaseRepository


class DemandPredictionRepository(BaseRepository[DemandPrediction]):
    """Repository for DemandPrediction with bbox spatial filtering."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(db, DemandPrediction)

    async def get_available_slots(self) -> list[dict]:
        """Return all (dia_semana_num, hora_num) pairs that have predictions."""
        query = (
            select(DemandPrediction.dia_semana_num, DemandPrediction.hora_num)
            .group_by(DemandPrediction.dia_semana_num, DemandPrediction.hora_num)
            .order_by(DemandPrediction.dia_semana_num, DemandPrediction.hora_num)
        )
        result = await self.db.execute(query)
        return [{"dia_semana_num": r[0], "hora_num": r[1]} for r in result.all()]

    async def get_by_slot(
        self,
        hora_num: int,
        dia_semana_num: int,
        limit: int = 5000,
    ) -> list[DemandPrediction]:
        """Get demand predictions for a time slot (no bbox filter — returns all hexagons)."""
        query = (
            select(DemandPrediction)
            .where(
                DemandPrediction.hora_num == hora_num,
                DemandPrediction.dia_semana_num == dia_semana_num,
            )
            .order_by(DemandPrediction.pred_abs.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_slot_and_bbox(
        self,
        hora_num: int,
        dia_semana_num: int,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
        limit: int = 5000,
    ) -> list[DemandPrediction]:
        """
        Get demand predictions for a time slot filtered by bounding box.

        Args:
            hora_num: Hour of day (0-23)
            dia_semana_num: Day of week (0-6)
            min_lat: Minimum latitude (south bound)
            min_lon: Minimum longitude (west bound)
            max_lat: Maximum latitude (north bound)
            max_lon: Maximum longitude (east bound)
            limit: Maximum number of results

        Returns:
            List of DemandPrediction instances ordered by pred_abs desc
        """
        # PostGIS ST_MakeEnvelope uses (xmin=lon, ymin=lat, xmax=lon, ymax=lat, srid)
        envelope = ST_MakeEnvelope(min_lon, min_lat, max_lon, max_lat, 4326)
        query = (
            select(DemandPrediction)
            .where(
                DemandPrediction.hora_num == hora_num,
                DemandPrediction.dia_semana_num == dia_semana_num,
                ST_Within(DemandPrediction.location, envelope),
            )
            .order_by(DemandPrediction.pred_abs.desc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
