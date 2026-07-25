"""demand_predictions_slot_index

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-29 10:00:00.000000

Adds a composite B-tree index on (hora_num, dia_semana_num) with an INCLUDE
clause covering the columns most fetched by the GET /demand-predictions endpoint.

The existing idx_demand_predictions_slot index is on (predicted_for, pred_abs DESC)
which does not match the query filter — this migration adds the correct index and
drops the unused one.
"""

from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the old slot index that uses predicted_for — not used by any query
    op.drop_index("idx_demand_predictions_slot", table_name="demand_predictions")

    # Composite index matching the exact WHERE clause of get_by_slot_and_bbox.
    # INCLUDE avoids a heap fetch for the most-accessed columns — PostGIS
    # still needs the heap for `location` (geometry is not INCLUDEable in GIST).
    op.execute("""
        CREATE INDEX idx_demand_predictions_slot_spatial
        ON demand_predictions (hora_num, dia_semana_num)
        INCLUDE (h3_r8, pred_abs, demand_level, lat, lon)
    """)


def downgrade() -> None:
    op.drop_index("idx_demand_predictions_slot_spatial", table_name="demand_predictions")

    op.execute("""
        CREATE INDEX idx_demand_predictions_slot
        ON demand_predictions (predicted_for, pred_abs DESC)
    """)
