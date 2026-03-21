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
    worker_id: str | None = None
    dispatch_lease_seconds: int = 300
    api_base_url: str | None = None
    extension_paths: tuple[Path, ...] = ()
    extension_modules: tuple[str, ...] = ()
    external_registry_cache_root: Path | None = None
    config_database_path: Path | None = None
    analytics_database_path: Path | None = None
    config_backend: str = "sqlite"
    metadata_backend: str = "sqlite"
    postgres_dsn: str | None = None
    control_postgres_dsn: str | None = None
    metadata_postgres_dsn: str | None = None
    reporting_postgres_dsn: str | None = None
    control_schema: str = "control"
    reporting_backend: str = "duckdb"
    reporting_schema: str = "reporting"
    blob_backend: str = "filesystem"
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_prefix: str = ""
    auth_mode: str = "disabled"
    session_secret: str | None = None
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_scopes: tuple[str, ...] = ("openid", "profile", "email")
    oidc_api_audience: str | None = None
    oidc_username_claim: str = "preferred_username"
    oidc_groups_claim: str = "groups"
    oidc_reader_groups: tuple[str, ...] = ()
    oidc_operator_groups: tuple[str, ...] = ()
    oidc_admin_groups: tuple[str, ...] = ()
    enable_bootstrap_local_admin: bool = False
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = None
    auth_failure_window_seconds: int = 900
    auth_failure_threshold: int = 5
    auth_lockout_seconds: int = 900
    enable_unsafe_admin: bool = False
    ha_url: str | None = None    # e.g. "http://homeassistant.local:8123"
    ha_token: str | None = None  # HA long-lived access token
    ha_mqtt_broker_url: str | None = None   # e.g. "mqtt://mosquitto.local:1883"
    ha_mqtt_username: str | None = None
    ha_mqtt_password: str | None = None

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

    @property
    def resolved_external_registry_cache_root(self) -> Path:
        return self.external_registry_cache_root or (
            self.data_dir / "external-registry-cache"
        )

    @property
    def resolved_api_base_url(self) -> str:
        return self.api_base_url or f"http://127.0.0.1:{self.api_port}"

    @property
    def resolved_control_postgres_dsn(self) -> str | None:
        return self.control_postgres_dsn or self.postgres_dsn

    @property
    def resolved_metadata_postgres_dsn(self) -> str | None:
        return self.metadata_postgres_dsn or self.postgres_dsn

    @property
    def resolved_reporting_postgres_dsn(self) -> str | None:
        return self.reporting_postgres_dsn or self.postgres_dsn

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
        api_base_url = env.get("HOMELAB_ANALYTICS_API_BASE_URL") or None
        web_host = env.get("HOMELAB_ANALYTICS_WEB_HOST", "0.0.0.0")
        web_port = int(env.get("HOMELAB_ANALYTICS_WEB_PORT", "8081"))
        worker_poll_interval_seconds = int(
            env.get("HOMELAB_ANALYTICS_WORKER_POLL_INTERVAL", "30")
        )
        worker_id = env.get("HOMELAB_ANALYTICS_WORKER_ID") or None
        dispatch_lease_seconds = int(
            env.get("HOMELAB_ANALYTICS_DISPATCH_LEASE_SECONDS", "300")
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
        external_registry_cache_root_override = env.get(
            "HOMELAB_ANALYTICS_EXTERNAL_REGISTRY_CACHE_ROOT"
        )
        external_registry_cache_root = (
            Path(external_registry_cache_root_override)
            if external_registry_cache_root_override
            else None
        )
        config_db_override = env.get("HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH")
        config_database_path = Path(config_db_override) if config_db_override else None
        analytics_db_override = env.get("HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH")
        analytics_database_path = (
            Path(analytics_db_override) if analytics_db_override else None
        )
        config_backend = env.get("HOMELAB_ANALYTICS_CONFIG_BACKEND", "sqlite")
        metadata_backend = env.get("HOMELAB_ANALYTICS_METADATA_BACKEND", "sqlite")
        postgres_dsn = env.get("HOMELAB_ANALYTICS_POSTGRES_DSN") or None
        control_postgres_dsn = (
            env.get("HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN") or None
        )
        metadata_postgres_dsn = (
            env.get("HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN") or None
        )
        reporting_postgres_dsn = (
            env.get("HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN") or None
        )
        control_schema = env.get("HOMELAB_ANALYTICS_CONTROL_SCHEMA", "control")
        reporting_backend = env.get("HOMELAB_ANALYTICS_REPORTING_BACKEND", "duckdb")
        reporting_schema = env.get("HOMELAB_ANALYTICS_REPORTING_SCHEMA", "reporting")
        blob_backend = env.get("HOMELAB_ANALYTICS_BLOB_BACKEND", "filesystem")
        s3_endpoint_url = env.get("HOMELAB_ANALYTICS_S3_ENDPOINT_URL") or None
        s3_bucket = env.get("HOMELAB_ANALYTICS_S3_BUCKET") or None
        s3_region = env.get("HOMELAB_ANALYTICS_S3_REGION", "us-east-1")
        s3_access_key_id = env.get("HOMELAB_ANALYTICS_S3_ACCESS_KEY_ID") or None
        s3_secret_access_key = (
            env.get("HOMELAB_ANALYTICS_S3_SECRET_ACCESS_KEY") or None
        )
        s3_prefix = env.get("HOMELAB_ANALYTICS_S3_PREFIX", "")
        auth_mode = env.get("HOMELAB_ANALYTICS_AUTH_MODE", "disabled")
        session_secret = env.get("HOMELAB_ANALYTICS_SESSION_SECRET") or None
        oidc_issuer_url = env.get("HOMELAB_ANALYTICS_OIDC_ISSUER_URL") or None
        oidc_client_id = env.get("HOMELAB_ANALYTICS_OIDC_CLIENT_ID") or None
        oidc_client_secret = env.get("HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET") or None
        oidc_redirect_uri = env.get("HOMELAB_ANALYTICS_OIDC_REDIRECT_URI") or None
        oidc_scopes = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_OIDC_SCOPES", "openid,profile,email"),
                delimiter=",",
            )
        )
        oidc_api_audience = env.get("HOMELAB_ANALYTICS_OIDC_API_AUDIENCE") or None
        oidc_username_claim = env.get(
            "HOMELAB_ANALYTICS_OIDC_USERNAME_CLAIM",
            "preferred_username",
        )
        oidc_groups_claim = env.get(
            "HOMELAB_ANALYTICS_OIDC_GROUPS_CLAIM",
            "groups",
        )
        oidc_reader_groups = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_OIDC_READER_GROUPS", ""),
                delimiter=",",
            )
        )
        oidc_operator_groups = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS", ""),
                delimiter=",",
            )
        )
        oidc_admin_groups = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS", ""),
                delimiter=",",
            )
        )
        enable_bootstrap_local_admin = env.get(
            "HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN", ""
        ).lower() in {"1", "true", "yes", "on"}
        bootstrap_admin_username = (
            env.get("HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME") or None
        )
        bootstrap_admin_password = (
            env.get("HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD") or None
        )
        auth_failure_window_seconds = int(
            env.get("HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS", "900")
        )
        auth_failure_threshold = int(
            env.get("HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD", "5")
        )
        auth_lockout_seconds = int(
            env.get("HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS", "900")
        )
        enable_unsafe_admin = env.get(
            "HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN", ""
        ).lower() in {"1", "true", "yes", "on"}
        ha_url = env.get("HOMELAB_ANALYTICS_HA_URL") or None
        ha_token = env.get("HOMELAB_ANALYTICS_HA_TOKEN") or None
        ha_mqtt_broker_url = env.get("HOMELAB_ANALYTICS_HA_MQTT_BROKER_URL") or None
        ha_mqtt_username = env.get("HOMELAB_ANALYTICS_HA_MQTT_USERNAME") or None
        ha_mqtt_password = env.get("HOMELAB_ANALYTICS_HA_MQTT_PASSWORD") or None
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
            api_base_url=api_base_url,
            web_host=web_host,
            web_port=web_port,
            worker_poll_interval_seconds=worker_poll_interval_seconds,
            worker_id=worker_id,
            dispatch_lease_seconds=dispatch_lease_seconds,
            extension_paths=extension_paths,
            extension_modules=extension_modules,
            external_registry_cache_root=external_registry_cache_root,
            config_database_path=config_database_path,
            analytics_database_path=analytics_database_path,
            config_backend=config_backend,
            metadata_backend=metadata_backend,
            postgres_dsn=postgres_dsn,
            control_postgres_dsn=control_postgres_dsn,
            metadata_postgres_dsn=metadata_postgres_dsn,
            reporting_postgres_dsn=reporting_postgres_dsn,
            control_schema=control_schema,
            reporting_backend=reporting_backend,
            reporting_schema=reporting_schema,
            blob_backend=blob_backend,
            s3_endpoint_url=s3_endpoint_url,
            s3_bucket=s3_bucket,
            s3_region=s3_region,
            s3_access_key_id=s3_access_key_id,
            s3_secret_access_key=s3_secret_access_key,
            s3_prefix=s3_prefix,
            auth_mode=auth_mode,
            session_secret=session_secret,
            oidc_issuer_url=oidc_issuer_url,
            oidc_client_id=oidc_client_id,
            oidc_client_secret=oidc_client_secret,
            oidc_redirect_uri=oidc_redirect_uri,
            oidc_scopes=oidc_scopes,
            oidc_api_audience=oidc_api_audience,
            oidc_username_claim=oidc_username_claim,
            oidc_groups_claim=oidc_groups_claim,
            oidc_reader_groups=oidc_reader_groups,
            oidc_operator_groups=oidc_operator_groups,
            oidc_admin_groups=oidc_admin_groups,
            enable_bootstrap_local_admin=enable_bootstrap_local_admin,
            bootstrap_admin_username=bootstrap_admin_username,
            bootstrap_admin_password=bootstrap_admin_password,
            auth_failure_window_seconds=auth_failure_window_seconds,
            auth_failure_threshold=auth_failure_threshold,
            auth_lockout_seconds=auth_lockout_seconds,
            enable_unsafe_admin=enable_unsafe_admin,
            ha_url=ha_url,
            ha_token=ha_token,
            ha_mqtt_broker_url=ha_mqtt_broker_url,
            ha_mqtt_username=ha_mqtt_username,
            ha_mqtt_password=ha_mqtt_password,
        )


def _split_config_value(value: str, *, delimiter: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(delimiter) if part.strip())
