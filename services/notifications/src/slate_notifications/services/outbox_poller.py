"""Outbox fallback poller — durability guarantee for missed pg_notify events.

Responsibilities (single):
    Periodically drain the ``assignment_events`` outbox table and broadcast
    any events that were not delivered via pg_notify (e.g. because the
    listener was reconnecting at the time of the DB commit).

Why this exists:
    ``pg_notify`` is best-effort: if no listener is connected at the exact
    moment of ``PERFORM pg_notify(...)`` inside the trigger, the message is
    lost forever.  The PostgreSQL trigger writes each event to the
    ``assignment_events`` outbox table *in the same transaction*, so no event
    is ever truly lost — this poller recovers them within ``POLL_INTERVAL``
    seconds.

Deduplication:
    Events are marked ``processed_at = now()`` after broadcast.  The
    ``get_unprocessed()`` query uses ``SELECT ... FOR UPDATE SKIP LOCKED``
    so that a second instance (if ever deployed) cannot double-process the
    same batch.

Usage (managed by ``main.py`` lifespan):
    >>> task = asyncio.create_task(poll(session_maker, broadcaster))
    >>> task.cancel()          # on shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket

from sqlalchemy.ext.asyncio import async_sessionmaker

from ..repositories.dispatch_event_repository import DispatchEventRepository
from .broadcaster import NotificationBroadcaster

logger = logging.getLogger(__name__)

POLL_INTERVAL = 30  # seconds between drain passes
_HOSTNAME = socket.gethostname()


async def poll(
    session_maker: async_sessionmaker,
    broadcaster: NotificationBroadcaster,
) -> None:
    """Run the outbox drain loop indefinitely.

    Every ``POLL_INTERVAL`` seconds, fetches up to 100 unprocessed rows
    from ``assignment_events``, broadcasts each one via the broadcaster,
    and marks them as processed.  Rows that fail to broadcast are skipped
    and retried on the next pass.

    Args:
        session_maker: SQLAlchemy async session factory (from ``core/database.py``).
        broadcaster: Singleton broadcaster that delivers payloads to SSE clients.

    Yields:
        Long-running coroutine.  Exits only on ``CancelledError``.
    """
    while True:
        try:
            await asyncio.sleep(POLL_INTERVAL)
            await _drain_once(session_maker, broadcaster)
        except asyncio.CancelledError:
            logger.info("Outbox poller shutting down")
            break
        except Exception:
            logger.exception("Outbox poller error; will retry in %ds", POLL_INTERVAL)


async def _drain_once(
    session_maker: async_sessionmaker,
    broadcaster: NotificationBroadcaster,
) -> None:
    """Execute a single drain pass — fetch, broadcast, mark processed.

    Separated from the loop so it can be called directly in tests.

    Args:
        session_maker: SQLAlchemy async session factory.
        broadcaster: Broadcaster instance.
    """
    async with session_maker() as session:
        repo = DispatchEventRepository(session)
        async with session.begin():
            events = await repo.get_unprocessed()
            if not events:
                return

            processed_ids: list[int] = []
            for event in events:
                try:
                    payload = (
                        event.payload
                        if isinstance(event.payload, dict)
                        else json.loads(event.payload)
                    )
                    task_id = int(payload["task_id"]) if payload.get("task_id") else None
                    await broadcaster.broadcast_to_all_channels(event.resource_id, task_id, payload)
                    processed_ids.append(event.id)
                except Exception:
                    logger.exception("Outbox: failed to broadcast event id=%d", event.id)

            if processed_ids:
                await repo.mark_processed(processed_ids, _HOSTNAME)
                logger.info(
                    "Outbox: broadcast and marked %d event(s) as processed",
                    len(processed_ids),
                )
