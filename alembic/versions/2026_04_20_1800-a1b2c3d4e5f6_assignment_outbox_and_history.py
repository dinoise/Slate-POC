"""assignment_outbox_and_history

Revision ID: a1b2c3d4e5f6
Revises: 568143275b2e
Create Date: 2026-04-20 18:00:00.000000

Adds:
- assignment_status_history: immutable audit trail of status transitions
- assignment_events: outbox table for reliable SSE delivery
- Unified trigger trg_assignment_change (replaces trg_assignment_notify)
- Route columns on assignments (polyline, provider, distance_m, duration_s)
- Fixed unique constraint on demand_predictions to include model_version
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "568143275b2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. assignment_status_history ─────────────────────────────────────────
    op.create_table(
        "assignment_status_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ash_assignment_id", "assignment_status_history", ["assignment_id"]
    )
    op.create_index(
        "ix_ash_changed_at",
        "assignment_status_history",
        [sa.text("changed_at DESC")],
    )

    # ── 2. assignment_events (outbox) ─────────────────────────────────────────
    op.create_table(
        "assignment_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("adjuster_id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("old_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ae_adjuster",
        "assignment_events",
        ["adjuster_id", sa.text("created_at DESC")],
    )
    # Partial index — only unprocessed events (used by outbox poller)
    op.execute(
        "CREATE INDEX ix_ae_unprocessed ON assignment_events(created_at) "
        "WHERE processed_at IS NULL"
    )

    # ── 3. Route columns on assignments ───────────────────────────────────────
    op.add_column("assignments", sa.Column("route_polyline", sa.Text(), nullable=True))
    op.add_column(
        "assignments", sa.Column("route_provider", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "assignments",
        sa.Column("route_fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "assignments", sa.Column("route_distance_m", sa.Integer(), nullable=True)
    )
    op.add_column(
        "assignments", sa.Column("route_duration_s", sa.Integer(), nullable=True)
    )

    # ── 4. Fix unique constraint on demand_predictions ────────────────────────
    op.drop_constraint("uq_demand_h3_slot", "demand_predictions", type_="unique")
    op.create_unique_constraint(
        "uq_demand_h3_predicted_model",
        "demand_predictions",
        ["h3_r8", "predicted_for", "model_version"],
    )

    # ── 5. Unified trigger (replaces trg_assignment_notify) ───────────────────
    op.execute("DROP TRIGGER IF EXISTS trg_assignment_notify ON assignments;")
    op.execute("DROP FUNCTION IF EXISTS notify_assignment_event();")

    op.execute("""
        CREATE OR REPLACE FUNCTION handle_assignment_change()
        RETURNS TRIGGER AS $$
        DECLARE
            v_payload  JSONB;
            v_evt_type VARCHAR(30);
        BEGIN
            -- Determine event type
            IF TG_OP = 'INSERT' THEN
                v_evt_type := 'assignment.created';
            ELSE
                v_evt_type := 'assignment.updated';
            END IF;

            -- Build snapshot payload
            v_payload := jsonb_build_object(
                'assignment_id',         NEW.id,
                'adjuster_id',           NEW.adjuster_id,
                'incident_id',           NEW.incident_id,
                'status',                NEW.status,
                'distance_km',           NEW.distance_km,
                'travel_time_minutes',   NEW.travel_time_minutes,
                'assigned_at',           NEW.assigned_at,
                'estimated_arrival_time',NEW.estimated_arrival_time,
                'route_polyline',        NEW.route_polyline,
                'route_distance_m',      NEW.route_distance_m,
                'route_duration_s',      NEW.route_duration_s,
                'event',                 v_evt_type
            );

            -- Insert into outbox (durable delivery guarantee)
            INSERT INTO assignment_events(
                assignment_id, adjuster_id, incident_id,
                event_type, old_status, new_status, payload
            ) VALUES (
                NEW.id, NEW.adjuster_id, NEW.incident_id,
                v_evt_type,
                CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE NULL END,
                NEW.status,
                v_payload
            );

            -- Insert into history only on status change (or initial insert)
            IF TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status THEN
                INSERT INTO assignment_status_history(
                    assignment_id, from_status, to_status
                ) VALUES (
                    NEW.id,
                    CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE NULL END,
                    NEW.status
                );
            END IF;

            -- pg_notify: best-effort immediate delivery (same as before)
            PERFORM pg_notify('assignment_events', v_payload::text);

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_assignment_change
        AFTER INSERT OR UPDATE ON assignments
        FOR EACH ROW EXECUTE FUNCTION handle_assignment_change();
    """)


def downgrade() -> None:
    # Remove new trigger and restore previous one
    op.execute("DROP TRIGGER IF EXISTS trg_assignment_change ON assignments;")
    op.execute("DROP FUNCTION IF EXISTS handle_assignment_change();")

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

    # Restore demand_predictions constraint
    op.drop_constraint(
        "uq_demand_h3_predicted_model", "demand_predictions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_demand_h3_slot", "demand_predictions", ["h3_r8", "predicted_for"]
    )

    # Remove route columns
    op.drop_column("assignments", "route_duration_s")
    op.drop_column("assignments", "route_distance_m")
    op.drop_column("assignments", "route_fetched_at")
    op.drop_column("assignments", "route_provider")
    op.drop_column("assignments", "route_polyline")

    # Drop outbox and history tables
    op.execute("DROP INDEX IF EXISTS ix_ae_unprocessed")
    op.drop_index("ix_ae_adjuster", table_name="assignment_events")
    op.drop_table("assignment_events")

    op.drop_index("ix_ash_changed_at", table_name="assignment_status_history")
    op.drop_index("ix_ash_assignment_id", table_name="assignment_status_history")
    op.drop_table("assignment_status_history")
