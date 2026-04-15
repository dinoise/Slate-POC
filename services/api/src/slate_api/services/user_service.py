"""Business logic for User operations."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import ConflictError, NotFoundError
from ..models.user import User
from ..repositories.user_repository import UserRepository
from ..schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for User operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = UserRepository(db)

    async def create_user(self, data: UserCreate) -> User:
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise ConflictError(f"User with email '{data.email}' already exists")
        return await self.repository.create(
            external_id=str(uuid.uuid4()),
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
        )

    async def get_user(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if not user:
            raise NotFoundError(f"User {user_id} not found")
        return user

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_user(self, user_id: int, data: UserUpdate) -> User:
        await self.get_user(user_id)
        updated = await self.repository.update(user_id, **data.model_dump(exclude_unset=True))
        if not updated:
            raise NotFoundError(f"User {user_id} not found")
        return updated

    async def delete_user(self, user_id: int) -> None:
        await self.get_user(user_id)
        await self.repository.delete(user_id)
