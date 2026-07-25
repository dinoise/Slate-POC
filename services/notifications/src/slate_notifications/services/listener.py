"""PostgreSQL LISTEN loop — pg_notify consumer.

Responsibilities (single):
    Maintain a long-lived asyncpg connection subscribed to all channels
    declared in ``domain.channel_config.CHANNEL_CONFIGS`` and forward
    each notification to the broadcaster.

Adding a new pg_notify channel:
    1. Create the DB trigger (Alembic migration).
    2. Add a ``Channel`` member to ``domain/channels.py``.
    3. Add a ``ChannelConfig`` entry to ``domain/channel_config.py``.

    The listener picks up the new channel automatically on next restart —
    no changes to this file are needed.

This module does NOT:
    - Know about SSE clients or HTTP
    - Perform DB enrichment             →  see ``enricher.py``
    - Handle the outbox fallback        →  see ``outbox_poller.py``

The LISTEN connection is intentionally separate from the SQLAlchemy
async pool: pools are designed for short transactional work, while a
LISTEN connection must remain open indefinitely.

Usage (managed by ``main.py`` lifespan):
    >>> task = asyncio.create_task(listen(dsn, broadcaster))
    >>> task.cancel()    # on shutdown
"""

from __future__ import annotations

import asyncio
import json
import logging

import asyncpg

from ..domain.channel_config import CHANNEL_CONFIGS, ChannelConfig  # noqa: F401
from .broadcaster import NotificationBroadcaster

logger = logging.getLogger(__name__)

_INITIAL_BACKOFF = 1  # seconds
_MAX_BACKOFF = 60  # seconds
_KEEPALIVE_SLEEP = 30  # seconds between connection health checks


def _make_handler(
    config: ChannelConfig,
    broadcaster: NotificationBroadcaster,
):
    """Return an asyncpg notification callback bound to a specific ChannelConfig.

    Each pg_notify channel gets its own handler closure so the routing rules
    (targets list) are captured at registration time — avoids late-binding
    issues when registering multiple handlers in a loop.

    Args:
        config: Routing rules for this pg_notify channel.
        broadcaster: Broadcaster instance that receives routed payloads.

    Returns:
        An async callable compatible with ``asyncpg.Connection.add_listener``.
    """

    async def _handler(
        _conn: asyncpg.Connection,
        _pid: int,
        _channel: str,
        raw: str,
    ) -> None:
        """Dispatch a pg_notify message to all configured broadcaster targets.

        Parses the JSON payload and iterates ``config.targets`` — each target
        specifies which ``Channel`` bucket to deliver to and which payload field
        holds the entity ID.  Targets whose ID field is absent or null in the
        payload are silently skipped.

        Malformed payloads are logged and discarded — they must not crash
        the listener loop.

        Args:
            _conn: asyncpg connection (unused).
            _pid: Postgres backend PID (unused).
            _channel: pg_notify channel name (unused — handler is already bound).
            raw: Raw JSON string emitted by the trigger.
        """
        try:
            data = json.loads(raw)
            for target in config.targets:
                raw_id = data.get(target.id_field)
                if raw_id is None:
                    continue
                await broadcaster.broadcast(target.channel, int(raw_id), data)
            # Deliver to all global subscribers (e.g. OBSERVATORY) — these
            # are not reachable via entity-specific targets above.
            await broadcaster.broadcast_global(data)
        except Exception:
            logger.exception(
                "Failed to process pg_notify on channel '%s': %.200s",
                config.pg_channel,
                raw,
            )

    return _handler


async def listen(dsn: str, broadcaster: NotificationBroadcaster) -> None:
    """Run the pg_notify LISTEN loop with exponential backoff reconnection.

    Connects to PostgreSQL via asyncpg, registers one listener per entry in
    ``CHANNEL_CONFIGS``, and idles until a notification arrives or the
    connection drops.

    On connection loss the loop waits ``backoff`` seconds and retries,
    doubling the delay up to ``_MAX_BACKOFF`` seconds.  On a clean
    ``asyncio.CancelledError`` (service shutdown) the loop exits and closes
    the connection.

    Args:
        dsn: PostgreSQL DSN.  SQLAlchemy ``postgresql+asyncpg://`` scheme is
            normalised to ``postgresql://`` automatically.
        broadcaster: Singleton broadcaster that receives dispatched payloads.
    """
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
    backoff = _INITIAL_BACKOFF
    conn: asyncpg.Connection | None = None

    while True:
        try:
            conn = await asyncpg.connect(dsn)
            backoff = _INITIAL_BACKOFF
            if not conn:
                logger.error("Can't connect to the following DSN: ", conn)
                return

            # Register one handler per configured channel — a single asyncpg
            # connection supports multiple concurrent LISTEN channels.
            for config in CHANNEL_CONFIGS:
                await conn.add_listener(
                    config.pg_channel,
                    _make_handler(config, broadcaster),
                )
                logger.info("pg_notify LISTEN established on channel '%s'", config.pg_channel)

            # Idle — asyncpg delivers notifications via the event loop.
            while not conn.is_closed():
                await asyncio.sleep(_KEEPALIVE_SLEEP)

        except asyncio.CancelledError:
            logger.info("pg_notify listener shutting down")
            break
        except Exception:
            logger.exception("pg_notify listener error; reconnecting in %ds", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _MAX_BACKOFF)
        finally:
            if conn and not conn.is_closed():
                await conn.close()
            conn = None
