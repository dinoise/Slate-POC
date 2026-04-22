"""Integration tests for demand_refresh.repository.

Requires a real PostGIS database — provided by the pg_container fixture
in conftest.py via testcontainers.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from slate_core.models.demand_prediction import DemandPrediction
from slate_jobs.demand_refresh.predictor import SlotPrediction
from slate_jobs.demand_refresh.repository import _CHUNK_SIZE, upsert_predictions

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_prediction(
    h3_r8: str = "8829a4c001fffff",
    hora: int = 8,
    dia: int = 2,
    pred_ratio: float = 0.7,
    pred_abs: float = 2.1,
    demand_level: int = 1,
    lat: float = 19.43,
    lon: float = -99.13,
    version: str = "v1.0.0",
    predicted_for: datetime | None = None,
) -> SlotPrediction:
    return SlotPrediction(
        h3_r8=h3_r8,
        hora_num=hora,
        dia_semana_num=dia,
        pred_ratio=pred_ratio,
        pred_abs=pred_abs,
        demand_level=demand_level,
        lat=lat,
        lon=lon,
        model_version=version,
        predicted_for=predicted_for or datetime(2026, 4, 22, 8, 0, tzinfo=UTC),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_upsert_empty_returns_zero(db_session: AsyncSession) -> None:
    result = await upsert_predictions(db_session, [])
    assert result == 0


async def test_upsert_inserts_rows(db_session: AsyncSession) -> None:
    predictions = [_make_prediction(h3_r8=f"88{i:014x}"[:16]) for i in range(5)]
    n = await upsert_predictions(db_session, predictions)
    assert n == 5

    rows = (await db_session.execute(select(DemandPrediction))).scalars().all()
    assert len(rows) == 5


async def test_upsert_updates_on_conflict(db_session: AsyncSession) -> None:
    """Re-upserting same (h3_r8, predicted_for, model_version) updates values."""
    p = _make_prediction(pred_ratio=0.5, pred_abs=1.5, demand_level=0)
    await upsert_predictions(db_session, [p])

    # Update same key with new values
    p_updated = _make_prediction(pred_ratio=0.9, pred_abs=3.0, demand_level=2)
    await upsert_predictions(db_session, [p_updated])

    rows = (await db_session.execute(select(DemandPrediction))).scalars().all()
    assert len(rows) == 1
    assert rows[0].pred_ratio == pytest.approx(0.9)
    assert rows[0].pred_abs == pytest.approx(3.0)
    assert rows[0].demand_level == 2


async def test_upsert_location_is_populated(db_session: AsyncSession) -> None:
    """The PostGIS location column must be non-null after upsert."""
    p = _make_prediction(lat=19.43, lon=-99.13)
    await upsert_predictions(db_session, [p])

    result = await db_session.execute(
        text("SELECT ST_AsText(location) FROM demand_predictions LIMIT 1")
    )
    wkt = result.scalar_one()
    assert wkt is not None
    assert "POINT" in wkt


async def test_upsert_different_model_versions_coexist(db_session: AsyncSession) -> None:
    """Different model_version values should create separate rows."""
    p_v1 = _make_prediction(version="v1.0.0")
    p_v2 = _make_prediction(version="v2.0.0")
    await upsert_predictions(db_session, [p_v1, p_v2])

    rows = (await db_session.execute(select(DemandPrediction))).scalars().all()
    versions = {r.model_version for r in rows}
    assert versions == {"v1.0.0", "v2.0.0"}


async def test_upsert_chunks_large_batch(db_session: AsyncSession) -> None:
    """Batches larger than _CHUNK_SIZE should be fully upserted."""
    n = _CHUNK_SIZE + 50
    predictions = [
        _make_prediction(
            h3_r8=f"88{i:014x}"[:16],
            predicted_for=datetime(2026, 4, 22, 10, 0, tzinfo=UTC),
        )
        for i in range(n)
    ]
    total = await upsert_predictions(db_session, predictions)
    assert total == n

    count_result = await db_session.execute(text("SELECT COUNT(*) FROM demand_predictions"))
    assert count_result.scalar_one() == n
