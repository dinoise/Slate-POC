"""Channel definitions for the notification broadcaster.

A Channel identifies the dimension along which subscribers listen.
Adding a new subscription type (e.g. REGION, REPORTER) only requires
adding a new member here — no changes to the broadcaster are needed.

Example:
    >>> broadcaster.subscribe(Channel.ADJUSTER, adjuster_id)
    >>> broadcaster.subscribe(Channel.INCIDENT, incident_id)
"""

from enum import StrEnum


class Channel(StrEnum):
    """Broadcast channels supported by the notification service.

    Each value identifies a subscription key type. The broadcaster
    routes payloads to all queues registered under ``(channel, entity_id)``.

    Attributes:
        ADJUSTER: Events routed to a specific adjuster (adjuster app SSE stream).
        INCIDENT: Events routed to a specific incident (reporter app SSE stream).
    """

    ADJUSTER = "adjuster"
    INCIDENT = "incident"
    OBSERVATORY = "observatory"  # global channel — all assignment events, no entity filter
