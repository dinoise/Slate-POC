"""Service for AdjusterPosition business logic."""

from ..repositories.adjuster_position_repository import AdjusterPositionRepository


class AdjusterPositionService:
    def __init__(self, repo: AdjusterPositionRepository) -> None:
        self.repo = repo

    async def get_scenario(self, scenario: str):
        return await self.repo.get_by_scenario(scenario)

    async def list_scenarios(self) -> list[str]:
        return await self.repo.list_scenarios()
