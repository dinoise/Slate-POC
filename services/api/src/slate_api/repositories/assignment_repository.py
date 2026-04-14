"""Repository for Assignment model."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Assignment
from .base_repository import BaseRepository


class AssignmentRepository(BaseRepository[Assignment]):
    """Repository for Assignment operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize repository."""
        super().__init__(db, Assignment)

    async def get_by_incident(
        self,
        incident_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments for an incident.

        Args:
            incident_id: Incident ID
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = (
            select(Assignment)
            .where(Assignment.incident_id == incident_id)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_adjuster(
        self,
        adjuster_id: int,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments for an adjuster.

        Args:
            adjuster_id: Adjuster ID
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = (
            select(Assignment)
            .where(Assignment.adjuster_id == adjuster_id)
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_adjuster(
        self,
        adjuster_id: int,
    ) -> list[Assignment]:
        """
        Get active assignments for an adjuster.

        Args:
            adjuster_id: Adjuster ID

        Returns:
            List of active assignments
        """
        query = select(Assignment).where(
            Assignment.adjuster_id == adjuster_id,
            Assignment.status.in_(["assigned", "accepted", "en_route", "arrived", "in_progress"]),
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_status(
        self,
        status: str,
        limit: int = 100,
    ) -> list[Assignment]:
        """
        Get assignments by status.

        Args:
            status: Assignment status
            limit: Maximum results

        Returns:
            List of assignments
        """
        query = select(Assignment).where(Assignment.status == status).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
