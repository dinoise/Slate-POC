"""one_active_assignment_per_incident

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-21 12:00:00.000000

Problem:
    The optimizer can create two assignments for the same incident if two
    concurrent requests both read the incident as 'pending' before either
    commit updates it to 'assigned'.  This results in duplicate notifications
    and two assignments pointing to the same incident.

Fix:
    A partial unique index that allows at most one non-terminal assignment
    per incident at any given time.  Terminal statuses ('cancelled',
    'completed') are excluded so that an incident can be re-assigned after
    a cancellation.

    This is a DB-level guard — it makes the optimizer idempotent regardless
    of application-layer timing.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sanitise existing data: if an incident already has more than one active
    # assignment (created by the race condition this migration fixes), cancel
    # all duplicates except the one with the highest id (most recent).
    op.execute("""
        UPDATE assignments
        SET status = 'cancelled'
        WHERE status NOT IN ('cancelled', 'completed')
          AND id NOT IN (
              SELECT MAX(id)
              FROM assignments
              WHERE status NOT IN ('cancelled', 'completed')
              GROUP BY incident_id
          )
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_one_active_assignment_per_incident
        ON assignments (incident_id)
        WHERE status NOT IN ('cancelled', 'completed')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_one_active_assignment_per_incident")
