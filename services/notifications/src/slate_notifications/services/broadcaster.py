"""pg_notify listener and SSE broadcaster — notifications service."""

from __future__ import annotations

import asyncio
import json
import logging
import socket

import asyncpg
from fastapi import FastAPI

from ..core.config import settings
from ..core.database import async_session_maker
from ..repositories.assignment_event_repository import AssignmentEventRepository

logger = logging.getLogger(__name__)

CHANNEL = "assignment_events"
_HOSTNAME = socket.gethostname()
_OUTBOX_POLL_INTERVAL = 30  # seconds


class NotificationBroadcaster:
    """
    SSE subscriber queues — indexed by adjuster_id AND incident_id.

    Adjuster streams: subscribe(adjuster_id=X)
    Reporter streams: subscribe(incident_id=X)

    broadcast() routes to both buckets automatically using the payload fields.
    """

    def __init__(self) -> None:
        self._by_adjuster: dict[int, set[asyncio.Queue[dict]]] = {}
        self._by_incident: dict[int, set[asyncio.Queue[dict]]] = {}

    def subscribe(
        self,
        *,
        adjuster_id: int | None = None,
        incident_id: int | None = None,
    ) -> asyncio.Queue[dict]:
        if adjuster_id is None and incident_id is None:
            raise ValueError("adjuster_id or incident_id required")
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
        if adjuster_id is not None:
            self._by_adjuster.setdefault(adjuster_id, set()).add(queue)
            logger.debug("SSE subscriber added for adjuster %d", adjuster_id)
        if incident_id is not None:
            self._by_incident.setdefault(incident_id, set()).add(queue)
            logger.debug("SSE subscriber added for incident %d", incident_id)
        return queue

    def unsubscribe(
        self,
        queue: asyncio.Queue[dict],
        *,
        adjuster_id: int | None = None,
        incident_id: int | None = None,
    ) -> None:
        if adjuster_id is not None:
            bucket = self._by_adjuster.get(adjuster_id)
            if bucket:
                bucket.discard(queue)
                if not bucket:
                    del self._by_adjuster[adjuster_id]
            logger.debug("SSE subscriber removed for adjuster %d", adjuster_id)
        if incident_id is not None:
            bucket = self._by_incident.get(incident_id)
            if bucket:
                bucket.discard(queue)
                if not bucket:
                    del self._by_incident[incident_id]
            logger.debug("SSE subscriber removed for incident %d", incident_id)

    async def broadcast(self, adjuster_id: int, payload: dict) -> None:
        incident_id: int | None = payload.get("incident_id")
        targets: list[asyncio.Queue[dict]] = [
            *self._by_adjuster.get(adjuster_id, set()),
            *(self._by_incident.get(incident_id, set()) if incident_id else []),
        ]
        for queue in targets:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full for adjuster %d / incident %s — dropping event",
                    adjuster_id,
                    incident_id,
                )


broadcaster = NotificationBroadcaster()
_listener_conn: asyncpg.Connection | None = None
_listener_task: asyncio.Task | None = None
_outbox_task: asyncio.Task | None = None


async def _listen_loop(dsn: str) -> None:
    global _listener_conn
    backoff = 1

    while True:
        try:
            _listener_conn = await asyncpg.connect(dsn)
            backoff = 1

            async def on_notification(
                conn: asyncpg.Connection,
                pid: int,
                channel: str,
                payload: str,
            ) -> None:
                try:
                    data = json.loads(payload)
                    adjuster_id = int(data["adjuster_id"])
                    await broadcaster.broadcast(adjuster_id, data)
                except Exception:
                    logger.exception("Error processing pg_notify payload: %s", payload)

            await _listener_conn.add_listener(CHANNEL, on_notification)
            logger.info("pg_notify LISTEN established on channel '%s'", CHANNEL)

            while not _listener_conn.is_closed():
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("pg_notify listener error; reconnecting in %ds", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            if _listener_conn and not _listener_conn.is_closed():
                await _listener_conn.close()
            _listener_conn = None


async def _outbox_poll_loop() -> None:
    """Periodically drain unprocessed outbox events and broadcast them via SSE."""
    while True:
        try:
            await asyncio.sleep(_OUTBOX_POLL_INTERVAL)
            async with async_session_maker() as session:
                repo = AssignmentEventRepository(session)
                async with session.begin():
                    events = await repo.get_unprocessed()
                    if not events:
                        continue
                    processed_ids: list[int] = []
                    for event in events:
                        try:
                            payload = (
                                event.payload
                                if isinstance(event.payload, dict)
                                else json.loads(event.payload)
                            )
                            await broadcaster.broadcast(event.adjuster_id, payload)
                            processed_ids.append(event.id)
                        except Exception:
                            logger.exception("Outbox: failed to broadcast event id=%d", event.id)
                    if processed_ids:
                        await repo.mark_processed(processed_ids, _HOSTNAME)
                        logger.info("Outbox: broadcast and marked %d events", len(processed_ids))
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Outbox poller error; will retry in %ds", _OUTBOX_POLL_INTERVAL)


async def start_listener(app: FastAPI) -> None:
    global _listener_task, _outbox_task
    dsn = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    _listener_task = asyncio.create_task(_listen_loop(dsn), name="pg_notify_listener")
    _outbox_task = asyncio.create_task(_outbox_poll_loop(), name="outbox_poller")
    logger.info("pg_notify listener and outbox poller tasks started")


async def stop_listener(app: FastAPI) -> None:
    global _listener_task, _listener_conn, _outbox_task
    for task in (_listener_task, _outbox_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _listener_task = None
    _outbox_task = None
    if _listener_conn and not _listener_conn.is_closed():
        await _listener_conn.close()
    logger.info("pg_notify listener and outbox poller stopped")
