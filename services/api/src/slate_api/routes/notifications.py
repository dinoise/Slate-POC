"""SSE notification endpoint — real-time assignment events for adjusters."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ..core.database import async_session_maker
from ..core.notifier import broadcaster
from ..repositories.assignment_repository import AssignmentRepository
from ..repositories.incident_repository import IncidentRepository

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


async def _enrich_event(data: dict) -> dict:
    """
    Fetch full assignment + incident details for the SSE payload.

    Uses a fresh DB session — the SSE generator outlives the request scope,
    so we cannot use the DBSession FastAPI dependency here.
    """
    async with async_session_maker() as db:
        assignment_repo = AssignmentRepository(db)
        incident_repo = IncidentRepository(db)

        assignment = await assignment_repo.get_by_id(int(data["assignment_id"]))
        incident = (
            await incident_repo.get_by_id(int(data["incident_id"]))
            if assignment
            else None
        )

        if not assignment or not incident:
            return data  # forward raw payload if lookup fails

        return {
            "assignment_id": assignment.id,
            "adjuster_id": assignment.adjuster_id,
            "incident_id": incident.id,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "description": incident.description,
            "address": incident.address,
            "latitude": incident.latitude,
            "longitude": incident.longitude,
            "distance_km": assignment.distance_km,
            "travel_time_minutes": assignment.travel_time_minutes,
            "status": assignment.status,
            "assigned_at": (
                assignment.assigned_at.isoformat() if assignment.assigned_at else None
            ),
        }


@router.get("/stream")
async def notification_stream(
    request: Request,
    adjuster_id: int = Query(..., gt=0, description="Adjuster ID to subscribe to"),
) -> StreamingResponse:
    """
    SSE stream for a specific adjuster.

    Opens a long-lived connection that forwards pg_notify assignment events
    as enriched SSE 'assignment' events.
    """
    queue = broadcaster.subscribe(adjuster_id)

    async def event_generator():
        try:
            yield "event: connected\ndata: {}\n\n"

            while True:
                if await request.is_disconnected():
                    break

                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    enriched = await _enrich_event(payload)
                    yield f"event: assignment\ndata: {json.dumps(enriched)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive comment — prevents nginx / browser idle timeout
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
