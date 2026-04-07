from __future__ import annotations

import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from packages.shared.auth_modes import (
    IdentityMode,
    ResolvedAuthMode,
    normalize_auth_mode,
    normalize_identity_mode,
)

_DEPRECATED_ENV_ALIAS_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("HOMELAB_ANALYTICS_CONFIG_BACKEND", "HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND"),
    (
        "HOMELAB_ANALYTICS_METADATA_BACKEND",
        "HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND",
    ),
    (
        "HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN",
        "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN",
    ),
    (
        "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN",
        "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN",
    ),
)


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
    control_plane_backend: str | None = None
    # Deprecated aliases for backward compatibility. Prefer
    # HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND.
    config_backend: str | None = None
    metadata_backend: str | None = None
    postgres_dsn: str | None = None
    control_plane_dsn: str | None = None
    # Deprecated aliases for backward compatibility. Prefer
    # HOMELAB_ANALYTICS_CONTROL_PLANE_DSN.
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
    identity_mode: str | None = None
    auth_mode_legacy_strict: bool = False
    machine_jwt_enabled: bool = False
    machine_jwt_issuer_url: str | None = None
    machine_jwt_jwks_url: str | None = None
    machine_jwt_audience: str | None = None
    machine_jwt_username_claim: str = "sub"
    machine_jwt_role_claim: str | None = "role"
    machine_jwt_default_role: str = "reader"
    machine_jwt_permissions_claim: str | None = None
    machine_jwt_scopes_claim: str | None = "scope"
    session_secret: str | None = None
    break_glass_enabled: bool = False
    break_glass_internal_only: bool = True
    break_glass_ttl_minutes: int = 30
    break_glass_allowed_cidrs: tuple[str, ...] = ()
    proxy_username_header: str = "x-forwarded-user"
    proxy_role_header: str = "x-forwarded-role"
    proxy_permissions_header: str | None = None
    proxy_trusted_cidrs: tuple[str, ...] = ()
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_redirect_uri: str | None = None
    oidc_scopes: tuple[str, ...] = ("openid", "profile", "email")
    oidc_api_audience: str | None = None
    oidc_username_claim: str = "preferred_username"
    oidc_groups_claim: str = "groups"
    oidc_permissions_claim: str | None = None
    oidc_permission_group_mappings: tuple[str, ...] = ()
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
    def resolved_identity_mode(self) -> IdentityMode:
        return normalize_identity_mode(self.identity_mode or self.auth_mode)

    @property
    def resolved_auth_mode(self) -> ResolvedAuthMode:
        return normalize_auth_mode(self.resolved_identity_mode)

    @property
    def is_local_single_user_mode(self) -> bool:
        return self.resolved_identity_mode == "local_single_user"

    @property
    def uses_legacy_auth_mode_fallback(self) -> bool:
        auth_mode = self.auth_mode.strip().lower()
        return self.identity_mode is None and bool(auth_mode) and auth_mode != "disabled"

    @property
    def resolved_control_plane_backend(self) -> str:
        backends: dict[str, str] = {}
        if self.control_plane_backend:
            backends["HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND"] = (
                self.control_plane_backend
            )
        if self.config_backend:
            backends["HOMELAB_ANALYTICS_CONFIG_BACKEND (deprecated)"] = (
                self.config_backend
            )
        if self.metadata_backend:
            backends["HOMELAB_ANALYTICS_METADATA_BACKEND (deprecated)"] = (
                self.metadata_backend
            )
        if not backends:
            # If a DSN is configured but no backend var is set, infer postgres
            # Only infer postgres from control-plane-specific DSN fields.
            # The generic postgres_dsn is shared with reporting and must not
            # silently promote the control-plane backend.
            has_control_dsn = bool(
                self.control_plane_dsn
                or self.control_postgres_dsn
                or self.metadata_postgres_dsn
            )
            return "postgres" if has_control_dsn else "sqlite"

        normalized = {
            source: value.strip().lower() for source, value in backends.items()
        }
        unique_values = sorted(set(normalized.values()))
        if len(unique_values) > 1:
            rendered = ", ".join(
                f"{source}={value!r}" for source, value in normalized.items()
            )
            raise ValueError(
                "Conflicting control-plane backend settings; configure only one "
                "effective value via HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND. "
                f"Received: {rendered}."
            )
        return unique_values[0]

    @property
    def resolved_control_plane_postgres_dsn(self) -> str | None:
        dsns: dict[str, str] = {}
        if self.control_plane_dsn:
            dsns["HOMELAB_ANALYTICS_CONTROL_PLANE_DSN"] = self.control_plane_dsn
        if self.control_postgres_dsn:
            dsns["HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN (deprecated)"] = (
                self.control_postgres_dsn
            )
        if self.metadata_postgres_dsn:
            dsns["HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN (deprecated)"] = (
                self.metadata_postgres_dsn
            )
        if not dsns:
            return self.postgres_dsn

        unique_values = sorted(set(dsns.values()))
        if len(unique_values) > 1:
            rendered = ", ".join(f"{source}={value!r}" for source, value in dsns.items())
            raise ValueError(
                "Conflicting control-plane Postgres DSN settings; configure only one "
                "effective value via HOMELAB_ANALYTICS_CONTROL_PLANE_DSN. "
                f"Received: {rendered}."
            )
        return unique_values[0]

    @property
    def resolved_control_postgres_dsn(self) -> str | None:
        return self.resolved_control_plane_postgres_dsn

    @property
    def resolved_metadata_postgres_dsn(self) -> str | None:
        return self.resolved_control_plane_postgres_dsn

    @property
    def resolved_reporting_postgres_dsn(self) -> str | None:
        return self.reporting_postgres_dsn or self.postgres_dsn

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AppSettings":
        env = environ or os.environ
        _emit_deprecated_env_alias_warnings(env)
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
        control_plane_backend = (
            env.get("HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND") or None
        )
        config_backend = env.get("HOMELAB_ANALYTICS_CONFIG_BACKEND") or None
        metadata_backend = env.get("HOMELAB_ANALYTICS_METADATA_BACKEND") or None
        postgres_dsn = env.get("HOMELAB_ANALYTICS_POSTGRES_DSN") or None
        control_plane_dsn = env.get("HOMELAB_ANALYTICS_CONTROL_PLANE_DSN") or None
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
        identity_mode = env.get("HOMELAB_ANALYTICS_IDENTITY_MODE") or None
        auth_mode_legacy_strict = env.get(
            "HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT", ""
        ).lower() in {"1", "true", "yes", "on"}
        machine_jwt_enabled = env.get(
            "HOMELAB_ANALYTICS_MACHINE_JWT_ENABLED", ""
        ).lower() in {"1", "true", "yes", "on"}
        machine_jwt_issuer_url = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL") or None
        )
        machine_jwt_jwks_url = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_JWKS_URL") or None
        )
        machine_jwt_audience = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE") or None
        )
        machine_jwt_username_claim = env.get(
            "HOMELAB_ANALYTICS_MACHINE_JWT_USERNAME_CLAIM",
            "sub",
        ).strip()
        machine_jwt_role_claim = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_ROLE_CLAIM", "role").strip() or None
        )
        machine_jwt_default_role = env.get(
            "HOMELAB_ANALYTICS_MACHINE_JWT_DEFAULT_ROLE",
            "reader",
        ).strip()
        machine_jwt_permissions_claim = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_PERMISSIONS_CLAIM") or None
        )
        machine_jwt_scopes_claim = (
            env.get("HOMELAB_ANALYTICS_MACHINE_JWT_SCOPES_CLAIM", "scope").strip()
            or None
        )
        session_secret = env.get("HOMELAB_ANALYTICS_SESSION_SECRET") or None
        break_glass_enabled = env.get(
            "HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED", ""
        ).lower() in {"1", "true", "yes", "on"}
        break_glass_internal_only = env.get(
            "HOMELAB_ANALYTICS_BREAK_GLASS_INTERNAL_ONLY",
            "true",
        ).lower() in {"1", "true", "yes", "on"}
        break_glass_ttl_minutes = int(
            env.get("HOMELAB_ANALYTICS_BREAK_GLASS_TTL_MINUTES", "30")
        )
        break_glass_allowed_cidrs = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_BREAK_GLASS_ALLOWED_CIDRS", ""),
                delimiter=",",
            )
        )
        proxy_username_header = env.get(
            "HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER",
            "x-forwarded-user",
        ).strip()
        proxy_role_header = env.get(
            "HOMELAB_ANALYTICS_PROXY_ROLE_HEADER",
            "x-forwarded-role",
        ).strip()
        proxy_permissions_header = (
            env.get("HOMELAB_ANALYTICS_PROXY_PERMISSIONS_HEADER") or None
        )
        proxy_trusted_cidrs = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS", ""),
                delimiter=",",
            )
        )
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
        oidc_permissions_claim = (
            env.get("HOMELAB_ANALYTICS_OIDC_PERMISSIONS_CLAIM") or None
        )
        oidc_permission_group_mappings = tuple(
            _split_config_value(
                env.get("HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS", ""),
                delimiter=";",
            )
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
            control_plane_backend=control_plane_backend,
            config_backend=config_backend,
            metadata_backend=metadata_backend,
            postgres_dsn=postgres_dsn,
            control_plane_dsn=control_plane_dsn,
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
            identity_mode=identity_mode,
            auth_mode_legacy_strict=auth_mode_legacy_strict,
            machine_jwt_enabled=machine_jwt_enabled,
            machine_jwt_issuer_url=machine_jwt_issuer_url,
            machine_jwt_jwks_url=machine_jwt_jwks_url,
            machine_jwt_audience=machine_jwt_audience,
            machine_jwt_username_claim=machine_jwt_username_claim,
            machine_jwt_role_claim=machine_jwt_role_claim,
            machine_jwt_default_role=machine_jwt_default_role,
            machine_jwt_permissions_claim=machine_jwt_permissions_claim,
            machine_jwt_scopes_claim=machine_jwt_scopes_claim,
            session_secret=session_secret,
            break_glass_enabled=break_glass_enabled,
            break_glass_internal_only=break_glass_internal_only,
            break_glass_ttl_minutes=break_glass_ttl_minutes,
            break_glass_allowed_cidrs=break_glass_allowed_cidrs,
            proxy_username_header=proxy_username_header,
            proxy_role_header=proxy_role_header,
            proxy_permissions_header=proxy_permissions_header,
            proxy_trusted_cidrs=proxy_trusted_cidrs,
            oidc_issuer_url=oidc_issuer_url,
            oidc_client_id=oidc_client_id,
            oidc_client_secret=oidc_client_secret,
            oidc_redirect_uri=oidc_redirect_uri,
            oidc_scopes=oidc_scopes,
            oidc_api_audience=oidc_api_audience,
            oidc_username_claim=oidc_username_claim,
            oidc_groups_claim=oidc_groups_claim,
            oidc_permissions_claim=oidc_permissions_claim,
            oidc_permission_group_mappings=oidc_permission_group_mappings,
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


def _emit_deprecated_env_alias_warnings(env: Mapping[str, str]) -> None:
    for alias, replacement in _DEPRECATED_ENV_ALIAS_REPLACEMENTS:
        alias_value = env.get(alias)
        if alias_value is None or not alias_value.strip():
            continue
        warnings.warn(
            (
                f"{alias} is deprecated and will be removed no earlier than v0.2.0; "
                f"use {replacement} instead."
            ),
            DeprecationWarning,
            stacklevel=3,
        )
