"""
Cloud Run Job entrypoint — daily demand prediction refresh.

Runs LightGBM inference to populate the demand_predictions table.
Scheduled via Cloud Scheduler (2am daily).

Usage:
    DATABASE_URL=postgresql+asyncpg://... uv run python -m slate_jobs.demand_refresh
"""

from __future__ import annotations

import asyncio
import logging

from .config import settings

logging.basicConfig(
    level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logger = logging.getLogger(__name__)


async def run_demand_refresh() -> None:
    """
    Refresh demand predictions for the next 24 hours.

    TODO (Phase 2):
    - Load LightGBM model from Cloud Storage or baked into image
    - Generate predictions per H3 hex cell, hour, day_of_week
    - Truncate demand_predictions and insert new rows
    """
    logger.info("Starting demand refresh job (stub)")
    # Placeholder — model inference will go here
    logger.info("Demand refresh job completed (stub — no predictions written)")


if __name__ == "__main__":
    asyncio.run(run_demand_refresh())
