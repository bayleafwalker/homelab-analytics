from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class AppSettings:
    data_dir: Path
    landing_root: Path
    metadata_database_path: Path
    account_transactions_inbox_dir: Path
    processed_files_dir: Path
    failed_files_dir: Path
    api_host: str
    api_port: int
    web_host: str
    web_port: int
    worker_poll_interval_seconds: int
    extension_paths: tuple[Path, ...] = ()
    extension_modules: tuple[str, ...] = ()
    config_database_path: Path | None = None
    analytics_database_path: Path | None = None
    metadata_backend: str = "sqlite"
    postgres_dsn: str | None = None
    reporting_backend: str = "duckdb"
    blob_backend: str = "filesystem"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_prefix: str = ""

    @property
    def resolved_config_database_path(self) -> Path:
        """Absolute path to the ingestion-config SQLite database.

        Defaults to ``<data_dir>/config.db`` when not explicitly set via
        the ``HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH`` env var.
        """
        return self.config_database_path or (self.data_dir / "config.db")

    @property
    def resolved_analytics_database_path(self) -> Path:
        return self.analytics_database_path or (
            self.data_dir / "analytics" / "warehouse.duckdb"
        )

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppSettings":
        env = environ or os.environ
        data_dir = Path(
            env.get(
                "HOMELAB_ANALYTICS_DATA_DIR",
                str(Path.cwd() / ".local" / "homelab-analytics"),
            )
        )
        api_host = env.get("HOMELAB_ANALYTICS_API_HOST", "0.0.0.0")
        api_port = int(env.get("HOMELAB_ANALYTICS_API_PORT", "8080"))
        web_host = env.get("HOMELAB_ANALYTICS_WEB_HOST", "0.0.0.0")
        web_port = int(env.get("HOMELAB_ANALYTICS_WEB_PORT", "8081"))
        worker_poll_interval_seconds = int(
            env.get("HOMELAB_ANALYTICS_WORKER_POLL_INTERVAL", "30")
        )
        extension_paths = tuple(
            Path(path)
            for path in _split_config_value(
                env.get("HOMELAB_ANALYTICS_EXTENSION_PATHS", ""),
                delimiter=os.pathsep,
            )
        )
        extension_modules = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_EXTENSION_MODULES", ""),
                delimiter=",",
            )
        )
        config_db_override = env.get("HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH")
        config_database_path = Path(config_db_override) if config_db_override else None
        analytics_db_override = env.get("HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH")
        analytics_database_path = (
            Path(analytics_db_override) if analytics_db_override else None
        )
        metadata_backend = env.get("HOMELAB_ANALYTICS_METADATA_BACKEND", "sqlite")
        postgres_dsn = env.get("HOMELAB_ANALYTICS_POSTGRES_DSN") or None
        reporting_backend = env.get("HOMELAB_ANALYTICS_REPORTING_BACKEND", "duckdb")
        blob_backend = env.get("HOMELAB_ANALYTICS_BLOB_BACKEND", "filesystem")
        s3_endpoint_url = env.get("HOMELAB_ANALYTICS_S3_ENDPOINT_URL") or None
        s3_bucket = env.get("HOMELAB_ANALYTICS_S3_BUCKET") or None
        s3_region = env.get("HOMELAB_ANALYTICS_S3_REGION", "us-east-1")
        s3_access_key_id = env.get("HOMELAB_ANALYTICS_S3_ACCESS_KEY_ID") or None
        s3_secret_access_key = (
            env.get("HOMELAB_ANALYTICS_S3_SECRET_ACCESS_KEY") or None
        )
        s3_prefix = env.get("HOMELAB_ANALYTICS_S3_PREFIX", "")
        return cls(
            data_dir=data_dir,
            landing_root=data_dir / "landing",
            metadata_database_path=data_dir / "metadata" / "runs.db",
            account_transactions_inbox_dir=(
                data_dir / "inbox" / "account-transactions"
            ),
            processed_files_dir=data_dir / "processed" / "account-transactions",
            failed_files_dir=data_dir / "failed" / "account-transactions",
            api_host=api_host,
            api_port=api_port,
            web_host=web_host,
            web_port=web_port,
            worker_poll_interval_seconds=worker_poll_interval_seconds,
            extension_paths=extension_paths,
            extension_modules=extension_modules,
            config_database_path=config_database_path,
            analytics_database_path=analytics_database_path,
            metadata_backend=metadata_backend,
            postgres_dsn=postgres_dsn,
            reporting_backend=reporting_backend,
            blob_backend=blob_backend,
            s3_endpoint_url=s3_endpoint_url,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_access_key_id=s3_access_key_id,
            s3_secret_access_key=s3_secret_access_key,
            s3_prefix=s3_prefix,
        )


def _split_config_value(value: str, *, delimiter: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(delimiter) if part.strip())
