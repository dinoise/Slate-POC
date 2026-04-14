"""demand_predictions

Revision ID: ea7904e1226e
Revises: 25b52c0f9f8b
Create Date: 2026-03-09 17:48:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "ea7904e1226e"
down_revision: Union[str, None] = "25b52c0f9f8b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_geospatial_table(
        "demand_predictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("h3_r8", sa.String(length=16), nullable=False),
        sa.Column("hora_num", sa.SmallInteger(), nullable=False),
        sa.Column("dia_semana_num", sa.SmallInteger(), nullable=False),
        sa.Column("pred_ratio", sa.Float(), nullable=False),
        sa.Column("pred_abs", sa.Float(), nullable=False),
        sa.Column("demand_level", sa.SmallInteger(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column(
            "location",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "model_version", sa.String(length=20), nullable=False, server_default="v1.0.0"
        ),
        sa.Column("predicted_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("h3_r8", "predicted_for", name="uq_demand_h3_slot"),
    )
    op.create_geospatial_index(
        "idx_demand_predictions_location",
        "demand_predictions",
        ["location"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(
        "idx_demand_predictions_slot",
        "demand_predictions",
        ["predicted_for", sa.text("pred_abs DESC")],
    )
    op.create_index(
        "idx_demand_predictions_h3",
        "demand_predictions",
        ["h3_r8"],
    )


def downgrade() -> None:
    op.drop_index("idx_demand_predictions_h3", table_name="demand_predictions")
    op.drop_index("idx_demand_predictions_slot", table_name="demand_predictions")
    op.drop_geospatial_index(
        "idx_demand_predictions_location",
        table_name="demand_predictions",
        postgresql_using="gist",
        column_name="location",
    )
    op.drop_geospatial_table("demand_predictions")
