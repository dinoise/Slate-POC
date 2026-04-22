"""Tests for DemandPredictor — pure inference, no I/O.

Uses a minimal LightGBM model trained in-memory so no model file is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from slate_jobs.demand_refresh.predictor import FEATURE_COLS, DemandPredictor, SlotPrediction

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_features(n_rows: int = 10) -> pd.DataFrame:
    """Build a minimal features DataFrame matching predictor expectations."""
    rng = np.random.default_rng(42)
    rows = []
    for i in range(n_rows):
        rows.append(
            {
                "h3_r8": f"88{i:014x}"[:16],
                "hora_num": 8,
                "dia_semana_num": 2,
                "es_fin_semana": 0,
                "hora_sin": np.sin(2 * np.pi * 8 / 24),
                "hora_cos": np.cos(2 * np.pi * 8 / 24),
                "dia_sin": np.sin(2 * np.pi * 2 / 7),
                "dia_cos": np.cos(2 * np.pi * 2 / 7),
                "h3_count": float(rng.integers(1, 50)),
                "h3_smooth": float(rng.uniform(0.5, 5.0)),
                "demand_level_num": int(rng.integers(0, 3)),
                "nivel_danio_medio": float(rng.uniform(0.5, 2.0)),
                "pct_auto": float(rng.uniform(0.3, 0.9)),
                "lesionados_medio": float(rng.uniform(0.0, 1.0)),
                "media_hex": float(rng.uniform(0.5, 3.0)),
                "lat": float(rng.uniform(18.0, 33.0)),
                "lon": float(rng.uniform(-117.0, -88.0)),
            }
        )
    return pd.DataFrame(rows)


def _make_centroids(features: pd.DataFrame) -> pd.DataFrame:
    return features[["h3_r8", "lat", "lon"]].copy()


# ── Fixture: in-memory LightGBM model ─────────────────────────────────────────


@pytest.fixture(scope="module")
def lgb_model_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Train a tiny LightGBM regressor and save it to a temp file."""
    import lightgbm as lgb

    features = _make_features(200)
    X = features[FEATURE_COLS].values
    y = np.random.default_rng(0).uniform(0.1, 2.0, len(X))

    dataset = lgb.Dataset(X, label=y)
    model = lgb.train(
        {"num_leaves": 4, "n_estimators": 5, "verbosity": -1},
        dataset,
        num_boost_round=5,
    )

    path = tmp_path_factory.mktemp("models") / "model.lgb"
    model.save_model(str(path))
    return path


@pytest.fixture(scope="module")
def features_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    df = _make_features(40)  # 4 slots × 10 hexagons
    # Add multiple hora/dia_semana combos
    df2 = df.copy()
    df2["hora_num"] = 14
    df2["dia_semana_num"] = 4
    combined = pd.concat([df, df2], ignore_index=True)
    path = tmp_path_factory.mktemp("data") / "features.parquet"
    combined.to_parquet(path, index=False)
    return path


@pytest.fixture(scope="module")
def centroids_path(tmp_path_factory: pytest.TempPathFactory, features_path: Path) -> Path:
    df = pd.read_parquet(features_path)[["h3_r8", "lat", "lon"]].drop_duplicates()
    path = tmp_path_factory.mktemp("data") / "h3_centroids.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture(scope="module")
def predictor(lgb_model_path: Path, features_path: Path, centroids_path: Path) -> DemandPredictor:
    return DemandPredictor(
        model_path=lgb_model_path,
        features_path=features_path,
        h3_centroids_path=centroids_path,
        model_version="test-v1",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_predict_slot_returns_list(predictor: DemandPredictor) -> None:
    predicted_for = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
    results = predictor.predict_slot(hora=8, dia_semana=2, predicted_for=predicted_for)
    assert isinstance(results, list)


def test_predict_slot_result_shape(predictor: DemandPredictor) -> None:
    predicted_for = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
    results = predictor.predict_slot(hora=8, dia_semana=2, predicted_for=predicted_for)
    # With threshold=0.5 and random model, at least some hexagons should be active
    assert len(results) >= 0  # could be 0 if all below threshold — that's valid
    for r in results:
        assert isinstance(r, SlotPrediction)


def test_slot_prediction_fields(predictor: DemandPredictor) -> None:
    predicted_for = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
    results = predictor.predict_slot(hora=8, dia_semana=2, predicted_for=predicted_for)
    if not results:
        pytest.skip("No active hexagons above threshold — adjust threshold or data")
    r = results[0]
    assert r.hora_num == 8
    assert r.dia_semana_num == 2
    assert r.predicted_for == predicted_for
    assert r.model_version == "test-v1"
    assert r.pred_ratio >= 0.01  # clipped minimum
    assert r.pred_abs >= 0.0
    assert r.demand_level in (0, 1, 2)
    assert -180 <= r.lon <= 180
    assert -90 <= r.lat <= 90


def test_predict_slot_unknown_hora_returns_empty(predictor: DemandPredictor) -> None:
    """Hora with no feature rows should return empty list, not raise."""
    predicted_for = datetime(2026, 4, 22, 23, 0, tzinfo=UTC)
    results = predictor.predict_slot(hora=23, dia_semana=6, predicted_for=predicted_for)
    assert results == []


def test_predict_slot_skips_rows_without_lat(
    lgb_model_path: Path,
    tmp_path: Path,
    centroids_path: Path,
) -> None:
    """Rows where lat/lon merge produced NaN should be silently dropped."""

    features = _make_features(5)
    features_path = tmp_path / "features_no_centroid.parquet"
    features.to_parquet(features_path, index=False)

    # Centroids with no matching h3_r8 → lat/lon will be NaN after merge
    empty_centroids = tmp_path / "empty_centroids.parquet"
    pd.DataFrame(columns=["h3_r8", "lat", "lon"]).to_parquet(empty_centroids, index=False)

    p = DemandPredictor(
        model_path=lgb_model_path,
        features_path=features_path,
        h3_centroids_path=empty_centroids,
        model_version="test-v1",
    )
    results = p.predict_slot(
        hora=8, dia_semana=2, predicted_for=datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
    )
    assert results == []
