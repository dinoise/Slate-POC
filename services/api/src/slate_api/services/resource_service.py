"""Business logic for Resource operations."""

from geoalchemy2.functions import ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.enums import BUSY_RESOURCE_STATUSES, ResourceStatus
from ..core.exceptions import ConflictError, NotFoundError
from ..models import Resource
from ..repositories.resource_repository import ResourceRepository
from ..schemas.resource import ResourceCreate, ResourceRead, ResourceUpdate


class ResourceService:
    """Service for Resource business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = ResourceRepository(db)

    async def create_resource(self, data: ResourceCreate) -> Resource:
        existing = await self.repository.get_by_external_id(data.external_id)
        if existing:
            raise ConflictError(f"Resource with external_id '{data.external_id}' already exists")

        home_location = ST_MakePoint(data.home_longitude, data.home_latitude)

        return await self.repository.create(
            external_id=data.external_id,
            first_name=data.first_name,
            last_name=data.last_name,
            email=data.email,
            phone=data.phone,
            home_latitude=data.home_latitude,
            home_longitude=data.home_longitude,
            home_location=home_location,
            skills=data.skills,
            max_cases_per_day=data.max_cases_per_day,
            is_active=True,
            status=ResourceStatus.AVAILABLE,
        )

    async def get_resource(self, resource_id: int) -> Resource:
        resource = await self.repository.get_by_id(resource_id)
        if not resource:
            raise NotFoundError(f"Resource with id {resource_id} not found")
        return resource

    async def get_all_resources(
        self,
        skip: int = 0,
        limit: int = 100,
        is_active: bool | None = None,
    ) -> tuple[list[Resource], int]:
        filters = {}
        if is_active is not None:
            filters["is_active"] = is_active
        return await self.repository.get_all_paginated(skip=skip, limit=limit, **filters)

    async def update_resource(self, resource_id: int, data: ResourceUpdate) -> Resource:
        await self.get_resource(resource_id)

        updated = await self.repository.update(resource_id, **data.model_dump(exclude_unset=True))
        if not updated:
            raise NotFoundError(f"Resource with id {resource_id} not found")
        return updated

    async def soft_delete_resource(self, resource_id: int) -> Resource:
        await self.get_resource(resource_id)
        updated = await self.repository.update(
            resource_id, is_active=False, status=ResourceStatus.OFFLINE
        )
        if not updated:
            raise NotFoundError(f"Resource with id {resource_id} not found")
        return updated

    async def get_available_resources(
        self,
        latitude: float | None = None,
        longitude: float | None = None,
        radius_km: float = 50.0,
        skills: list[str] | None = None,
        limit: int = 100,
        scenario: str = "initial",
    ) -> list[ResourceRead]:
        """Get available resources enriched with current position from resource_positions."""
        if skills:
            plain_resources = await self.repository.get_by_skills(skills, limit)
            return [ResourceRead.model_validate(r) for r in plain_resources]

        rows = await self.repository.get_available(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            limit=limit,
            scenario=scenario,
        )

        result = []
        for resource, cur_lat, cur_lon in rows:
            read = ResourceRead.model_validate(resource)
            read.current_latitude = cur_lat
            read.current_longitude = cur_lon
            result.append(read)
        return result

    async def reset_all_to_available(self) -> int:
        """Reset all busy/en_route/on_site resources back to available."""
        reset = 0
        for s in BUSY_RESOURCE_STATUSES:
            resources = await self.repository.get_all(limit=1000, status=s, is_active=True)
            for resource in resources:
                await self.repository.update(resource.id, status=ResourceStatus.AVAILABLE)
                reset += 1
        return reset
