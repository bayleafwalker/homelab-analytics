import os
from pathlib import Path
import unittest

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


if __name__ == "__main__":
    unittest.main()
