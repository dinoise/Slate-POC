"""users_table_fk_and_notify_trigger

Revision ID: 568143275b2e
Revises: e7c681c66318
Create Date: 2026-04-10 01:37:29.004923

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "568143275b2e"
down_revision: Union[str, None] = "e7c681c66318"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table (no geometry — plain op.create_table)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)

    # 2. Add reported_by_user_id FK to incidents (nullable — SET NULL on user delete)
    op.add_column(
        "incidents",
        sa.Column("reported_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_incidents_reported_by_user_id",
        "incidents",
        "users",
        ["reported_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_incidents_reported_by_user_id",
        "incidents",
        ["reported_by_user_id"],
        unique=False,
    )

    # 3. pg_notify trigger on assignments — fires on INSERT and UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_assignment_event()
        RETURNS TRIGGER AS $$
        DECLARE
            payload TEXT;
        BEGIN
            payload := json_build_object(
                'assignment_id', NEW.id,
                'adjuster_id',   NEW.adjuster_id,
                'incident_id',   NEW.incident_id,
                'status',        NEW.status,
                'event',         TG_OP
            )::text;
            PERFORM pg_notify('assignment_events', payload);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_assignment_notify
        AFTER INSERT OR UPDATE ON assignments
        FOR EACH ROW EXECUTE FUNCTION notify_assignment_event();
    """)


def downgrade() -> None:
    # Reverse order: trigger → function → FK/col → users table
    op.execute("DROP TRIGGER IF EXISTS trg_assignment_notify ON assignments;")
    op.execute("DROP FUNCTION IF EXISTS notify_assignment_event();")

    op.drop_index("ix_incidents_reported_by_user_id", table_name="incidents")
    op.drop_constraint(
        "fk_incidents_reported_by_user_id", "incidents", type_="foreignkey"
    )
    op.drop_column("incidents", "reported_by_user_id")

    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_table("users")
