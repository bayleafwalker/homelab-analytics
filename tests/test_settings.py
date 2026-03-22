import os
import unittest
import warnings
from pathlib import Path

from packages.shared.settings import AppSettings


class AppSettingsTests(unittest.TestCase):
    def test_settings_can_be_loaded_from_environment(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-analytics",
                "HOMELAB_ANALYTICS_API_HOST": "127.0.0.1",
                "HOMELAB_ANALYTICS_API_PORT": "9090",
                "HOMELAB_ANALYTICS_WEB_HOST": "127.0.0.1",
                "HOMELAB_ANALYTICS_WEB_PORT": "9091",
                "HOMELAB_ANALYTICS_WORKER_ID": "worker-a",
                "HOMELAB_ANALYTICS_DISPATCH_LEASE_SECONDS": "600",
            }
        )

        self.assertEqual(Path("/tmp/homelab-analytics"), settings.data_dir)
        self.assertEqual(
            Path("/tmp/homelab-analytics/landing"),
            settings.landing_root,
        )
        self.assertEqual(
            Path("/tmp/homelab-analytics/metadata/runs.db"),
            settings.metadata_database_path,
        )
        self.assertEqual(
            Path("/tmp/homelab-analytics/inbox/account-transactions"),
            settings.account_transactions_inbox_dir,
        )
        self.assertEqual(
            Path("/tmp/homelab-analytics/processed/account-transactions"),
            settings.processed_files_dir,
        )
        self.assertEqual(
            Path("/tmp/homelab-analytics/failed/account-transactions"),
            settings.failed_files_dir,
        )
        self.assertEqual("127.0.0.1", settings.api_host)
        self.assertEqual(9090, settings.api_port)
        self.assertEqual("127.0.0.1", settings.web_host)
        self.assertEqual(9091, settings.web_port)
        self.assertEqual(30, settings.worker_poll_interval_seconds)
        self.assertEqual("worker-a", settings.worker_id)
        self.assertEqual(600, settings.dispatch_lease_seconds)
        self.assertEqual((), settings.extension_paths)
        self.assertEqual((), settings.extension_modules)
        self.assertEqual(
            Path("/tmp/homelab-analytics/external-registry-cache"),
            settings.resolved_external_registry_cache_root,
        )
        self.assertEqual(
            Path("/tmp/homelab-analytics/analytics/warehouse.duckdb"),
            settings.resolved_analytics_database_path,
        )
        self.assertIsNone(settings.control_plane_backend)
        self.assertIsNone(settings.config_backend)
        self.assertIsNone(settings.metadata_backend)
        self.assertEqual("sqlite", settings.resolved_control_plane_backend)
        self.assertEqual("control", settings.control_schema)
        self.assertEqual("duckdb", settings.reporting_backend)
        self.assertEqual("reporting", settings.reporting_schema)
        self.assertEqual("filesystem", settings.blob_backend)
        self.assertEqual("disabled", settings.auth_mode)
        self.assertIsNone(settings.identity_mode)
        self.assertEqual("disabled", settings.resolved_identity_mode)
        self.assertEqual("disabled", settings.resolved_auth_mode)
        self.assertFalse(settings.auth_mode_legacy_strict)
        self.assertFalse(settings.machine_jwt_enabled)
        self.assertIsNone(settings.machine_jwt_issuer_url)
        self.assertIsNone(settings.machine_jwt_jwks_url)
        self.assertIsNone(settings.machine_jwt_audience)
        self.assertEqual("sub", settings.machine_jwt_username_claim)
        self.assertEqual("role", settings.machine_jwt_role_claim)
        self.assertEqual("reader", settings.machine_jwt_default_role)
        self.assertIsNone(settings.machine_jwt_permissions_claim)
        self.assertEqual("scope", settings.machine_jwt_scopes_claim)
        self.assertIsNone(settings.session_secret)
        self.assertFalse(settings.break_glass_enabled)
        self.assertTrue(settings.break_glass_internal_only)
        self.assertEqual(30, settings.break_glass_ttl_minutes)
        self.assertEqual((), settings.break_glass_allowed_cidrs)
        self.assertEqual("x-forwarded-user", settings.proxy_username_header)
        self.assertEqual("x-forwarded-role", settings.proxy_role_header)
        self.assertIsNone(settings.proxy_permissions_header)
        self.assertEqual((), settings.proxy_trusted_cidrs)
        self.assertIsNone(settings.oidc_issuer_url)
        self.assertIsNone(settings.oidc_client_id)
        self.assertIsNone(settings.oidc_client_secret)
        self.assertIsNone(settings.oidc_redirect_uri)
        self.assertEqual(("openid", "profile", "email"), settings.oidc_scopes)
        self.assertIsNone(settings.oidc_api_audience)
        self.assertEqual("preferred_username", settings.oidc_username_claim)
        self.assertEqual("groups", settings.oidc_groups_claim)
        self.assertIsNone(settings.oidc_permissions_claim)
        self.assertEqual((), settings.oidc_permission_group_mappings)
        self.assertEqual((), settings.oidc_reader_groups)
        self.assertEqual((), settings.oidc_operator_groups)
        self.assertEqual((), settings.oidc_admin_groups)
        self.assertFalse(settings.enable_bootstrap_local_admin)
        self.assertIsNone(settings.bootstrap_admin_username)
        self.assertIsNone(settings.bootstrap_admin_password)
        self.assertEqual(900, settings.auth_failure_window_seconds)
        self.assertEqual(5, settings.auth_failure_threshold)
        self.assertEqual(900, settings.auth_lockout_seconds)
        self.assertFalse(settings.enable_unsafe_admin)
        self.assertIsNone(settings.postgres_dsn)
        self.assertIsNone(settings.control_plane_dsn)
        self.assertIsNone(settings.control_postgres_dsn)
        self.assertIsNone(settings.metadata_postgres_dsn)
        self.assertIsNone(settings.reporting_postgres_dsn)
        self.assertIsNone(settings.s3_endpoint_url)
        self.assertIsNone(settings.s3_bucket)
        self.assertEqual("us-east-1", settings.s3_region)
        self.assertIsNone(settings.s3_access_key_id)
        self.assertIsNone(settings.s3_secret_access_key)
        self.assertEqual("", settings.s3_prefix)

    def test_settings_parse_extension_configuration(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_EXTENSION_PATHS": (
                    f"/opt/homelab/extensions{os.pathsep}/srv/custom-analytics"
                ),
                "HOMELAB_ANALYTICS_EXTENSION_MODULES": (
                    "homelab_ext.reports,custom_budgeting"
                ),
            }
        )

        self.assertEqual(
            (
                Path("/opt/homelab/extensions"),
                Path("/srv/custom-analytics"),
            ),
            settings.extension_paths,
        )
        self.assertEqual(
            ("homelab_ext.reports", "custom_budgeting"),
            settings.extension_modules,
        )

    def test_external_registry_cache_root_can_be_overridden_via_env(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-test",
                "HOMELAB_ANALYTICS_EXTERNAL_REGISTRY_CACHE_ROOT": (
                    "/srv/homelab/external-registry-cache"
                ),
            }
        )

        self.assertEqual(
            Path("/srv/homelab/external-registry-cache"),
            settings.external_registry_cache_root,
        )
        self.assertEqual(
            Path("/srv/homelab/external-registry-cache"),
            settings.resolved_external_registry_cache_root,
        )

    def test_settings_default_to_repo_local_data_directory(self) -> None:
        settings = AppSettings.from_env({})

        self.assertEqual(Path.cwd() / ".local" / "homelab-analytics", settings.data_dir)
        self.assertEqual(settings.data_dir / "landing", settings.landing_root)
        self.assertEqual(
            settings.data_dir / "metadata" / "runs.db",
            settings.metadata_database_path,
        )
        self.assertEqual(
            settings.data_dir / "inbox" / "account-transactions",
            settings.account_transactions_inbox_dir,
        )
        self.assertEqual(
            settings.data_dir / "processed" / "account-transactions",
            settings.processed_files_dir,
        )
        self.assertEqual(
            settings.data_dir / "failed" / "account-transactions",
            settings.failed_files_dir,
        )
        self.assertEqual("0.0.0.0", settings.web_host)
        self.assertEqual(8081, settings.web_port)
        self.assertIsNone(settings.worker_id)
        self.assertEqual(300, settings.dispatch_lease_seconds)
        self.assertEqual((), settings.extension_paths)
        self.assertEqual((), settings.extension_modules)
        self.assertEqual(
            settings.data_dir / "external-registry-cache",
            settings.resolved_external_registry_cache_root,
        )

    def test_resolved_config_database_path_defaults_to_data_dir(self) -> None:
        settings = AppSettings.from_env(
            {"HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-test"}
        )

        self.assertEqual(
            Path("/tmp/homelab-test/config.db"),
            settings.resolved_config_database_path,
        )

    def test_config_database_path_can_be_overridden_via_env(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-test",
                "HOMELAB_ANALYTICS_CONFIG_DATABASE_PATH": "/srv/config/homelab.db",
            }
        )

        self.assertEqual(
            Path("/srv/config/homelab.db"),
            settings.resolved_config_database_path,
        )
        self.assertEqual(
            Path("/srv/config/homelab.db"),
            settings.config_database_path,
        )

    def test_analytics_database_path_can_be_overridden_via_env(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-test",
                "HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH": (
                    "/srv/analytics/homelab.duckdb"
                ),
            }
        )

        self.assertEqual(
            Path("/srv/analytics/homelab.duckdb"),
            settings.analytics_database_path,
        )
        self.assertEqual(
            Path("/srv/analytics/homelab.duckdb"),
            settings.resolved_analytics_database_path,
        )

    def test_storage_backend_settings_can_be_loaded_from_environment(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_DATA_DIR": "/tmp/homelab-test",
                "HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND": "postgres",
                "HOMELAB_ANALYTICS_POSTGRES_DSN": (
                    "postgresql://homelab:homelab@postgres:5432/homelab"
                ),
                "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN": (
                    "postgresql://api-control:api-control@postgres:5432/homelab"
                ),
                "HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN": (
                    "postgresql://api-reporting:api-reporting@postgres:5432/homelab"
                ),
                "HOMELAB_ANALYTICS_CONTROL_SCHEMA": "platform_control",
                "HOMELAB_ANALYTICS_REPORTING_BACKEND": "postgres",
                "HOMELAB_ANALYTICS_REPORTING_SCHEMA": "published_reporting",
                "HOMELAB_ANALYTICS_BLOB_BACKEND": "s3",
                "HOMELAB_ANALYTICS_S3_ENDPOINT_URL": "http://minio:9000",
                "HOMELAB_ANALYTICS_S3_BUCKET": "homelab-landing",
                "HOMELAB_ANALYTICS_S3_REGION": "eu-west-1",
                "HOMELAB_ANALYTICS_S3_ACCESS_KEY_ID": "minio",
                "HOMELAB_ANALYTICS_S3_SECRET_ACCESS_KEY": "password",
                "HOMELAB_ANALYTICS_S3_PREFIX": "bronze",
                "HOMELAB_ANALYTICS_AUTH_MODE": "local",
                "HOMELAB_ANALYTICS_IDENTITY_MODE": "local_single_user",
                "HOMELAB_ANALYTICS_AUTH_MODE_LEGACY_STRICT": "true",
                "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
                "HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED": "true",
                "HOMELAB_ANALYTICS_BREAK_GLASS_INTERNAL_ONLY": "false",
                "HOMELAB_ANALYTICS_BREAK_GLASS_TTL_MINUTES": "45",
                "HOMELAB_ANALYTICS_BREAK_GLASS_ALLOWED_CIDRS": (
                    "10.0.0.0/8,192.168.0.0/16"
                ),
                "HOMELAB_ANALYTICS_PROXY_USERNAME_HEADER": "x-auth-user",
                "HOMELAB_ANALYTICS_PROXY_ROLE_HEADER": "x-auth-role",
                "HOMELAB_ANALYTICS_PROXY_PERMISSIONS_HEADER": "x-auth-permissions",
                "HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS": (
                    "10.0.0.0/8,172.16.0.0/12"
                ),
                "HOMELAB_ANALYTICS_OIDC_ISSUER_URL": "https://auth.example.test/application/o/homelab/",
                "HOMELAB_ANALYTICS_OIDC_CLIENT_ID": "homelab-analytics",
                "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET": "oidc-client-secret",
                "HOMELAB_ANALYTICS_OIDC_REDIRECT_URI": "https://analytics.example.test/auth/callback",
                "HOMELAB_ANALYTICS_OIDC_SCOPES": "openid,profile,email,groups",
                "HOMELAB_ANALYTICS_OIDC_API_AUDIENCE": "homelab-analytics-api",
                "HOMELAB_ANALYTICS_OIDC_USERNAME_CLAIM": "email",
                "HOMELAB_ANALYTICS_OIDC_GROUPS_CLAIM": "roles",
                "HOMELAB_ANALYTICS_OIDC_PERMISSIONS_CLAIM": "hla_permissions",
                "HOMELAB_ANALYTICS_OIDC_PERMISSION_GROUP_MAPPINGS": (
                    "finance-readers=reports.read;"
                    "automation-operators=ingest.write,runs.retry"
                ),
                "HOMELAB_ANALYTICS_OIDC_READER_GROUPS": "dash-readers",
                "HOMELAB_ANALYTICS_OIDC_OPERATOR_GROUPS": "operators-a,operators-b",
                "HOMELAB_ANALYTICS_OIDC_ADMIN_GROUPS": "platform-admins",
                "HOMELAB_ANALYTICS_MACHINE_JWT_ENABLED": "true",
                "HOMELAB_ANALYTICS_MACHINE_JWT_ISSUER_URL": "https://machine-auth.example.test/",
                "HOMELAB_ANALYTICS_MACHINE_JWT_JWKS_URL": "https://machine-auth.example.test/jwks",
                "HOMELAB_ANALYTICS_MACHINE_JWT_AUDIENCE": "homelab-machine",
                "HOMELAB_ANALYTICS_MACHINE_JWT_USERNAME_CLAIM": "client_id",
                "HOMELAB_ANALYTICS_MACHINE_JWT_ROLE_CLAIM": "hla_role",
                "HOMELAB_ANALYTICS_MACHINE_JWT_DEFAULT_ROLE": "operator",
                "HOMELAB_ANALYTICS_MACHINE_JWT_PERMISSIONS_CLAIM": "hla_permissions",
                "HOMELAB_ANALYTICS_MACHINE_JWT_SCOPES_CLAIM": "scope",
                "HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN": "true",
                "HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME": "admin",
                "HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD": "admin-password",
                "HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS": "600",
                "HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD": "4",
                "HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS": "1200",
                "HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN": "true",
            }
        )

        self.assertEqual("postgres", settings.control_plane_backend)
        self.assertEqual("postgres", settings.resolved_control_plane_backend)
        self.assertIsNone(settings.config_backend)
        self.assertIsNone(settings.metadata_backend)
        self.assertEqual(
            "postgresql://homelab:homelab@postgres:5432/homelab",
            settings.postgres_dsn,
        )
        self.assertEqual(
            "postgresql://api-control:api-control@postgres:5432/homelab",
            settings.control_plane_dsn,
        )
        self.assertEqual(
            "postgresql://api-reporting:api-reporting@postgres:5432/homelab",
            settings.reporting_postgres_dsn,
        )
        self.assertIsNone(settings.control_postgres_dsn)
        self.assertIsNone(settings.metadata_postgres_dsn)
        self.assertEqual("platform_control", settings.control_schema)
        self.assertEqual("postgres", settings.reporting_backend)
        self.assertEqual("published_reporting", settings.reporting_schema)
        self.assertEqual("s3", settings.blob_backend)
        self.assertEqual("http://minio:9000", settings.s3_endpoint_url)
        self.assertEqual("homelab-landing", settings.s3_bucket)
        self.assertEqual("eu-west-1", settings.s3_region)
        self.assertEqual("minio", settings.s3_access_key_id)
        self.assertEqual("password", settings.s3_secret_access_key)
        self.assertEqual("bronze", settings.s3_prefix)
        self.assertEqual("local", settings.auth_mode)
        self.assertEqual("local_single_user", settings.identity_mode)
        self.assertEqual("local_single_user", settings.resolved_identity_mode)
        self.assertEqual("local", settings.resolved_auth_mode)
        self.assertTrue(settings.auth_mode_legacy_strict)
        self.assertEqual("session-secret", settings.session_secret)
        self.assertTrue(settings.break_glass_enabled)
        self.assertFalse(settings.break_glass_internal_only)
        self.assertEqual(45, settings.break_glass_ttl_minutes)
        self.assertEqual(
            ("10.0.0.0/8", "192.168.0.0/16"),
            settings.break_glass_allowed_cidrs,
        )
        self.assertEqual("x-auth-user", settings.proxy_username_header)
        self.assertEqual("x-auth-role", settings.proxy_role_header)
        self.assertEqual("x-auth-permissions", settings.proxy_permissions_header)
        self.assertEqual(
            ("10.0.0.0/8", "172.16.0.0/12"),
            settings.proxy_trusted_cidrs,
        )
        self.assertEqual(
            "https://auth.example.test/application/o/homelab/",
            settings.oidc_issuer_url,
        )
        self.assertEqual("homelab-analytics", settings.oidc_client_id)
        self.assertEqual("oidc-client-secret", settings.oidc_client_secret)
        self.assertEqual(
            "https://analytics.example.test/auth/callback",
            settings.oidc_redirect_uri,
        )
        self.assertEqual(
            ("openid", "profile", "email", "groups"),
            settings.oidc_scopes,
        )
        self.assertEqual("homelab-analytics-api", settings.oidc_api_audience)
        self.assertEqual("email", settings.oidc_username_claim)
        self.assertEqual("roles", settings.oidc_groups_claim)
        self.assertEqual("hla_permissions", settings.oidc_permissions_claim)
        self.assertEqual(
            (
                "finance-readers=reports.read",
                "automation-operators=ingest.write,runs.retry",
            ),
            settings.oidc_permission_group_mappings,
        )
        self.assertEqual(("dash-readers",), settings.oidc_reader_groups)
        self.assertEqual(
            ("operators-a", "operators-b"),
            settings.oidc_operator_groups,
        )
        self.assertEqual(("platform-admins",), settings.oidc_admin_groups)
        self.assertTrue(settings.machine_jwt_enabled)
        self.assertEqual(
            "https://machine-auth.example.test/",
            settings.machine_jwt_issuer_url,
        )
        self.assertEqual(
            "https://machine-auth.example.test/jwks",
            settings.machine_jwt_jwks_url,
        )
        self.assertEqual("homelab-machine", settings.machine_jwt_audience)
        self.assertEqual("client_id", settings.machine_jwt_username_claim)
        self.assertEqual("hla_role", settings.machine_jwt_role_claim)
        self.assertEqual("operator", settings.machine_jwt_default_role)
        self.assertEqual(
            "hla_permissions",
            settings.machine_jwt_permissions_claim,
        )
        self.assertEqual("scope", settings.machine_jwt_scopes_claim)
        self.assertTrue(settings.enable_bootstrap_local_admin)
        self.assertEqual("admin", settings.bootstrap_admin_username)
        self.assertEqual("admin-password", settings.bootstrap_admin_password)
        self.assertEqual(600, settings.auth_failure_window_seconds)
        self.assertEqual(4, settings.auth_failure_threshold)
        self.assertEqual(1200, settings.auth_lockout_seconds)
        self.assertTrue(settings.enable_unsafe_admin)

    def test_settings_support_deprecated_control_plane_env_aliases(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            settings = AppSettings.from_env(
                {
                    "HOMELAB_ANALYTICS_CONFIG_BACKEND": "postgres",
                    "HOMELAB_ANALYTICS_METADATA_BACKEND": "postgres",
                    "HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN": (
                        "postgresql://legacy-control:legacy-control@postgres:5432/homelab"
                    ),
                    "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN": (
                        "postgresql://legacy-control:legacy-control@postgres:5432/homelab"
                    ),
                }
            )

        self.assertEqual("postgres", settings.resolved_control_plane_backend)
        self.assertEqual(
            "postgresql://legacy-control:legacy-control@postgres:5432/homelab",
            settings.resolved_control_plane_postgres_dsn,
        )
        self.assertEqual(
            {
                "HOMELAB_ANALYTICS_CONFIG_BACKEND",
                "HOMELAB_ANALYTICS_METADATA_BACKEND",
                "HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN",
                "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN",
            },
            {
                str(warning.message).split(" is deprecated", maxsplit=1)[0]
                for warning in caught
                if warning.category is DeprecationWarning
            },
        )

    def test_empty_deprecated_env_alias_values_do_not_emit_warnings(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", DeprecationWarning)
            AppSettings.from_env(
                {
                    "HOMELAB_ANALYTICS_CONFIG_BACKEND": "",
                    "HOMELAB_ANALYTICS_METADATA_BACKEND": "   ",
                    "HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN": "",
                    "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN": "   ",
                }
            )

        self.assertEqual([], [warning for warning in caught if warning.category is DeprecationWarning])

    def test_conflicting_control_plane_backend_aliases_raise_value_error(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            settings = AppSettings.from_env(
                {
                    "HOMELAB_ANALYTICS_CONFIG_BACKEND": "postgres",
                    "HOMELAB_ANALYTICS_METADATA_BACKEND": "sqlite",
                }
            )

        with self.assertRaisesRegex(
            ValueError,
            "Conflicting control-plane backend settings",
        ):
            _ = settings.resolved_control_plane_backend

    def test_conflicting_control_plane_dsn_aliases_raise_value_error(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            settings = AppSettings.from_env(
                {
                    "HOMELAB_ANALYTICS_CONTROL_POSTGRES_DSN": (
                        "postgresql://legacy-control:legacy-control@postgres:5432/homelab"
                    ),
                    "HOMELAB_ANALYTICS_METADATA_POSTGRES_DSN": (
                        "postgresql://legacy-metadata:legacy-metadata@postgres:5432/homelab"
                    ),
                }
            )

        with self.assertRaisesRegex(
            ValueError,
            "Conflicting control-plane Postgres DSN settings",
        ):
            _ = settings.resolved_control_plane_postgres_dsn

    def test_local_single_user_auth_mode_alias_resolves_to_local(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_AUTH_MODE": "local_single_user",
            }
        )

        self.assertEqual("local_single_user", settings.auth_mode)
        self.assertEqual("local_single_user", settings.resolved_identity_mode)
        self.assertEqual("local", settings.resolved_auth_mode)

    def test_identity_mode_overrides_auth_mode_when_explicitly_set(self) -> None:
        settings = AppSettings.from_env(
            {
                "HOMELAB_ANALYTICS_AUTH_MODE": "oidc",
                "HOMELAB_ANALYTICS_IDENTITY_MODE": "disabled",
            }
        )

        self.assertEqual("oidc", settings.auth_mode)
        self.assertEqual("disabled", settings.identity_mode)
        self.assertEqual("disabled", settings.resolved_identity_mode)
        self.assertEqual("disabled", settings.resolved_auth_mode)


if __name__ == "__main__":
    unittest.main()
