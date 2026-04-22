"""
Cloud Run Job — batch assignment optimization.

Reads available adjusters and open incidents from DB, builds a cost matrix,
runs the OR-Tools assignment solver via slate_core, persists assignments,
and fires pg_notify so the notifications service picks up new assignments.

Invoked by the ``optimize`` console script installed via
``[project.scripts]`` in pyproject.toml.
"""

from __future__ import annotations

import asyncio
import json

import asyncpg
import numpy as np
from sqlalchemy import text

from slate_core.optimization.assignment_solver import solve
from slate_infra.logging import get_logger, setup_logging

from ..config import settings
from ..db import async_session_maker, engine

logger = get_logger(__name__)

NOTIFY_CHANNEL = "assignment_events"


async def _run() -> None:
    """
    Main optimization job.

    Reads available adjusters and open incidents from DB,
    builds cost matrix via adjuster positions, runs OR-Tools,
    persists assignments, and fires pg_notify for each.
    """
    logger.info("Starting optimization job")

    async with async_session_maker() as db:
        result = await db.execute(
            text("""
                SELECT a.id, ap.latitude, ap.longitude
                FROM adjusters a
                JOIN (
                    SELECT DISTINCT ON (adjuster_id) adjuster_id, latitude, longitude
                    FROM adjuster_positions
                    ORDER BY adjuster_id, recorded_at DESC
                ) ap ON ap.adjuster_id = a.id
                WHERE a.status = 'available'
            """)
        )
        adjusters = result.fetchall()

        result = await db.execute(
            text("""
                SELECT id, latitude, longitude
                FROM incidents
                WHERE status = 'open'
                ORDER BY created_at ASC
                LIMIT 500
            """)
        )
        incidents = result.fetchall()

    if not adjusters:
        logger.info("No available adjusters — nothing to optimize")
        return
    if not incidents:
        logger.info("No open incidents — nothing to optimize")
        return

    logger.info("%d adjusters, %d incidents", len(adjusters), len(incidents))

    adj_coords = np.array([[a.latitude, a.longitude] for a in adjusters])
    inc_coords = np.array([[i.latitude, i.longitude] for i in incidents])
    diff = adj_coords[:, None, :] - inc_coords[None, :, :]
    cost_matrix = np.sqrt((diff**2).sum(axis=2))

    results, unassigned = solve(cost_matrix)
    logger.info("%d assignments solved, %d incidents unassigned", len(results), len(unassigned))

    dsn = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    notify_conn = await asyncpg.connect(dsn)

    try:
        async with async_session_maker() as db:
            for r in results:
                adjuster = adjusters[r.adjuster_idx]
                incident = incidents[r.claim_idx]

                row = await db.execute(
                    text("""
                        INSERT INTO assignments (incident_id, adjuster_id, status, distance_km,
                                                travel_time_minutes, assigned_at)
                        VALUES (:incident_id, :adjuster_id, 'assigned', :dist_km, :travel_min, NOW())
                        RETURNING id
                    """),
                    {
                        "incident_id": incident.id,
                        "adjuster_id": adjuster.id,
                        "dist_km": round(r.travel_time_min * 0.8, 2),
                        "travel_min": round(r.travel_time_min, 1),
                    },
                )
                assignment_id = row.scalar_one()
                await db.execute(
                    text("UPDATE adjusters SET status = 'busy' WHERE id = :id"),
                    {"id": adjuster.id},
                )

                payload = json.dumps(
                    {
                        "assignment_id": assignment_id,
                        "adjuster_id": adjuster.id,
                        "incident_id": incident.id,
                        "status": "assigned",
                    }
                )
                await notify_conn.execute(f"SELECT pg_notify('{NOTIFY_CHANNEL}', $1)", payload)

            await db.commit()
    finally:
        await notify_conn.close()
        await engine.dispose()

    logger.info("Optimization job completed — %d assignments created", len(results))


def main() -> None:
    """Console script entrypoint — installed via [project.scripts]."""
    setup_logging(log_level=settings.effective_log_level, is_local=settings.is_local)
    asyncio.run(_run())
