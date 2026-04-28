"""Tests for demand_refresh/main.py — entrypoint orchestration.

All external dependencies (GCS, DB, predictor) are mocked so these tests
run without network access or a real database.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from slate_jobs.demand_refresh.main import _build_slots, _run
from slate_jobs.demand_refresh.predictor import SlotPrediction

_CDMX = ZoneInfo("America/Mexico_City")

# ── _build_slots ──────────────────────────────────────────────────────────────


def test_build_slots_count() -> None:
    slots = _build_slots(24)
    assert len(slots) == 24


def test_build_slots_aligned_to_full_hour() -> None:
    slots = _build_slots(3)
    for _hora, _dia, dt in slots:
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.microsecond == 0


def test_build_slots_consecutive_hours() -> None:
    slots = _build_slots(5)
    dts = [dt for _, _, dt in slots]
    for i in range(1, len(dts)):
        assert dts[i] - dts[i - 1] == timedelta(hours=1)


def test_build_slots_hora_matches_cdmx_hour() -> None:
    """hora must reflect local CDMX hour, not UTC hour."""
    slots = _build_slots(24)
    for hora, _dia, dt in slots:
        assert hora == dt.astimezone(_CDMX).hour


def test_build_slots_dia_matches_cdmx_weekday() -> None:
    """dia_semana must reflect local CDMX weekday, not UTC weekday."""
    slots = _build_slots(24)
    for _hora, dia, dt in slots:
        assert dia == dt.astimezone(_CDMX).weekday()


def test_build_slots_starts_in_future() -> None:
    slots = _build_slots(1)
    now = datetime.now(UTC)
    _, _, first_slot = slots[0]
    assert first_slot > now


# ── _run ─────────────────────────────────────────────────────────────────────


def _make_slot_prediction(**kwargs) -> SlotPrediction:
    defaults = {
        "h3_r8": "8829a4c001fffff",
        "hora_num": 8,
        "dia_semana_num": 2,
        "pred_ratio": 0.7,
        "pred_abs": 2.1,
        "demand_level": 1,
        "lat": 19.43,
        "lon": -99.13,
        "model_version": "v1.0.0",
        "predicted_for": datetime(2026, 4, 22, 8, 0, tzinfo=UTC),
    }
    return SlotPrediction(**{**defaults, **kwargs})


@pytest.fixture
def mock_artifacts() -> dict:
    from pathlib import Path

    return {
        "model.lgb": Path("/tmp/model.lgb"),
        "features.parquet": Path("/tmp/features.parquet"),
        "h3_centroids.parquet": Path("/tmp/h3_centroids.parquet"),
    }


async def test_run_calls_download_artifacts(mock_artifacts) -> None:
    with (
        patch(
            "slate_jobs.demand_refresh.main.download_artifacts", return_value=mock_artifacts
        ) as mock_dl,
        patch("slate_jobs.demand_refresh.main.DemandPredictor") as mock_predictor_cls,
        patch(
            "slate_jobs.demand_refresh.main.upsert_predictions",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("slate_jobs.demand_refresh.main.async_session_maker") as mock_session_maker,
        patch("slate_jobs.demand_refresh.main.engine") as mock_engine,
        patch("slate_jobs.demand_refresh.main.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v1.0.0"
        mock_settings.HOURS_AHEAD = 2
        mock_settings.PRED_ABS_THRESHOLD = 0.5
        mock_predictor_cls.return_value.predict_slot.return_value = []
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_dl.assert_called_once_with("v1.0.0")


async def test_run_calls_predict_slot_for_each_slot(mock_artifacts) -> None:
    mock_predictor = MagicMock()
    mock_predictor.predict_slot.return_value = []

    with (
        patch("slate_jobs.demand_refresh.main.download_artifacts", return_value=mock_artifacts),
        patch("slate_jobs.demand_refresh.main.DemandPredictor", return_value=mock_predictor),
        patch(
            "slate_jobs.demand_refresh.main.upsert_predictions",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("slate_jobs.demand_refresh.main.async_session_maker") as mock_session_maker,
        patch("slate_jobs.demand_refresh.main.engine") as mock_engine,
        patch("slate_jobs.demand_refresh.main.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v1.0.0"
        mock_settings.HOURS_AHEAD = 3
        mock_settings.PRED_ABS_THRESHOLD = 0.5
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        assert mock_predictor.predict_slot.call_count == 3


async def test_run_upserts_when_predictions_returned(mock_artifacts) -> None:
    predictions = [_make_slot_prediction()]
    mock_predictor = MagicMock()
    mock_predictor.predict_slot.return_value = predictions
    mock_upsert = AsyncMock(return_value=len(predictions))

    with (
        patch("slate_jobs.demand_refresh.main.download_artifacts", return_value=mock_artifacts),
        patch("slate_jobs.demand_refresh.main.DemandPredictor", return_value=mock_predictor),
        patch("slate_jobs.demand_refresh.main.upsert_predictions", mock_upsert),
        patch("slate_jobs.demand_refresh.main.async_session_maker") as mock_session_maker,
        patch("slate_jobs.demand_refresh.main.engine") as mock_engine,
        patch("slate_jobs.demand_refresh.main.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v1.0.0"
        mock_settings.HOURS_AHEAD = 2
        mock_settings.PRED_ABS_THRESHOLD = 0.5
        mock_db = AsyncMock()
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        assert mock_upsert.call_count == 2  # once per slot
        mock_upsert.assert_called_with(mock_db, predictions)


async def test_run_skips_upsert_when_no_predictions(mock_artifacts) -> None:
    mock_predictor = MagicMock()
    mock_predictor.predict_slot.return_value = []
    mock_upsert = AsyncMock(return_value=0)

    with (
        patch("slate_jobs.demand_refresh.main.download_artifacts", return_value=mock_artifacts),
        patch("slate_jobs.demand_refresh.main.DemandPredictor", return_value=mock_predictor),
        patch("slate_jobs.demand_refresh.main.upsert_predictions", mock_upsert),
        patch("slate_jobs.demand_refresh.main.async_session_maker") as mock_session_maker,
        patch("slate_jobs.demand_refresh.main.engine") as mock_engine,
        patch("slate_jobs.demand_refresh.main.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v1.0.0"
        mock_settings.HOURS_AHEAD = 2
        mock_settings.PRED_ABS_THRESHOLD = 0.5
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_engine.dispose = AsyncMock()

        await _run()

        mock_upsert.assert_not_called()


async def test_run_disposes_engine(mock_artifacts) -> None:
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    with (
        patch("slate_jobs.demand_refresh.main.download_artifacts", return_value=mock_artifacts),
        patch("slate_jobs.demand_refresh.main.DemandPredictor") as mock_predictor_cls,
        patch(
            "slate_jobs.demand_refresh.main.upsert_predictions",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("slate_jobs.demand_refresh.main.async_session_maker") as mock_session_maker,
        patch("slate_jobs.demand_refresh.main.engine", mock_engine),
        patch("slate_jobs.demand_refresh.main.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v1.0.0"
        mock_settings.HOURS_AHEAD = 1
        mock_settings.PRED_ABS_THRESHOLD = 0.5
        mock_predictor_cls.return_value.predict_slot.return_value = []
        mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=False)

        await _run()

        mock_engine.dispose.assert_awaited_once()
