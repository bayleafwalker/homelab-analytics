from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import FastAPI

from apps.api.main import build_app, build_service, build_transformation_service
from packages.shared.settings import AppSettings


class ApiMainTests(unittest.TestCase):
    def test_build_service_uses_settings_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            service = build_service(settings)

            self.assertEqual(settings.landing_root, service.landing_root)
            self.assertEqual(
                settings.metadata_database_path,
                service.metadata_repository.database_path,
            )

    def test_build_transformation_service_uses_settings_path(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            transformation_service = build_transformation_service(settings)

            self.assertTrue(
                settings.resolved_analytics_database_path.exists()
            )
            transformation_service.store.close()

    def test_build_app_returns_fastapi_app(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    Path(temp_dir) / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    Path(temp_dir) / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    Path(temp_dir) / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            app = build_app(settings)

            self.assertIsInstance(app, FastAPI)


if __name__ == "__main__":
    unittest.main()
