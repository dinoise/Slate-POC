"""In-memory SSE broadcaster — routes payloads to subscriber queues.

Responsibilities (single):
    Route an incoming payload to every asyncio.Queue subscribed to a
    given ``(Channel, entity_id)`` pair, and to every global subscriber
    of the channel.

Subscription model:
    Entity-specific: ``subscribe(channel, entity_id=<int>)``
        Queue receives only events for that entity.
        Keyed as ``(Channel, int)`` in ``_subscribers``.

    Global: ``subscribe(channel, entity_id=None)``
        Queue receives ALL events published on that channel, regardless
        of entity_id.  Keyed by ``Channel`` in ``_global_subscribers``.
        Used by ``Channel.OBSERVATORY`` to receive every assignment event.

    This models the same distinction found in production pub/sub systems:
    NATS subject wildcards, Mercure ``topic=*``, Socket.io namespace broadcast.

This module intentionally does NOT contain:
    - The pg_notify LISTEN loop  →  see ``services/listener.py``
    - The outbox fallback poller →  see ``services/outbox_poller.py``
    - DB queries or enrichment   →  see ``services/enricher.py``

Example:
    >>> broadcaster = NotificationBroadcaster()
    >>> queue = broadcaster.subscribe(Channel.ADJUSTER, entity_id=5)
    >>> obs_queue = broadcaster.subscribe(Channel.OBSERVATORY, entity_id=None)
    >>> await broadcaster.broadcast(Channel.ADJUSTER, adjuster_id=5, payload={})
    # → queue receives payload (entity match)
    # → obs_queue receives payload (global subscriber)
"""

from __future__ import annotations

import asyncio

from ..core.logging import get_logger
from ..domain.channels import Channel

logger = get_logger(__name__)


class NotificationBroadcaster:
    """Routes notification payloads to per-subscriber asyncio queues.

    Maintains two registries:
    - ``_subscribers``: entity-specific subscriptions keyed by ``(Channel, int)``
    - ``_global_subscribers``: global subscriptions keyed by ``Channel`` —
      these receive every event published on their channel regardless of entity_id.

    Thread-safety: designed for a single-process asyncio event loop.
    All methods are safe to call from coroutines without locking.
    """

    def __init__(self) -> None:
        self._subscribers: dict[tuple[Channel, int], set[asyncio.Queue[dict]]] = {}
        self._global_subscribers: dict[Channel, set[asyncio.Queue[dict]]] = {}

    # ── Subscription lifecycle ────────────────────────────────────────────────

    def subscribe(self, channel: Channel, entity_id: int | None) -> asyncio.Queue[dict]:
        """Register a new subscriber and return its dedicated queue.

        Args:
            channel: The channel to subscribe to.
            entity_id: The specific entity ID to watch (adjuster PK, incident PK, …).
                Pass ``None`` to receive ALL events on this channel regardless of
                entity — used by global channels like ``Channel.OBSERVATORY``.

        Returns:
            A fresh ``asyncio.Queue`` that will receive matching payloads.
        """
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
        if entity_id is None:
            self._global_subscribers.setdefault(channel, set()).add(queue)
            logger.debug("SSE global subscriber added — channel=%s", channel.value)
        else:
            key = (channel, entity_id)
            self._subscribers.setdefault(key, set()).add(queue)
            logger.debug("SSE subscriber added — channel=%s entity_id=%d", channel.value, entity_id)
        return queue

    def unsubscribe(
        self,
        channel: Channel,
        entity_id: int | None,
        queue: asyncio.Queue[dict],
    ) -> None:
        """Remove a subscriber queue.

        Safe to call even if the queue is no longer registered (no-op).

        Args:
            channel: Channel the queue was subscribed to.
            entity_id: Entity ID the queue was subscribed to, or ``None`` for
                global subscribers.
            queue: The queue instance returned by :meth:`subscribe`.
        """
        if entity_id is None:
            bucket = self._global_subscribers.get(channel)
            if bucket:
                bucket.discard(queue)
                if not bucket:
                    del self._global_subscribers[channel]
            logger.debug("SSE global subscriber removed — channel=%s", channel.value)
        else:
            key = (channel, entity_id)
            bucket = self._subscribers.get(key)
            if bucket:
                bucket.discard(queue)
                if not bucket:
                    del self._subscribers[key]
            logger.debug(
                "SSE subscriber removed — channel=%s entity_id=%d", channel.value, entity_id
            )

    # ── Broadcasting ─────────────────────────────────────────────────────────

    async def broadcast(
        self,
        channel: Channel,
        entity_id: int,
        payload: dict,
    ) -> None:
        """Deliver a payload to entity-specific and global subscribers of ``channel``.

        Delivers to:
        1. All queues subscribed to ``(channel, entity_id)`` — entity-specific match.
        2. All queues subscribed globally to ``channel`` (``entity_id=None``) —
           global subscribers receive every event on the channel.

        Queues that are full receive a warning log and the event is dropped
        for that subscriber only — other subscribers are unaffected.

        Args:
            channel: Target channel.
            entity_id: The concrete entity ID of the event source.
            payload: Raw dict to deliver (typically the pg_notify JSON payload).
        """
        queues: list[asyncio.Queue[dict]] = []

        # Entity-specific subscribers
        entity_key = (channel, entity_id)
        queues.extend(self._subscribers.get(entity_key, set()))

        # Global subscribers — receive every event on this channel
        queues.extend(self._global_subscribers.get(channel, set()))

        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full — dropping event for channel=%s entity_id=%d",
                    channel.value,
                    entity_id,
                )

    async def broadcast_global(self, payload: dict) -> None:
        """Deliver a payload to ALL global subscribers across every channel.

        Global subscribers are those registered with ``entity_id=None`` via
        :meth:`subscribe`.  They receive every event regardless of which
        channel or entity triggered it.

        This is the equivalent of ``io.emit()`` in Socket.io or ``PUBLISH *``
        in Mercure — a distinct delivery path from entity-specific fan-out,
        with no dependency on any particular channel or entity_id.

        Args:
            payload: Raw dict to deliver to all global subscriber queues.
        """
        for channel, queues in self._global_subscribers.items():
            for queue in list(queues):
                try:
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    logger.warning(
                        "Queue full — dropping global event for channel=%s", channel.value
                    )

    async def broadcast_to_all_channels(
        self,
        adjuster_id: int,
        incident_id: int | None,
        payload: dict,
    ) -> None:
        """Convenience: broadcast to ADJUSTER, INCIDENT, and all global subscribers.

        Called by the pg_notify listener and the outbox poller, which receive
        a single payload and need to fan it out to all relevant subscribers.

        Entity-specific delivery is handled by :meth:`broadcast`.
        Global delivery (e.g. OBSERVATORY) is handled by :meth:`broadcast_global`
        — no entity_id needed, no coupling to specific global channels.

        Args:
            adjuster_id: Routes to ``Channel.ADJUSTER`` entity subscribers.
            incident_id: Routes to ``Channel.INCIDENT`` entity subscribers if not None.
            payload: Payload dict to deliver to all matching queues.
        """
        await self.broadcast(Channel.ADJUSTER, adjuster_id, payload)
        if incident_id is not None:
            await self.broadcast(Channel.INCIDENT, incident_id, payload)
        await self.broadcast_global(payload)


# Singleton instance — created by main.py lifespan and shared across modules.
broadcaster = NotificationBroadcaster()
