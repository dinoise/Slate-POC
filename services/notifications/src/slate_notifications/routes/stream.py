"""SSE stream endpoints — notifications service.

Routes:
    GET /notifications/stream/adjusters/{adjuster_id}
        Subscribe to assignment events for a specific adjuster.
        Consumed by the adjuster app.

    GET /notifications/stream/incidents/{incident_id}
        Subscribe to assignment events for a specific incident.
        Consumed by the reporter app to track assignment progress.

    GET /notifications/stream/observatory
        Subscribe to all assignment events (no entity filter).
        Consumed by the admin observatory dashboard.

Design:
    Route handlers are intentionally thin — each handler:
    1. Subscribes to the broadcaster.
    2. Returns a ``StreamingResponse`` wrapping ``_event_generator()``.
    3. Unsubscribes on disconnect (inside the generator's ``finally`` block).

    Enrichment (DB JOIN to add incident fields) is delegated to
    ``services.enricher.Enricher``, which is injected via ``Depends``.

Auth:
    Google token verified via ``verify_google_token`` dependency.
    The native ``EventSource`` API does not support custom headers, so
    the token is accepted as a ``?token=`` query parameter in addition
    to the standard ``Authorization`` header.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import verify_google_token
from ..core.database import get_db
from ..domain.channels import Channel
from ..services.broadcaster import broadcaster
from ..services.enricher import Enricher

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_KEEPALIVE_INTERVAL = 15  # seconds


async def _event_generator(
    request: Request,
    channel: Channel,
    entity_id: int | None,
    enricher: Enricher,
) -> object:
    """Yield SSE-formatted strings for as long as the client is connected.

    Sends an initial ``connected`` event as a handshake, then waits on
    the broadcaster queue.  A keepalive comment (``': keepalive'``) is
    sent every ``_KEEPALIVE_INTERVAL`` seconds to prevent proxy timeouts.

    The queue is automatically unsubscribed in the ``finally`` block,
    regardless of how the generator exits (client disconnect, server
    shutdown, or exception).

    Args:
        request: FastAPI request — used to detect client disconnection.
        channel: Broadcaster channel this stream is subscribed to.
        entity_id: Entity ID (adjuster PK or incident PK) to watch, or
            ``None`` for global channels that receive all events (e.g. OBSERVATORY).
        enricher: Enricher instance for DB-joining raw payloads.

    Yields:
        SSE-formatted strings: ``event: <name>\\ndata: <json>\\n\\n``
        or ``': keepalive\\n\\n'`` comments.
    """
    queue = broadcaster.subscribe(channel, entity_id)
    try:
        yield "event: connected\ndata: {}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_INTERVAL)
                event = await enricher.enrich(payload)
                yield f"event: assignment\ndata: {json.dumps(event.model_dump())}\n\n"
            except TimeoutError:
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        broadcaster.unsubscribe(channel, entity_id, queue)
        if entity_id is None:
            logger.info("SSE stream closed — channel=%s (global)", channel.value)
        else:
            logger.info("SSE stream closed — channel=%s entity_id=%d", channel.value, entity_id)


@router.get(
    "/stream/adjusters/{adjuster_id}",
    dependencies=[Depends(verify_google_token)],
    summary="SSE stream for an adjuster",
    description=(
        "Subscribe to real-time assignment events for a specific adjuster. "
        "Delivers ``assignment`` events whenever an assignment is created or "
        "its status changes. Used by the adjuster app."
    ),
)
async def adjuster_stream(
    adjuster_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Open an SSE stream for a specific adjuster.

    Args:
        adjuster_id: PK of the adjuster to subscribe to.
        request: Injected by FastAPI — used for disconnect detection.
        db: Async DB session injected by FastAPI.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` media type.
    """
    enricher = Enricher(db)
    return StreamingResponse(
        _event_generator(request, Channel.ADJUSTER, adjuster_id, enricher),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get(
    "/stream/incidents/{incident_id}",
    dependencies=[Depends(verify_google_token)],
    summary="SSE stream for an incident",
    description=(
        "Subscribe to real-time assignment events for a specific incident. "
        "Delivers ``assignment`` events as the assigned adjuster progresses "
        "through their workflow. Used by the reporter app."
    ),
)
async def incident_stream(
    incident_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Open an SSE stream for a specific incident.

    Args:
        incident_id: PK of the incident to subscribe to.
        request: Injected by FastAPI — used for disconnect detection.
        db: Async DB session injected by FastAPI.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` media type.
    """
    enricher = Enricher(db)
    return StreamingResponse(
        _event_generator(request, Channel.INCIDENT, incident_id, enricher),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get(
    "/stream/observatory",
    dependencies=[Depends(verify_google_token)],
    summary="SSE stream for the admin observatory",
    description=(
        "Subscribe to all assignment events across the entire fleet. "
        "Delivers ``assignment`` events for every adjuster and incident — "
        "no entity filter. Used by the admin observatory dashboard."
    ),
)
async def observatory_stream(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Open a global SSE stream for the admin observatory.

    Receives every assignment event regardless of adjuster or incident.
    Subscribes with ``entity_id=None`` — the broadcaster delivers all
    events published on any channel to global subscribers.

    Args:
        request: Injected by FastAPI — used for disconnect detection.
        db: Async DB session injected by FastAPI.

    Returns:
        A ``StreamingResponse`` with ``text/event-stream`` media type.
    """
    enricher = Enricher(db)
    return StreamingResponse(
        _event_generator(request, Channel.OBSERVATORY, None, enricher),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
