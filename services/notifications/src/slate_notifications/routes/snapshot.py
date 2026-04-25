"""Snapshot endpoint — notifications service.

Route:
    GET /notifications/snapshot/observatory
        Returns the current state of all active assignments as a list of
        ``EnrichedAssignmentEvent`` objects — the same shape as individual
        SSE events from ``/notifications/stream/observatory``.

Design:
    The snapshot endpoint is the complement to the SSE stream: the client
    calls it once on mount to populate the map with all currently active
    assignments, then subscribes to the SSE stream for incremental delta
    updates.

    Sharing the same ``EnrichedAssignmentEvent`` schema with the stream
    guarantees that the client can use the same parser for both responses.

    ``Enricher.build_from_enriched`` is called for each row so the
    construction logic is never duplicated between the stream and snapshot
    paths.

Auth:
    Same ``verify_google_token`` dependency as the stream routes.
    The snapshot is a regular REST endpoint — the token is sent in the
    standard ``Authorization: Bearer <token>`` header (not ``?token=``).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import verify_google_token
from ..core.database import get_db
from ..repositories.assignment_repository import AssignmentRepository
from ..schemas.notification import EnrichedAssignmentEvent
from ..services.enricher import Enricher

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get(
    "/snapshot/observatory",
    dependencies=[Depends(verify_google_token)],
    response_model=list[EnrichedAssignmentEvent],
    summary="Snapshot of all active assignments",
    description=(
        "Returns all currently active assignments as ``EnrichedAssignmentEvent`` "
        "objects — the same shape as individual SSE events from "
        "``/notifications/stream/observatory``. "
        "Call once on mount to populate the observatory map before opening "
        "the SSE stream."
    ),
)
async def observatory_snapshot(
    db: AsyncSession = Depends(get_db),
) -> list[EnrichedAssignmentEvent]:
    """Fetch all active assignments enriched with incident and adjuster data.

    Args:
        db: Async DB session injected by FastAPI.

    Returns:
        List of ``EnrichedAssignmentEvent`` — one per active assignment,
        ordered by ``assigned_at`` descending.  Empty list when no active
        assignments exist.
    """
    repo = AssignmentRepository(db)
    rows = await repo.get_all_active_enriched()
    logger.info("Observatory snapshot: returning %d active assignments", len(rows))
    return [Enricher.build_from_enriched(row) for row in rows]
