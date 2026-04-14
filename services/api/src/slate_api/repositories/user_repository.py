"""Repository for User model."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import User
from .base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_external_id(self, external_id: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.external_id == external_id)
        )
        return result.scalar_one_or_none()
