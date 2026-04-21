"""Unit tests for NotificationBroadcaster — no DB required."""

from __future__ import annotations

import asyncio

import pytest

from slate_notifications.domain.channels import Channel
from slate_notifications.services.broadcaster import NotificationBroadcaster


@pytest.mark.asyncio
async def test_subscribe_returns_queue() -> None:
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.ADJUSTER, 1)
    assert queue is not None
    assert isinstance(queue, asyncio.Queue)


@pytest.mark.asyncio
async def test_broadcast_delivers_to_adjuster_subscriber() -> None:
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.ADJUSTER, 42)

    payload = {"assignment_id": 1, "adjuster_id": 42, "incident_id": 10}
    await bc.broadcast(Channel.ADJUSTER, 42, payload)

    assert queue.get_nowait() == payload


@pytest.mark.asyncio
async def test_broadcast_does_not_deliver_to_other_adjuster() -> None:
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.ADJUSTER, 1)

    await bc.broadcast(Channel.ADJUSTER, 2, {"assignment_id": 99, "adjuster_id": 2})

    assert queue.empty()


@pytest.mark.asyncio
async def test_broadcast_delivers_to_incident_subscriber() -> None:
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.INCIDENT, 7)

    payload = {"assignment_id": 5, "adjuster_id": 3, "incident_id": 7}
    await bc.broadcast(Channel.INCIDENT, 7, payload)

    assert queue.get_nowait() == payload


@pytest.mark.asyncio
async def test_unsubscribe_removes_queue() -> None:
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.ADJUSTER, 5)
    bc.unsubscribe(Channel.ADJUSTER, 5, queue)

    await bc.broadcast(Channel.ADJUSTER, 5, {"assignment_id": 1, "adjuster_id": 5})
    assert queue.empty()


@pytest.mark.asyncio
async def test_multiple_subscribers_same_channel() -> None:
    bc = NotificationBroadcaster()
    q1 = bc.subscribe(Channel.ADJUSTER, 10)
    q2 = bc.subscribe(Channel.ADJUSTER, 10)

    payload = {"assignment_id": 7, "adjuster_id": 10}
    await bc.broadcast(Channel.ADJUSTER, 10, payload)

    assert q1.get_nowait() == payload
    assert q2.get_nowait() == payload


@pytest.mark.asyncio
async def test_broadcast_to_all_channels_fans_out() -> None:
    """broadcast_to_all_channels must deliver to both ADJUSTER and INCIDENT queues."""
    bc = NotificationBroadcaster()
    adj_queue = bc.subscribe(Channel.ADJUSTER, 3)
    inc_queue = bc.subscribe(Channel.INCIDENT, 9)

    payload = {"assignment_id": 11, "adjuster_id": 3, "incident_id": 9}
    await bc.broadcast_to_all_channels(adjuster_id=3, incident_id=9, payload=payload)

    assert adj_queue.get_nowait() == payload
    assert inc_queue.get_nowait() == payload


@pytest.mark.asyncio
async def test_broadcast_to_all_channels_no_incident() -> None:
    """broadcast_to_all_channels with incident_id=None must not raise."""
    bc = NotificationBroadcaster()
    adj_queue = bc.subscribe(Channel.ADJUSTER, 1)

    payload = {"assignment_id": 2, "adjuster_id": 1}
    await bc.broadcast_to_all_channels(adjuster_id=1, incident_id=None, payload=payload)

    assert adj_queue.get_nowait() == payload


@pytest.mark.asyncio
async def test_queue_full_drops_event() -> None:
    """A full queue must not raise — the event is silently dropped."""
    bc = NotificationBroadcaster()
    queue = bc.subscribe(Channel.ADJUSTER, 3)

    for i in range(50):
        await queue.put({"i": i})

    # Must not raise even though queue is full
    await bc.broadcast(Channel.ADJUSTER, 3, {"assignment_id": 99})
    assert queue.full()
