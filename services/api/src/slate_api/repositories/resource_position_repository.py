"""Repository for ResourcePosition queries."""

from sqlalchemy import delete, distinct, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import ResourcePosition
from .base_repository import BaseRepository


class ResourcePositionRepository(BaseRepository[ResourcePosition]):
    """Repository for ResourcePosition with scenario-based queries."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, ResourcePosition)

    async def get_by_scenario(self, scenario: str) -> list[ResourcePosition]:
        """Get all resource positions for a given scenario, with resource loaded."""
        query = (
            select(ResourcePosition)
            .options(selectinload(ResourcePosition.resource))
            .where(ResourcePosition.scenario == scenario)
            .order_by(ResourcePosition.resource_id)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_scenarios(self) -> list[str]:
        """Return distinct scenario names."""
        query = select(distinct(ResourcePosition.scenario)).order_by(ResourcePosition.scenario)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_scenario(self, scenario: str) -> int:
        """Delete all rows for a scenario. Returns deleted row count."""
        result = await self.db.execute(
            delete(ResourcePosition)
            .where(ResourcePosition.scenario == scenario)
            .returning(ResourcePosition.id)
        )
        await self.db.commit()
        return len(result.fetchall())

    async def bulk_insert(self, positions: list[ResourcePosition]) -> list[ResourcePosition]:
        """Insert a list of ResourcePosition objects and return them."""
        self.db.add_all(positions)
        await self.db.commit()
        for p in positions:
            await self.db.refresh(p)
        return positions
