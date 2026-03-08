from __future__ import annotations

from dataclasses import dataclass
import os
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
        )


def _split_config_value(value: str, *, delimiter: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(delimiter) if part.strip())
