from __future__ import annotations

from packages.shared.settings import AppSettings
from packages.storage.blob import BlobStore, FilesystemBlobStore
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
        if not settings.postgres_dsn:
            raise ValueError(
                "Postgres metadata backend requires HOMELAB_ANALYTICS_POSTGRES_DSN."
            )
        return PostgresRunMetadataRepository(settings.postgres_dsn)
    raise ValueError(f"Unsupported metadata backend: {settings.metadata_backend!r}")


def build_reporting_store(settings: AppSettings) -> PostgresReportingStore | None:
    backend = settings.reporting_backend.lower()
    if backend == "duckdb":
        return None
    if backend == "postgres":
        if not settings.postgres_dsn:
            raise ValueError(
                "Postgres reporting backend requires HOMELAB_ANALYTICS_POSTGRES_DSN."
            )
        return PostgresReportingStore(settings.postgres_dsn)
    raise ValueError(f"Unsupported reporting backend: {settings.reporting_backend!r}")
