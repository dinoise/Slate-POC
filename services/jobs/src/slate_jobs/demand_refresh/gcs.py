"""Download model artifacts from Cloud Storage.

Artifacts are cached in /tmp so reruns within the same Cloud Run Job
instance skip the download. Cloud Run Jobs start fresh containers per
execution, so the cache is effectively per-run.

GCS layout:
    gs://{bucket}/demand_forecast/{version}/model.lgb
    gs://{bucket}/demand_forecast/{version}/features.parquet
    gs://{bucket}/demand_forecast/{version}/h3_centroids.parquet
"""

from __future__ import annotations

from pathlib import Path

from google.cloud import storage

from slate_infra.logging import get_logger

from ..config import settings

logger = get_logger(__name__)

_ARTIFACTS = [
    "model.lgb",
    "features.parquet",
    "h3_centroids.parquet",
]

_CACHE_DIR = Path("/tmp/slate_jobs/demand_forecast")


def download_artifacts(version: str | None = None) -> dict[str, Path]:
    """Download all required artifacts from GCS to /tmp.

    Skips files that are already present (idempotent within one execution).

    Args:
        version: Model version string, e.g. ``"v1.0.0"``.
                 Defaults to ``settings.MODEL_VERSION``.

    Returns:
        Dict mapping artifact name → local Path.
    """
    version = version or settings.MODEL_VERSION
    prefix = f"demand_forecast/{version}"
    local_dir = _CACHE_DIR / version
    local_dir.mkdir(parents=True, exist_ok=True)

    client = storage.Client()
    bucket = client.bucket(settings.GCS_BUCKET)

    paths: dict[str, Path] = {}
    for filename in _ARTIFACTS:
        local_path = local_dir / filename
        if local_path.exists():
            logger.info("Cache hit — skipping download: %s", filename)
        else:
            blob_name = f"{prefix}/{filename}"
            logger.info(
                "Downloading gs://%s/%s → %s",
                settings.GCS_BUCKET,
                blob_name,
                local_path,
            )
            bucket.blob(blob_name).download_to_filename(str(local_path))
            logger.info("Downloaded %s (%.1f KB)", filename, local_path.stat().st_size / 1024)
        paths[filename] = local_path

    return paths
