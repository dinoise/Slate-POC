"""In-memory SSE broadcaster — routes payloads to subscriber queues.

Responsibilities (single):
    Route an incoming payload to every asyncio.Queue subscribed to a
    given ``(Channel, entity_id)`` pair.

This module intentionally does NOT contain:
    - The pg_notify LISTEN loop  →  see ``services/listener.py``
    - The outbox fallback poller →  see ``services/outbox_poller.py``
    - DB queries or enrichment   →  see ``services/enricher.py``

Architecture note:
    The broadcaster is keyed by ``(Channel, entity_id)`` rather than by
    separate ``adjuster_id`` / ``incident_id`` dicts.  Adding a new
    subscription type (e.g. ``Channel.REGION``) requires only a new
    ``Channel`` enum value — no changes here.

Example:
    >>> broadcaster = NotificationBroadcaster()
    >>> queue = broadcaster.subscribe(Channel.ADJUSTER, adjuster_id)
    >>> await broadcaster.broadcast(Channel.ADJUSTER, adjuster_id, payload)
    >>> broadcaster.unsubscribe(Channel.ADJUSTER, adjuster_id, queue)
"""

from __future__ import annotations

import asyncio

from ..core.logging import get_logger
from ..domain.channels import Channel

logger = get_logger(__name__)


class NotificationBroadcaster:
    """Routes notification payloads to per-subscriber asyncio queues.

    Each connected SSE client owns one ``asyncio.Queue``.  The broadcaster
    keeps a ``dict[(Channel, entity_id) -> set[Queue]]`` so that a single
    ``broadcast()`` call fans out to all clients watching the same entity.

    Thread-safety: designed for a single-process asyncio event loop.
    All methods are safe to call from coroutines without locking.
    """

    def __init__(self) -> None:
        self._subscribers: dict[tuple[Channel, int], set[asyncio.Queue[dict]]] = {}

    # ── Subscription lifecycle ────────────────────────────────────────────────

    def subscribe(self, channel: Channel, entity_id: int) -> asyncio.Queue[dict]:
        """Register a new subscriber and return its dedicated queue.

        Args:
            channel: The channel dimension to subscribe on.
            entity_id: The specific entity ID to watch (adjuster PK, incident PK, …).

        Returns:
            A fresh ``asyncio.Queue`` that will receive payloads broadcast
            to ``(channel, entity_id)``.
        """
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=50)
        key = (channel, entity_id)
        self._subscribers.setdefault(key, set()).add(queue)
        logger.debug("SSE subscriber added — channel=%s entity_id=%d", channel.value, entity_id)
        return queue

    def unsubscribe(
        self,
        channel: Channel,
        entity_id: int,
        queue: asyncio.Queue[dict],
    ) -> None:
        """Remove a subscriber queue.

        Safe to call even if the queue is no longer registered (no-op).

        Args:
            channel: Channel the queue was subscribed to.
            entity_id: Entity ID the queue was subscribed to.
            queue: The queue instance returned by :meth:`subscribe`.
        """
        key = (channel, entity_id)
        bucket = self._subscribers.get(key)
        if bucket:
            bucket.discard(queue)
            if not bucket:
                del self._subscribers[key]
        logger.debug("SSE subscriber removed — channel=%s entity_id=%d", channel.value, entity_id)

    # ── Broadcasting ─────────────────────────────────────────────────────────

    async def broadcast(
        self,
        channel: Channel,
        entity_id: int,
        payload: dict,
    ) -> None:
        """Deliver a payload to all queues subscribed to ``(channel, entity_id)``.

        Queues that are full receive a warning log and the event is dropped
        for that subscriber only — other subscribers are unaffected.

        Args:
            channel: Target channel.
            entity_id: Target entity ID.
            payload: Raw dict to deliver (typically the pg_notify JSON payload).
        """
        key = (channel, entity_id)
        targets = list(self._subscribers.get(key, set()))
        for queue in targets:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    "Queue full — dropping event for channel=%s entity_id=%d",
                    channel.value,
                    entity_id,
                )

    async def broadcast_to_all_channels(
        self,
        adjuster_id: int,
        incident_id: int | None,
        payload: dict,
    ) -> None:
        """Convenience: broadcast to ADJUSTER, INCIDENT, and OBSERVATORY channels.

        Called by the pg_notify listener and the outbox poller, which receive
        a single payload and need to fan it out to all relevant subscribers.

        Args:
            adjuster_id: Routes to ``Channel.ADJUSTER`` subscribers.
            incident_id: Routes to ``Channel.INCIDENT`` subscribers if not None.
            payload: Payload dict to deliver to all matching queues.
        """
        await self.broadcast(Channel.ADJUSTER, adjuster_id, payload)
        if incident_id is not None:
            await self.broadcast(Channel.INCIDENT, incident_id, payload)
        # OBSERVATORY uses entity_id=0 as the conventional "global" key
        await self.broadcast(Channel.OBSERVATORY, 0, payload)


# Singleton instance — created by main.py lifespan and shared across modules.
broadcaster = NotificationBroadcaster()
