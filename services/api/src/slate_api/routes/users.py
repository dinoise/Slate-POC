"""User routes — CRUD for incident reporters."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..core import DBSession
from ..schemas.user import UserCreate, UserRead, UserUpdate
from ..services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _get_service(db: DBSession) -> UserService:
    return UserService(db)


UserServiceDep = Annotated[UserService, Depends(_get_service)]


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(await service.create_user(data))


@router.get("/", response_model=list[UserRead])
async def get_users(
    service: UserServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> list[UserRead]:
    return [UserRead.model_validate(u) for u in await service.get_all_users(skip, limit)]


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(await service.get_user(user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(user_id: int, data: UserUpdate, service: UserServiceDep) -> UserRead:
    return UserRead.model_validate(await service.update_user(user_id, data))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, service: UserServiceDep) -> None:
    await service.delete_user(user_id)
