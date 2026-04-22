from __future__ import annotations

from typing import cast

from packages.shared.settings import AppSettings
from packages.storage.auth_store import AuthStore
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.ingestion_config import IngestionConfigRepository
from packages.storage.postgres_ingestion_config import PostgresIngestionConfigRepository
from packages.storage.postgres_reporting import PostgresReportingStore
from packages.storage.postgres_run_metadata import PostgresRunMetadataRepository
from packages.storage.run_metadata import RunMetadataRepository, RunMetadataStore
from packages.storage.s3_blob import S3BlobStore


def _resolve_control_plane_backend(settings: AppSettings) -> str:
    backend = settings.resolved_control_plane_backend
    if backend not in {"sqlite", "postgres"}:
        raise ValueError(
            "Unsupported control-plane backend: "
            f"{backend!r}. Supported values are 'sqlite' and 'postgres'."
        )
    if backend == "sqlite":
        auth_mode = getattr(settings, "resolved_auth_mode", None)
        _SHARED_AUTH_MODES = {"oidc", "proxy"}
        if auth_mode in _SHARED_AUTH_MODES:
            raise ValueError(
                f"Control-plane backend is SQLite but auth mode is {auth_mode!r}, "
                "which requires a shared deployment. "
                "Set HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=postgres and "
                "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN for shared deployments."
            )
        has_specific_control_dsn = bool(
            getattr(settings, "control_plane_dsn", None)
            or getattr(settings, "control_postgres_dsn", None)
            or getattr(settings, "metadata_postgres_dsn", None)
        )
        has_generic_postgres_dsn = bool(getattr(settings, "postgres_dsn", None))
        if has_specific_control_dsn or has_generic_postgres_dsn:
            import warnings
            if has_specific_control_dsn:
                msg = (
                    "Control-plane backend is SQLite but a Postgres control-plane DSN is set. "
                    "Set HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=postgres for shared deployments."
                )
            else:
                msg = (
                    "Control-plane backend is SQLite but HOMELAB_ANALYTICS_POSTGRES_DSN is set. "
                    "The control plane will NOT use Postgres unless "
                    "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN is also set "
                    "(HOMELAB_ANALYTICS_POSTGRES_DSN is shared with reporting only). "
                    "Set HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND=postgres and "
                    "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN to use Postgres for the control plane."
                )
            warnings.warn(msg, RuntimeWarning, stacklevel=2)
    return backend


def _resolve_control_plane_postgres_dsn(settings: AppSettings) -> str:
    resolved_dsn = settings.resolved_control_plane_postgres_dsn
    if not resolved_dsn:
        raise ValueError(
            "Postgres control-plane backend requires "
            "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN "
            "(deprecated aliases: HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN, "
            "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN)."
        )
    return resolved_dsn


def build_blob_store(settings: AppSettings) -> BlobStore:
    backend = settings.blob_backend.lower()
    if backend == "filesystem":
        return FilesystemBlobStore(settings.landing_root)
    if backend == "s3":
        if not settings.s3_bucket:
            raise ValueError("S3 blob backend requires HOMELAB_ANALYTICS_S3_BUCKET.")
        return S3BlobStore(
            bucket=settings.s3_bucket,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            access_key_id=settings.s3_access_key_id,
            secret_access_key=settings.s3_secret_access_key,
            prefix=settings.s3_prefix,
        )
    raise ValueError(f"Unsupported blob backend: {settings.blob_backend!r}")


def build_run_metadata_store(settings: AppSettings) -> RunMetadataStore:
    backend = _resolve_control_plane_backend(settings)
    if backend == "sqlite":
        return RunMetadataRepository(settings.resolved_config_database_path)
    if backend == "postgres":
        return PostgresRunMetadataRepository(
            _resolve_control_plane_postgres_dsn(settings),
            schema=settings.control_schema,
        )
    raise AssertionError(f"Unhandled control-plane backend: {backend!r}")


def build_config_store(
    settings: AppSettings,
) -> IngestionConfigRepository | PostgresIngestionConfigRepository:
    backend = _resolve_control_plane_backend(settings)
    if backend == "sqlite":
        return IngestionConfigRepository(settings.resolved_config_database_path)
    if backend == "postgres":
        return PostgresIngestionConfigRepository(
            _resolve_control_plane_postgres_dsn(settings),
            schema=settings.control_schema,
        )
    raise AssertionError(f"Unhandled control-plane backend: {backend!r}")


def build_auth_store(settings: AppSettings) -> AuthStore:
    return cast(AuthStore, build_config_store(settings))


def build_reporting_store(settings: AppSettings) -> PostgresReportingStore | None:
    backend = settings.reporting_backend.lower()
    if backend == "duckdb":
        return None
    if backend == "postgres":
        resolved_dsn = settings.resolved_reporting_postgres_dsn
        if not resolved_dsn:
            raise ValueError(
                "Postgres reporting backend requires HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN."
            )
        return PostgresReportingStore(
            resolved_dsn,
            schema=settings.reporting_schema,
        )
    raise ValueError(f"Unsupported reporting backend: {settings.reporting_backend!r}")
