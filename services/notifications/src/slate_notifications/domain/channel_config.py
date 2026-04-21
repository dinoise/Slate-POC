"""Channel routing configuration — maps pg_notify channels to broadcaster channels.

Adding a new PostgreSQL trigger channel requires only a new ``ChannelConfig``
entry in ``CHANNEL_CONFIGS``.  No changes to the listener loop, broadcaster,
or route handlers are needed.

Example — adding a hypothetical ``adjuster_events`` channel that fans out to
both an ADJUSTER_STATUS channel and a REGION channel:

    1. Create the trigger in a new Alembic migration.

    2. Add ``Channel`` members::

        class Channel(str, Enum):
            ADJUSTER_STATUS = "adjuster_status"
            REGION          = "region"

    3. Add a ``ChannelConfig`` entry here::

        ChannelConfig(
            pg_channel="adjuster_events",
            targets=[
                ChannelTarget(channel=Channel.ADJUSTER_STATUS, id_field="adjuster_id"),
                ChannelTarget(channel=Channel.REGION,          id_field="region_id"),
            ],
        ),

    The listener registers the new pg_notify channel automatically on next
    restart — no other files need to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .channels import Channel


@dataclass(frozen=True, slots=True)
class ChannelTarget:
    """A single fan-out destination for a pg_notify payload.

    Attributes:
        channel: Broadcaster ``Channel`` bucket to deliver the payload to.
        id_field: JSON key in the pg_notify payload whose value is the
            entity ID used as the broadcaster routing key.
    """

    channel: Channel
    id_field: str


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Routing rules for a single pg_notify channel.

    Each entry maps one PostgreSQL LISTEN channel name to one or more
    broadcaster ``ChannelTarget`` destinations.  The listener iterates
    ``targets`` and delivers the payload to every matching subscriber.

    Attributes:
        pg_channel: Name of the PostgreSQL LISTEN channel — must match the
            first argument of ``pg_notify()`` in the trigger function.
        targets: One or more fan-out destinations.  Must contain at least
            one entry; order is not significant.
    """

    pg_channel: str
    targets: list[ChannelTarget] = field(default_factory=list)


# ── Active channel configurations ────────────────────────────────────────────
#
# Each entry registers one pg_notify LISTEN channel.
# Add a new entry here (+ Channel member + DB trigger) to support a new
# event source — no other code changes required.

CHANNEL_CONFIGS: list[ChannelConfig] = [
    ChannelConfig(
        pg_channel="assignment_events",
        targets=[
            ChannelTarget(channel=Channel.ADJUSTER, id_field="adjuster_id"),
            ChannelTarget(channel=Channel.INCIDENT, id_field="incident_id"),
        ],
    ),
    # Future example:
    # ChannelConfig(
    #     pg_channel="adjuster_events",
    #     targets=[
    #         ChannelTarget(channel=Channel.ADJUSTER_STATUS, id_field="adjuster_id"),
    #     ],
    # ),
]
