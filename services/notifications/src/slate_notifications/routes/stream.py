"""SSE stream endpoint — notifications service."""

from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ..config import settings
from ..notifier import broadcaster

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

_ENRICH_QUERY = """
    SELECT
        a.id            AS assignment_id,
        a.adjuster_id,
        a.incident_id,
        a.status,
        a.distance_km,
        a.travel_time_minutes,
        a.assigned_at,
        i.incident_type,
        i.severity,
        i.description,
        i.address,
        i.latitude,
        i.longitude
    FROM assignments a
    JOIN incidents   i ON i.id = a.incident_id
    WHERE a.id = $1
"""


async def _enrich(payload: dict) -> dict:
    """
    Join assignment + incident data for the SSE payload.

    Uses a short-lived asyncpg connection — we intentionally avoid SQLAlchemy
    here to keep this service dependency-free from the ORM layer.
    Falls back to the raw payload if the DB lookup fails.
    """
    dsn = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    try:
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow(_ENRICH_QUERY, int(payload["assignment_id"]))
        finally:
            await conn.close()

        if not row:
            return payload

        return {
            "assignment_id": row["assignment_id"],
            "adjuster_id": row["adjuster_id"],
            "incident_id": row["incident_id"],
            "status": row["status"],
            "distance_km": float(row["distance_km"]) if row["distance_km"] else None,
            "travel_time_minutes": row["travel_time_minutes"],
            "assigned_at": row["assigned_at"].isoformat() if row["assigned_at"] else None,
            "incident_type": row["incident_type"],
            "severity": row["severity"],
            "description": row["description"],
            "address": row["address"],
            "latitude": float(row["latitude"]) if row["latitude"] else None,
            "longitude": float(row["longitude"]) if row["longitude"] else None,
        }
    except Exception:
        logger.exception(
            "Enrichment failed for assignment %s — forwarding raw payload",
            payload.get("assignment_id"),
        )
        return payload


@router.get("/stream")
async def notification_stream(
    request: Request,
    adjuster_id: int = Query(..., gt=0, description="Adjuster ID to subscribe to"),
) -> StreamingResponse:
    """SSE stream for a specific adjuster."""
    queue = broadcaster.subscribe(adjuster_id)

    async def event_generator():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    enriched = await _enrich(payload)
                    yield f"event: assignment\ndata: {json.dumps(enriched)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(adjuster_id, queue)
            logger.info("SSE stream closed for adjuster %d", adjuster_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
