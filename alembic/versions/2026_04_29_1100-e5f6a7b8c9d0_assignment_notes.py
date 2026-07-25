"""assignment_notes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-29 11:00:00.000000

Adds assignment_notes table for AI agent field notes on assignments.
Used by the field_guide sub-agent via the log_field_note tool.
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assignment_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by_agent", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("agent_type", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["assignments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_assignment_notes_assignment_id",
        "assignment_notes",
        ["assignment_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_assignment_notes_assignment_id", table_name="assignment_notes")
    op.drop_table("assignment_notes")
