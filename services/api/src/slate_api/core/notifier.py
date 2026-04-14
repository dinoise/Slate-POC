"""pg_notify listener and SSE broadcaster for assignment events."""
from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
from fastapi import FastAPI

from .config import settings

logger = logging.getLogger(__name__)

CHANNEL = "assignment_events"


class NotificationBroadcaster:
    """
    Manages per-adjuster SSE subscriber queues.

    subscribe(adjuster_id) → Queue   — called when SSE connection opens
    unsubscribe(adjuster_id, queue)  — called in SSE generator finally block
    broadcast(adjuster_id, payload)  — called by pg_notify listener callback
    """

    def __init__(self) -> None:
        self._subscribers: dict[int, set[asyncio.Queue[dict]]] = {}

    def subscribe(self, adjuster_id: int) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
        self._subscribers.setdefault(adjuster_id, set()).add(queue)
        logger.debug(
            "SSE subscriber added for adjuster %d (total: %d)",
            adjuster_id,
            len(self._subscribers[adjuster_id]),
        )
        return queue

    def unsubscribe(self, adjuster_id: int, queue: asyncio.Queue[dict]) -> None:
        bucket = self._subscribers.get(adjuster_id)
        if bucket:
            bucket.discard(queue)
            if not bucket:
                del self._subscribers[adjuster_id]
        logger.debug("SSE subscriber removed for adjuster %d", adjuster_id)

    async def broadcast(self, adjuster_id: int, payload: dict) -> None:
        for queue in list(self._subscribers.get(adjuster_id, set())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full for adjuster %d — dropping event", adjuster_id
                )


# Module-level singletons
broadcaster = NotificationBroadcaster()
_listener_conn: asyncpg.Connection | None = None
_listener_task: asyncio.Task | None = None


async def _listen_loop(dsn: str) -> None:
    """
    Persistent asyncpg LISTEN loop with automatic reconnect on failure.
    Parses each pg_notify payload and fans it out to SSE subscribers.
    """
    global _listener_conn
    backoff = 1

    while True:
        try:
            _listener_conn = await asyncpg.connect(dsn)
            backoff = 1  # reset after successful connect

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
                    logger.exception(
                        "Error processing pg_notify payload: %s", payload
                    )

            await _listener_conn.add_listener(CHANNEL, on_notification)
            logger.info("pg_notify LISTEN established on channel '%s'", CHANNEL)

            # Keep-alive loop — asyncpg calls on_notification on each pg_notify
            while not _listener_conn.is_closed():
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception(
                "pg_notify listener error; reconnecting in %ds", backoff
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)
        finally:
            if _listener_conn and not _listener_conn.is_closed():
                await _listener_conn.close()
            _listener_conn = None


async def start_listener(app: FastAPI) -> None:
    """Start the pg_notify listener background task. Called in lifespan startup."""
    global _listener_task
    # asyncpg needs postgresql:// not postgresql+asyncpg://
    dsn = str(settings.DATABASE_URL).replace("postgresql+asyncpg://", "postgresql://")
    _listener_task = asyncio.create_task(_listen_loop(dsn), name="pg_notify_listener")
    logger.info("pg_notify listener task started")


async def stop_listener(app: FastAPI) -> None:
    """Cancel the listener task and close its connection. Called in lifespan shutdown."""
    global _listener_task, _listener_conn
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    if _listener_conn and not _listener_conn.is_closed():
        await _listener_conn.close()
    logger.info("pg_notify listener stopped")
