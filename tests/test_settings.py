import os
import unittest
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
        self.assertEqual((), settings.extension_paths)
        self.assertEqual((), settings.extension_modules)
        self.assertEqual(
            Path("/tmp/homelab-analytics/analytics/warehouse.duckdb"),
            settings.resolved_analytics_database_path,
        )
        self.assertEqual("sqlite", settings.config_backend)
        self.assertEqual("sqlite", settings.metadata_backend)
        self.assertEqual("control", settings.control_schema)
        self.assertEqual("duckdb", settings.reporting_backend)
        self.assertEqual("reporting", settings.reporting_schema)
        self.assertEqual("filesystem", settings.blob_backend)
        self.assertEqual("disabled", settings.auth_mode)
        self.assertIsNone(settings.session_secret)
        self.assertIsNone(settings.bootstrap_admin_username)
        self.assertIsNone(settings.bootstrap_admin_password)
        self.assertEqual(900, settings.auth_failure_window_seconds)
        self.assertEqual(5, settings.auth_failure_threshold)
        self.assertEqual(900, settings.auth_lockout_seconds)
        self.assertFalse(settings.enable_unsafe_admin)
        self.assertIsNone(settings.postgres_dsn)
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
        self.assertEqual((), settings.extension_paths)
        self.assertEqual((), settings.extension_modules)

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
                "HOMELAB_ANALYTICS_METADATA_BACKEND": "postgres",
                "HOMELAB_ANALYTICS_CONFIG_BACKEND": "postgres",
                "HOMELAB_ANALYTICS_POSTGRES_DSN": (
                    "postgresql://homelab:homelab@postgres:5432/homelab"
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
                "HOMELAB_ANALYTICS_SESSION_SECRET": "session-secret",
                "HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_USERNAME": "admin",
                "HOMELAB_ANALYTICS_BOOTSTRAP_ADMIN_PASSWORD": "admin-password",
                "HOMELAB_ANALYTICS_AUTH_FAILURE_WINDOW_SECONDS": "600",
                "HOMELAB_ANALYTICS_AUTH_FAILURE_THRESHOLD": "4",
                "HOMELAB_ANALYTICS_AUTH_LOCKOUT_SECONDS": "1200",
                "HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN": "true",
            }
        )

        self.assertEqual("postgres", settings.config_backend)
        self.assertEqual("postgres", settings.metadata_backend)
        self.assertEqual(
            "postgresql://homelab:homelab@postgres:5432/homelab",
            settings.postgres_dsn,
        )
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
        self.assertEqual("session-secret", settings.session_secret)
        self.assertEqual("admin", settings.bootstrap_admin_username)
        self.assertEqual("admin-password", settings.bootstrap_admin_password)
        self.assertEqual(600, settings.auth_failure_window_seconds)
        self.assertEqual(4, settings.auth_failure_threshold)
        self.assertEqual(1200, settings.auth_lockout_seconds)
        self.assertTrue(settings.enable_unsafe_admin)


if __name__ == "__main__":
    unittest.main()
