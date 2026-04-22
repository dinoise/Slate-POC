"""LightGBM demand predictor — pure inference, no I/O.

Loads the model and feature tables once and exposes ``predict_slot()``
for generating predictions for a single (hora, dia_semana, predicted_for)
combination.

The prediction formula is:
    pred_abs = model.predict(X) × media_hex

where ``media_hex`` is the historical average incident count for each H3
hexagon, stored in the features parquet.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from slate_infra.logging import get_logger

from ..config import settings

logger = get_logger(__name__)

FEATURE_COLS = [
    "hora_num",
    "dia_semana_num",
    "es_fin_semana",
    "hora_sin",
    "hora_cos",
    "dia_sin",
    "dia_cos",
    "h3_count",
    "h3_smooth",
    "demand_level_num",
    "nivel_danio_medio",
    "pct_auto",
    "lesionados_medio",
]


@dataclass(frozen=True, slots=True)
class SlotPrediction:
    """One row of output ready for DB insertion."""

    h3_r8: str
    hora_num: int
    dia_semana_num: int
    pred_ratio: float
    pred_abs: float
    demand_level: int
    lat: float
    lon: float
    model_version: str
    predicted_for: datetime


class DemandPredictor:
    """Loads artifacts once and generates per-slot predictions.

    Args:
        model_path: Local path to the serialised LightGBM model.
        features_path: Parquet with training features (one row per h3 × slot).
        h3_centroids_path: Parquet with h3_r8, lat, lon columns.
        model_version: Version string written into each prediction row.
    """

    def __init__(
        self,
        model_path: Path,
        features_path: Path,
        h3_centroids_path: Path,
        model_version: str | None = None,
    ) -> None:
        self._version = model_version or settings.MODEL_VERSION
        self._threshold = settings.PRED_ABS_THRESHOLD

        logger.info("Loading model from %s", model_path)
        self._model = lgb.Booster(model_file=str(model_path))

        logger.info("Loading features from %s", features_path)
        features_df = pd.read_parquet(features_path)

        logger.info("Loading H3 centroids from %s", h3_centroids_path)
        centroids = pd.read_parquet(h3_centroids_path, columns=["h3_r8", "lat", "lon"])

        self._features = features_df.merge(centroids, on="h3_r8", how="left")
        logger.info(
            "Features ready: %d rows, %d columns",
            len(self._features),
            len(self._features.columns),
        )

    def predict_slot(
        self,
        hora: int,
        dia_semana: int,
        predicted_for: datetime,
    ) -> list[SlotPrediction]:
        """Generate predictions for a single time slot.

        Args:
            hora: Hour of day (0–23).
            dia_semana: Day of week (0=Monday … 6=Sunday).
            predicted_for: UTC datetime this slot represents.

        Returns:
            List of SlotPrediction above the configured threshold.
        """
        slot = self._features[
            (self._features["hora_num"] == hora) & (self._features["dia_semana_num"] == dia_semana)
        ].copy()

        if slot.empty:
            logger.warning("No feature rows for hora=%d dia=%d — skipping slot", hora, dia_semana)
            return []

        pred_ratio = self._model.predict(slot[FEATURE_COLS])
        pred_ratio = np.clip(pred_ratio, 0.01, None)
        pred_abs = pred_ratio * slot["media_hex"].values

        active_mask = pred_abs >= self._threshold
        logger.debug(
            "hora=%02d dia=%d → %d/%d hexagons active (pred_abs ≥ %.1f)",
            hora,
            dia_semana,
            int(active_mask.sum()),
            len(slot),
            self._threshold,
        )

        results: list[SlotPrediction] = []
        for i, row in enumerate(slot.itertuples()):
            if not active_mask[i]:
                continue
            lat = getattr(row, "lat", None)
            lon = getattr(row, "lon", None)
            if lat is None or pd.isna(lat):
                continue
            results.append(
                SlotPrediction(
                    h3_r8=row.h3_r8,
                    hora_num=int(row.hora_num),
                    dia_semana_num=int(row.dia_semana_num),
                    pred_ratio=float(pred_ratio[i]),
                    pred_abs=float(pred_abs[i]),
                    demand_level=int(row.demand_level_num),
                    lat=float(lat),
                    lon=float(lon),
                    model_version=self._version,
                    predicted_for=predicted_for,
                )
            )
        return results
