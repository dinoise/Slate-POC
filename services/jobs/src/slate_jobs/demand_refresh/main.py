"""
Cloud Run Job — daily demand prediction refresh.

Downloads LightGBM artifacts from GCS, runs inference for the next
HOURS_AHEAD slots, and upserts results into demand_predictions.

Scheduled via Cloud Scheduler (2am daily, America/Bogota).

Invoked by the ``demand-refresh`` console script installed via
``[project.scripts]`` in pyproject.toml.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from slate_infra.logging import get_logger, setup_logging

from ..config import settings
from ..db import async_session_maker, engine
from .gcs import download_artifacts
from .predictor import DemandPredictor
from .repository import upsert_predictions

logger = get_logger(__name__)

_CDMX = ZoneInfo("America/Mexico_City")


def _build_slots(hours_ahead: int) -> list[tuple[int, int, datetime]]:
    """Return (hora, dia_semana, predicted_for) tuples for the next N hours.

    predicted_for is UTC-aware (stored as-is in the DB).
    hora and dia_semana are extracted from the slot converted to America/Mexico_City
    so they match the local-time patterns the LightGBM model was trained on.
    """
    now = datetime.now(UTC)
    base = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    slots = []
    for offset in range(hours_ahead):
        slot_utc = base + timedelta(hours=offset)
        slot_cdmx = slot_utc.astimezone(_CDMX)
        slots.append((slot_cdmx.hour, slot_cdmx.weekday(), slot_utc))
    return slots


async def _run() -> None:
    job_start = time.perf_counter()
    logger.info(
        "Starting demand refresh — version=%s hours_ahead=%d threshold=%.1f",
        settings.MODEL_VERSION,
        settings.HOURS_AHEAD,
        settings.PRED_ABS_THRESHOLD,
    )

    artifacts = download_artifacts(settings.MODEL_VERSION)

    predictor = DemandPredictor(
        model_path=artifacts["model.lgb"],
        features_path=artifacts["features.parquet"],
        h3_centroids_path=artifacts["h3_centroids.parquet"],
        model_version=settings.MODEL_VERSION,
    )

    slots = _build_slots(settings.HOURS_AHEAD)
    logger.info("Predicting %d slots from %s UTC", len(slots), slots[0][2].isoformat())

    total_rows = 0
    async with async_session_maker() as db:
        for hora, dia_semana, predicted_for in slots:
            predictions = predictor.predict_slot(hora, dia_semana, predicted_for)
            if predictions:
                n = await upsert_predictions(db, predictions)
                total_rows += n
                logger.info(
                    "slot %s hora=%02d dia=%d → %d rows upserted",
                    predicted_for.isoformat(),
                    hora,
                    dia_semana,
                    n,
                )
            else:
                logger.debug(
                    "slot %s hora=%02d dia=%d → no active hexagons, skipped",
                    predicted_for.isoformat(),
                    hora,
                    dia_semana,
                )

    elapsed = time.perf_counter() - job_start
    logger.info(
        "Demand refresh complete — %d rows upserted across %d slots in %.1fs",
        total_rows,
        len(slots),
        elapsed,
    )
    await engine.dispose()


def main() -> None:
    """Console script entrypoint — installed via [project.scripts]."""
    setup_logging(log_level=settings.effective_log_level, is_local=settings.is_local)
    asyncio.run(_run())
