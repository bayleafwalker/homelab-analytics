from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

import pytest

from packages.shared.settings import AppSettings
from packages.storage.blob import FilesystemBlobStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.run_metadata import RunMetadataRepository
from packages.storage.runtime import (
    build_auth_store,
    build_blob_store,
    build_config_store,
    build_reporting_store,
    build_run_metadata_store,
)


def _build_settings(temp_dir: str, **overrides: Any) -> AppSettings:
    settings = AppSettings(
        data_dir=Path(temp_dir),
        landing_root=Path(temp_dir) / "landing",
        metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
        account_transactions_inbox_dir=Path(temp_dir) / "inbox" / "account-transactions",
        processed_files_dir=Path(temp_dir) / "processed" / "account-transactions",
        failed_files_dir=Path(temp_dir) / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=30,
    )
    return replace(settings, **overrides)


def test_build_blob_store_defaults_to_filesystem() -> None:
    with TemporaryDirectory() as temp_dir:
        store = build_blob_store(_build_settings(temp_dir))

    assert isinstance(store, FilesystemBlobStore)


def test_build_blob_store_requires_bucket_for_s3() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, blob_backend="s3")

        with pytest.raises(
            ValueError, match="S3 blob backend requires HOMELAB_ANALYTICS_S3_BUCKET"
        ):
            build_blob_store(settings)


def test_build_blob_store_constructs_s3_store() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            blob_backend="S3",
            s3_bucket="landing",
            s3_endpoint_url="http://minio.local",
            s3_region="eu-west-1",
            s3_access_key_id="minio",
            s3_secret_access_key="password",
            s3_prefix="bronze",
        )

        with patch("packages.storage.runtime.S3BlobStore") as s3_store:
            build_blob_store(settings)

    s3_store.assert_called_once_with(
        bucket="landing",
        endpoint_url="http://minio.local",
        region_name="eu-west-1",
        access_key_id="minio",
        secret_access_key="password",
        prefix="bronze",
    )


def test_build_run_metadata_store_defaults_to_sqlite() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)
        store = build_run_metadata_store(settings)

    assert isinstance(store, RunMetadataRepository)
    assert store.database_path == settings.resolved_config_database_path


def test_build_run_metadata_store_requires_dsn_for_postgres() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, control_plane_backend="postgres")

        with pytest.raises(
            ValueError,
            match="HOMELAB_ANALYTICS_CONTROL_PLANE_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN",
        ):
            build_run_metadata_store(settings)


def test_build_run_metadata_store_constructs_postgres_repository() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="POSTGRES",
            postgres_dsn="postgresql://homelab:homelab@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresRunMetadataRepository") as repository:
            build_run_metadata_store(settings)

    repository.assert_called_once_with(
        "postgresql://homelab:homelab@postgres:5432/homelab",
        schema="control",
    )


def test_build_run_metadata_store_prefers_control_plane_specific_dsn() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="postgres",
            postgres_dsn="postgresql://fallback:fallback@postgres:5432/homelab",
            control_plane_dsn="postgresql://control:control@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresRunMetadataRepository") as repository:
            build_run_metadata_store(settings)

    repository.assert_called_once_with(
        "postgresql://control:control@postgres:5432/homelab",
        schema="control",
    )


def test_build_reporting_store_defaults_to_duckdb() -> None:
    with TemporaryDirectory() as temp_dir:
        store = build_reporting_store(_build_settings(temp_dir))

    assert store is None


def test_build_reporting_store_requires_dsn_for_postgres() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, reporting_backend="postgres")

        with pytest.raises(
            ValueError,
            match="HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN",
        ):
            build_reporting_store(settings)


def test_build_reporting_store_constructs_postgres_store() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            reporting_backend="POSTGRES",
            postgres_dsn="postgresql://homelab:homelab@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresReportingStore") as store_factory:
            build_reporting_store(settings)

    store_factory.assert_called_once_with(
        "postgresql://homelab:homelab@postgres:5432/homelab",
        schema="reporting",
    )


def test_build_reporting_store_prefers_reporting_specific_dsn() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            reporting_backend="postgres",
            postgres_dsn="postgresql://fallback:fallback@postgres:5432/homelab",
            reporting_postgres_dsn="postgresql://reporting:reporting@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresReportingStore") as store_factory:
            build_reporting_store(settings)

    store_factory.assert_called_once_with(
        "postgresql://reporting:reporting@postgres:5432/homelab",
        schema="reporting",
    )


def test_build_config_store_defaults_to_sqlite() -> None:
    with TemporaryDirectory() as temp_dir:
        store = build_config_store(_build_settings(temp_dir))

    assert isinstance(store, IngestionConfigRepository)


def test_build_config_store_requires_dsn_for_postgres() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, control_plane_backend="postgres")

        with pytest.raises(
            ValueError,
            match="HOMELAB_ANALYTICS_CONTROL_PLANE_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN",
        ):
            build_config_store(settings)


def test_build_config_store_constructs_postgres_repository() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="POSTGRES",
            postgres_dsn="postgresql://homelab:homelab@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresIngestionConfigRepository") as repository:
            build_config_store(settings)

    repository.assert_called_once_with(
        "postgresql://homelab:homelab@postgres:5432/homelab",
        schema="control",
    )


def test_build_config_store_prefers_control_plane_specific_dsn() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="postgres",
            postgres_dsn="postgresql://fallback:fallback@postgres:5432/homelab",
            control_plane_dsn="postgresql://control:control@postgres:5432/homelab",
        )

        with patch("packages.storage.runtime.PostgresIngestionConfigRepository") as repository:
            build_config_store(settings)

    repository.assert_called_once_with(
        "postgresql://control:control@postgres:5432/homelab",
        schema="control",
    )


def test_build_auth_store_reuses_config_store_backend() -> None:
    with TemporaryDirectory() as temp_dir:
        store = build_auth_store(_build_settings(temp_dir))

    assert isinstance(store, IngestionConfigRepository)


def test_build_control_plane_stores_support_deprecated_backend_aliases() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            config_backend="postgres",
            metadata_backend="postgres",
            control_postgres_dsn="postgresql://legacy:legacy@postgres:5432/homelab",
            metadata_postgres_dsn="postgresql://legacy:legacy@postgres:5432/homelab",
        )

        with (
            patch("packages.storage.runtime.PostgresIngestionConfigRepository") as config_repository,
            patch("packages.storage.runtime.PostgresRunMetadataRepository") as metadata_repository,
        ):
            build_config_store(settings)
            build_run_metadata_store(settings)

    config_repository.assert_called_once_with(
        "postgresql://legacy:legacy@postgres:5432/homelab",
        schema="control",
    )
    metadata_repository.assert_called_once_with(
        "postgresql://legacy:legacy@postgres:5432/homelab",
        schema="control",
    )


def test_build_control_plane_stores_reject_conflicting_backend_aliases() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            config_backend="postgres",
            metadata_backend="sqlite",
        )

        with pytest.raises(ValueError, match="Conflicting control-plane backend settings"):
            build_config_store(settings)

        with pytest.raises(ValueError, match="Conflicting control-plane backend settings"):
            build_run_metadata_store(settings)


def test_build_control_plane_stores_reject_conflicting_dsn_aliases() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="postgres",
            control_postgres_dsn="postgresql://legacy-control:legacy-control@postgres:5432/homelab",
            metadata_postgres_dsn=(
                "postgresql://legacy-metadata:legacy-metadata@postgres:5432/homelab"
            ),
        )

        with pytest.raises(
            ValueError,
            match="Conflicting control-plane Postgres DSN settings",
        ):
            build_config_store(settings)

        with pytest.raises(
            ValueError,
            match="Conflicting control-plane Postgres DSN settings",
        ):
            build_run_metadata_store(settings)


def test_build_control_plane_stores_reject_unknown_backend() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, control_plane_backend="mysql")

        with pytest.raises(ValueError, match="Unsupported control-plane backend"):
            build_config_store(settings)

        with pytest.raises(ValueError, match="Unsupported control-plane backend"):
            build_run_metadata_store(settings)


def test_sqlite_forced_with_specific_control_dsn_emits_warning() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            control_plane_backend="sqlite",
            control_plane_dsn="postgresql://control:control@postgres:5432/homelab",
        )

        with pytest.warns(RuntimeWarning, match="HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=postgres"):
            build_config_store(settings)


def test_sqlite_with_generic_postgres_dsn_emits_descriptive_warning() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            postgres_dsn="postgresql://shared:shared@postgres:5432/homelab",
        )

        with pytest.warns(RuntimeWarning, match="HOMELAB_ANALYTICS_CONTROL_PLANE_DSN"):
            build_config_store(settings)


def test_sqlite_with_no_dsn_and_disabled_auth_emits_no_warning() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir)

        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", RuntimeWarning)
            build_config_store(settings)


def test_sqlite_with_local_auth_emits_no_error() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(temp_dir, auth_mode="local")

        import warnings as _warnings
        with _warnings.catch_warnings():
            _warnings.simplefilter("error", RuntimeWarning)
            build_config_store(settings)


def test_sqlite_with_oidc_auth_raises_value_error() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            auth_mode="oidc",
            control_plane_backend="sqlite",
        )

        with pytest.raises(ValueError, match="auth mode is 'oidc'"):
            build_config_store(settings)


def test_sqlite_with_proxy_auth_raises_value_error() -> None:
    with TemporaryDirectory() as temp_dir:
        settings = _build_settings(
            temp_dir,
            auth_mode="proxy",
            control_plane_backend="sqlite",
        )

        with pytest.raises(ValueError, match="auth mode is 'proxy'"):
            build_config_store(settings)
