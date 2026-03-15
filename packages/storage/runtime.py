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
    backend = settings.metadata_backend.lower()
    if backend == "sqlite":
        return RunMetadataRepository(settings.metadata_database_path)
    if backend == "postgres":
        resolved_dsn = settings.resolved_metadata_postgres_dsn
        if not resolved_dsn:
            raise ValueError(
                "Postgres metadata backend requires HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN."
            )
        return PostgresRunMetadataRepository(
            resolved_dsn,
            schema=settings.control_schema,
        )
    raise ValueError(f"Unsupported metadata backend: {settings.metadata_backend!r}")


def build_config_store(
    settings: AppSettings,
) -> IngestionConfigRepository | PostgresIngestionConfigRepository:
    backend = settings.config_backend.lower()
    if backend == "sqlite":
        return IngestionConfigRepository(settings.resolved_config_database_path)
    if backend == "postgres":
        resolved_dsn = settings.resolved_control_postgres_dsn
        if not resolved_dsn:
            raise ValueError(
                "Postgres config backend requires HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN or HOMELAB_ANALYTICS_POSTGRES_DSN."
            )
        return PostgresIngestionConfigRepository(
            resolved_dsn,
            schema=settings.control_schema,
        )
    raise ValueError(f"Unsupported config backend: {settings.config_backend!r}")


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
