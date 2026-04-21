"""SSE stream endpoint — notifications service."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import verify_google_token
from ..core.database import get_db
from ..repositories.assignment_repository import AssignmentRepository, EnrichedAssignment
from ..services.broadcaster import broadcaster

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


async def _enrich(payload: dict, db: AsyncSession) -> dict:
    """Join assignment + incident data for the SSE payload using SQLAlchemy ORM.

    Falls back to the raw payload if the DB lookup fails.
    """
    try:
        repo = AssignmentRepository(db)
        enriched: EnrichedAssignment | None = await repo.get_enriched(int(payload["assignment_id"]))
        if enriched is None:
            return payload

        return {
            "assignment_id": enriched.assignment_id,
            "adjuster_id": enriched.adjuster_id,
            "incident_id": enriched.incident_id,
            "status": enriched.status,
            "distance_km": enriched.distance_km,
            "travel_time_minutes": enriched.travel_time_minutes,
            "assigned_at": enriched.assigned_at.isoformat() if enriched.assigned_at else None,
            "route_polyline": enriched.route_polyline,
            "route_provider": enriched.route_provider,
            "route_distance_m": enriched.route_distance_m,
            "route_duration_s": enriched.route_duration_s,
            "incident_type": enriched.incident_type,
            "severity": enriched.severity,
            "description": enriched.description,
            "address": enriched.address,
            "latitude": enriched.latitude,
            "longitude": enriched.longitude,
        }
    except Exception:
        logger.exception(
            "Enrichment failed for assignment %s — forwarding raw payload",
            payload.get("assignment_id"),
        )
        return payload


@router.get("/stream", dependencies=[Depends(verify_google_token)])
async def notification_stream(
    request: Request,
    db: AsyncSession = Depends(get_db),
    adjuster_id: int = Query(..., gt=0, description="Adjuster ID to subscribe to"),
) -> StreamingResponse:
    """SSE stream for a specific adjuster."""
    queue = broadcaster.subscribe(adjuster_id=adjuster_id)

    async def event_generator():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    enriched = await _enrich(payload, db)
                    yield f"event: assignment\ndata: {json.dumps(enriched)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(queue, adjuster_id=adjuster_id)
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


@router.get("/stream/incident", dependencies=[Depends(verify_google_token)])
async def incident_stream(
    request: Request,
    db: AsyncSession = Depends(get_db),
    incident_id: int = Query(..., gt=0, description="Incident ID to subscribe to"),
) -> StreamingResponse:
    """SSE stream for a reporter tracking a specific incident."""
    queue = broadcaster.subscribe(incident_id=incident_id)

    async def event_generator():
        try:
            yield "event: connected\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    enriched = await _enrich(payload, db)
                    yield f"event: assignment\ndata: {json.dumps(enriched)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            broadcaster.unsubscribe(queue, incident_id=incident_id)
            logger.info("SSE stream closed for incident %d", incident_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
