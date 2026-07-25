"""Service for ResourcePosition business logic."""

from ..repositories.resource_position_repository import ResourcePositionRepository


class ResourcePositionService:
    def __init__(self, repo: ResourcePositionRepository) -> None:
        self.repo = repo

    async def get_scenario(self, scenario: str):
        return await self.repo.get_by_scenario(scenario)

    async def list_scenarios(self) -> list[str]:
        return await self.repo.list_scenarios()
