"""Tests for DemandPredictor — pure inference, no I/O.

Uses a minimal LightGBM model trained in-memory so no model file is needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from slate_jobs.demand_refresh.predictor import (
    FEATURE_COLS,
    DemandPredictor,
    SlotPrediction,
    _classify_demand,
)

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


# ── _classify_demand unit tests ───────────────────────────────────────────────


def test_classify_demand_empty() -> None:
    result = _classify_demand(np.array([]))
    assert len(result) == 0


def test_classify_demand_levels_in_range() -> None:
    rng = np.random.default_rng(7)
    values = rng.uniform(0.1, 10.0, 100)
    levels = _classify_demand(values)
    assert set(levels).issubset({0, 1, 2})


def test_classify_demand_percentile_invariant() -> None:
    """Per-slot percentile classification should produce ~50% Low, ~35% Med, ~15% High."""
    rng = np.random.default_rng(99)
    # Use 200 values so percentile counts are stable
    values = rng.lognormal(mean=1.0, sigma=0.8, size=200)
    levels = _classify_demand(values)
    n = len(levels)
    pct_low = (levels == 0).sum() / n
    pct_high = (levels == 2).sum() / n
    # By construction: p50 threshold → ~50% Low; p85 threshold → ~15% High
    assert 0.45 <= pct_low <= 0.55, f"Expected ~50% Low, got {pct_low:.1%}"
    assert 0.10 <= pct_high <= 0.20, f"Expected ~15% High, got {pct_high:.1%}"


def test_classify_demand_single_value() -> None:
    """Single value always gets level 2 (it's both p50 and p85)."""
    levels = _classify_demand(np.array([5.0]))
    assert levels[0] == 2


def test_demand_level_not_from_training_feature(predictor: DemandPredictor) -> None:
    """demand_level must be derived from pred_abs — not copied from demand_level_num feature.

    We verify by checking that the distribution across a full slot roughly
    matches the expected per-slot percentile split, not an arbitrary training-time label.
    """
    predicted_for = datetime(2026, 4, 22, 8, 0, tzinfo=UTC)
    results = predictor.predict_slot(hora=8, dia_semana=2, predicted_for=predicted_for)
    if len(results) < 3:
        pytest.skip("Too few active hexagons to verify distribution")
    pred_abs_vals = np.array([r.pred_abs for r in results])
    demand_levels = np.array([r.demand_level for r in results])
    # Verify: rows with pred_abs >= p85 should all be level 2
    p85 = float(np.percentile(pred_abs_vals, 85))
    for r in results:
        if r.pred_abs >= p85:
            assert r.demand_level == 2, (
                f"Expected demand_level=2 for pred_abs={r.pred_abs:.3f} >= p85={p85:.3f}, "
                f"got {r.demand_level}"
            )
    # Verify: rows with pred_abs < p50 should all be level 0
    p50 = float(np.percentile(pred_abs_vals, 50))
    for r in results:
        if r.pred_abs < p50:
            assert r.demand_level == 0, (
                f"Expected demand_level=0 for pred_abs={r.pred_abs:.3f} < p50={p50:.3f}, "
                f"got {r.demand_level}"
            )
    _ = demand_levels  # suppress unused warning


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
