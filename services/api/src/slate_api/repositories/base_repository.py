"""Generic base repository with CRUD operations."""

from typing import Any, Generic, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic repository with common CRUD operations."""

    def __init__(self, db: AsyncSession, model: type[T]) -> None:
        """
        Initialize repository.

        Args:
            db: Database session
            model: SQLAlchemy model class
        """
        self.db = db
        self.model = model

    async def get_by_id(self, id: int) -> T | None:
        """
        Get record by ID.

        Args:
            id: Record ID

        Returns:
            Model instance or None if not found
        """
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> list[T]:
        """
        Get all records with optional filtering and pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            **filters: Additional filter criteria

        Returns:
            List of model instances
        """
        query = select(self.model)

        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create(self, **data: Any) -> T:
        """
        Create new record.

        Args:
            **data: Model attributes

        Returns:
            Created model instance
        """
        instance = self.model(**data)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def update(self, id: int, **data: Any) -> T | None:
        """
        Update existing record.

        Args:
            id: Record ID
            **data: Attributes to update

        Returns:
            Updated model instance or None if not found
        """
        stmt = update(self.model).where(self.model.id == id).values(**data).returning(self.model)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()

    async def delete(self, id: int) -> bool:
        """
        Delete record.

        Args:
            id: Record ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0

    async def get_all_paginated(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any,
    ) -> tuple[list[T], int]:
        """Get records with pagination and total count in a single round-trip."""
        count_query = select(func.count()).select_from(self.model)
        items_query = select(self.model)

        for key, value in filters.items():
            if hasattr(self.model, key):
                condition = getattr(self.model, key) == value
                count_query = count_query.where(condition)
                items_query = items_query.where(condition)

        total = (await self.db.execute(count_query)).scalar_one()
        items = list((await self.db.execute(items_query.offset(skip).limit(limit))).scalars().all())
        return items, total

    async def count(self, **filters: Any) -> int:
        """Count records matching optional filters."""
        query = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def exists(self, id: int) -> bool:
        """
        Check if record exists.

        Args:
            id: Record ID

        Returns:
            True if exists, False otherwise
        """
        query = select(self.model.id).where(self.model.id == id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
