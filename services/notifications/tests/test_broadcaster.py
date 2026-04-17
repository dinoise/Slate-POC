"""Unit tests for NotificationBroadcaster — no DB required."""

from __future__ import annotations

import asyncio

import pytest

from slate_notifications.notifier import NotificationBroadcaster


@pytest.mark.asyncio
async def test_subscribe_returns_queue() -> None:
    broadcaster = NotificationBroadcaster()
    queue = broadcaster.subscribe(1)
    assert queue is not None
    assert isinstance(queue, asyncio.Queue)


@pytest.mark.asyncio
async def test_broadcast_delivers_to_subscriber() -> None:
    broadcaster = NotificationBroadcaster()
    queue = broadcaster.subscribe(42)

    payload = {"assignment_id": 1, "adjuster_id": 42}
    await broadcaster.broadcast(42, payload)

    received = queue.get_nowait()
    assert received == payload


@pytest.mark.asyncio
async def test_broadcast_does_not_deliver_to_other_adjuster() -> None:
    broadcaster = NotificationBroadcaster()
    queue = broadcaster.subscribe(1)

    # Broadcast to adjuster 2 — adjuster 1's queue should remain empty
    await broadcaster.broadcast(2, {"assignment_id": 99, "adjuster_id": 2})

    assert queue.empty()


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue() -> None:
    broadcaster = NotificationBroadcaster()
    queue = broadcaster.subscribe(5)

    broadcaster.unsubscribe(5, queue)

    # Broadcast after unsubscribe — queue receives nothing
    await broadcaster.broadcast(5, {"assignment_id": 1, "adjuster_id": 5})
    assert queue.empty()


@pytest.mark.asyncio
async def test_multiple_subscribers_same_adjuster() -> None:
    broadcaster = NotificationBroadcaster()
    q1 = broadcaster.subscribe(10)
    q2 = broadcaster.subscribe(10)

    payload = {"assignment_id": 7, "adjuster_id": 10}
    await broadcaster.broadcast(10, payload)

    assert q1.get_nowait() == payload
    assert q2.get_nowait() == payload


@pytest.mark.asyncio
async def test_queue_full_drops_event() -> None:
    """A full queue should not raise — the event is silently dropped."""
    broadcaster = NotificationBroadcaster()
    queue = broadcaster.subscribe(3)

    # Fill the queue to capacity (maxsize=50)
    for i in range(50):
        await queue.put({"i": i})

    # This should not raise even though queue is full
    await broadcaster.broadcast(3, {"assignment_id": 99, "adjuster_id": 3})
    assert queue.full()
