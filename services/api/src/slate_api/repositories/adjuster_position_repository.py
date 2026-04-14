"""Repository for AdjusterPosition queries."""
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.adjuster_position import AdjusterPosition
from .base_repository import BaseRepository


class AdjusterPositionRepository(BaseRepository[AdjusterPosition]):
    """Repository for AdjusterPosition with scenario-based queries."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, AdjusterPosition)

    async def get_by_scenario(self, scenario: str) -> list[AdjusterPosition]:
        """Get all adjuster positions for a given scenario, with adjuster loaded."""
        query = (
            select(AdjusterPosition)
            .options(selectinload(AdjusterPosition.adjuster))
            .where(AdjusterPosition.scenario == scenario)
            .order_by(AdjusterPosition.adjuster_id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_scenarios(self) -> list[str]:
        """Return distinct scenario names."""
        from sqlalchemy import distinct

        query = select(distinct(AdjusterPosition.scenario)).order_by(AdjusterPosition.scenario)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_scenario(self, scenario: str) -> int:
        """Delete all rows for a scenario. Returns deleted row count."""
        result = await self.db.execute(
            delete(AdjusterPosition)
            .where(AdjusterPosition.scenario == scenario)
            .returning(AdjusterPosition.id)
        )
        await self.db.commit()
        return len(result.fetchall())

    async def bulk_insert(self, positions: list[AdjusterPosition]) -> list[AdjusterPosition]:
        """Insert a list of AdjusterPosition objects and return them."""
        self.db.add_all(positions)
        await self.db.commit()
        for p in positions:
            await self.db.refresh(p)
        return positions
