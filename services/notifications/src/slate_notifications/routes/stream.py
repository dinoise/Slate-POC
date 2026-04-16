"""SSE stream endpoint — notifications service."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from ..notifier import broadcaster

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


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
                    yield f"event: assignment\ndata: {json.dumps(payload)}\n\n"
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
