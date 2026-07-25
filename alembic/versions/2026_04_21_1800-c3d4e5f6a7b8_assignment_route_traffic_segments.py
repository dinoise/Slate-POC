"""assignment_route_traffic_segments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-21 18:00:00.000000

Adds a JSONB column to store traffic segment data (speed classifications per
polyline segment) alongside the existing route geometry columns.

Traffic segments are computed by the routing provider (e.g. Google Routes API
with TRAFFIC_AWARE) at assignment time and stored here so they can be included
in SSE payloads without an extra round-trip to the routing API.

Schema:
    route_traffic_segments JSONB — nullable list of
        {start_index: int, end_index: int, speed: "NORMAL"|"SLOW"|"TRAFFIC_JAM"}
"""

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("route_traffic_segments", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assignments", "route_traffic_segments")
