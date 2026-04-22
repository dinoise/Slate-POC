"""Persistence layer for demand predictions.

Uses a raw SQL upsert via ``text()`` for bulk PostGIS inserts. This is
intentional: SQLAlchemy's ORM insert cannot mix per-row bind parameters with
SQL expressions (like ST_MakePoint) in a single ``executemany`` call, and
geoalchemy2 function objects cause type coercion failures in bulk ``values()``
lists.

Rows are chunked to stay below PostgreSQL's 65535 bind-parameter limit.
The unique constraint name ``uq_demand_h3_predicted_model`` is defined in
``slate_core.models.demand_prediction.DemandPrediction`` — if it changes,
update the ON CONFLICT clause below.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from slate_infra.logging import get_logger

from .predictor import SlotPrediction

logger = get_logger(__name__)

# PostgreSQL limit is 65535 bind parameters per query.
# Each row uses 11 bound parameters → 65535 // 11 ≈ 5957.
# Use 1000 as a safe, round chunk size.
_CHUNK_SIZE = 1000

_UPSERT_SQL = text("""
    INSERT INTO demand_predictions
        (h3_r8, hora_num, dia_semana_num, pred_ratio, pred_abs, demand_level,
         lat, lon, location, model_version, predicted_for, created_at)
    VALUES
        (:h3_r8, :hora_num, :dia_semana_num, :pred_ratio, :pred_abs, :demand_level,
         :lat, :lon, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
         :model_version, :predicted_for, NOW())
    ON CONFLICT ON CONSTRAINT uq_demand_h3_predicted_model
    DO UPDATE SET
        pred_ratio   = EXCLUDED.pred_ratio,
        pred_abs     = EXCLUDED.pred_abs,
        demand_level = EXCLUDED.demand_level,
        location     = ST_SetSRID(ST_MakePoint(EXCLUDED.lon, EXCLUDED.lat), 4326),
        created_at   = NOW()
""")


async def upsert_predictions(
    session: AsyncSession,
    predictions: list[SlotPrediction],
) -> int:
    """Upsert a batch of SlotPrediction rows in chunks.

    Args:
        session: Active async SQLAlchemy session.
        predictions: Rows produced by ``DemandPredictor.predict_slot()``.

    Returns:
        Number of rows in the batch (0 if input is empty).
    """
    if not predictions:
        return 0

    total = 0
    for offset in range(0, len(predictions), _CHUNK_SIZE):
        chunk = predictions[offset : offset + _CHUNK_SIZE]
        rows = [
            {
                "h3_r8": p.h3_r8,
                "hora_num": p.hora_num,
                "dia_semana_num": p.dia_semana_num,
                "pred_ratio": p.pred_ratio,
                "pred_abs": p.pred_abs,
                "demand_level": p.demand_level,
                "lat": p.lat,
                "lon": p.lon,
                "model_version": p.model_version,
                "predicted_for": p.predicted_for,
            }
            for p in chunk
        ]
        await session.execute(_UPSERT_SQL, rows)
        total += len(chunk)
        logger.debug("Upserted chunk %d rows (total so far: %d)", len(chunk), total)

    await session.commit()
    logger.debug("Upserted %d demand_prediction rows total", total)
    return total
