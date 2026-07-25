"""Tests for demand_refresh/gcs.py — GCS artifact download.

Mocks google.cloud.storage so no real GCS access is needed.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from slate_jobs.demand_refresh.gcs import download_artifacts


@pytest.fixture
def mock_storage(tmp_path: Path):
    """Mock google.cloud.storage.Client and return a factory for blob mocks."""
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    def make_blob(local_path: Path):
        """Blob mock that writes a dummy file on download_to_filename."""
        blob = MagicMock()

        def fake_download(path: str) -> None:
            Path(path).write_bytes(b"fake-content")

        blob.download_to_filename.side_effect = fake_download
        return blob

    mock_bucket.blob.side_effect = lambda name: make_blob(tmp_path / name.split("/")[-1])

    with patch("slate_jobs.demand_refresh.gcs.storage.Client", return_value=mock_client):
        yield mock_client, mock_bucket


def test_download_creates_local_files(mock_storage, tmp_path: Path) -> None:
    with patch("slate_jobs.demand_refresh.gcs._CACHE_DIR", tmp_path):
        paths = download_artifacts("v1.0.0")

    assert set(paths.keys()) == {"model.lgb", "features.parquet", "h3_centroids.parquet"}
    for path in paths.values():
        assert path.exists()


def test_download_uses_correct_gcs_paths(mock_storage, tmp_path: Path) -> None:
    _, mock_bucket = mock_storage
    with patch("slate_jobs.demand_refresh.gcs._CACHE_DIR", tmp_path):
        download_artifacts("v2.0.0")

    blob_names = [call.args[0] for call in mock_bucket.blob.call_args_list]
    assert "demand_forecast/v2.0.0/model.lgb" in blob_names
    assert "demand_forecast/v2.0.0/features.parquet" in blob_names
    assert "demand_forecast/v2.0.0/h3_centroids.parquet" in blob_names


def test_download_skips_cached_files(mock_storage, tmp_path: Path) -> None:
    _, mock_bucket = mock_storage
    version_dir = tmp_path / "v1.0.0"
    version_dir.mkdir(parents=True)

    # Pre-create model.lgb to simulate cache hit
    (version_dir / "model.lgb").write_bytes(b"cached")

    with patch("slate_jobs.demand_refresh.gcs._CACHE_DIR", tmp_path):
        download_artifacts("v1.0.0")

    blob_names = [call.args[0] for call in mock_bucket.blob.call_args_list]
    assert "demand_forecast/v1.0.0/model.lgb" not in blob_names
    assert "demand_forecast/v1.0.0/features.parquet" in blob_names


def test_download_idempotent_second_run(mock_storage, tmp_path: Path) -> None:
    """Running twice should not re-download already cached files."""
    _, mock_bucket = mock_storage
    with patch("slate_jobs.demand_refresh.gcs._CACHE_DIR", tmp_path):
        download_artifacts("v1.0.0")
        first_call_count = mock_bucket.blob.call_count

        download_artifacts("v1.0.0")
        second_call_count = mock_bucket.blob.call_count

    # Second run should make no additional blob calls
    assert second_call_count == first_call_count


def test_download_uses_settings_version_by_default(mock_storage, tmp_path: Path) -> None:
    _, mock_bucket = mock_storage
    with (
        patch("slate_jobs.demand_refresh.gcs._CACHE_DIR", tmp_path),
        patch("slate_jobs.demand_refresh.gcs.settings") as mock_settings,
    ):
        mock_settings.MODEL_VERSION = "v99.0.0"
        mock_settings.GCS_BUCKET = "test-bucket"
        download_artifacts()  # no version arg → uses settings

    blob_names = [call.args[0] for call in mock_bucket.blob.call_args_list]
    assert all("v99.0.0" in name for name in blob_names)
