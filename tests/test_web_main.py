import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.web.main import (
    build_app,
    build_lazy_transformation_service,
    build_reporting_service,
    build_service,
    build_transformation_service,
)
from packages.pipelines.promotion import promote_run
from packages.shared.settings import AppSettings
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.test_web_app import invoke_wsgi_app


class WebMainTests(unittest.TestCase):
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

    def test_build_reporting_service_uses_transformation_runtime(self) -> None:
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
            reporting_service = build_reporting_service(settings, transformation_service)

            self.assertEqual([], reporting_service.get_monthly_cashflow())
            transformation_service.store.close()

    def test_build_app_returns_wsgi_callable(self) -> None:
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

            self.assertTrue(callable(app))

    def test_build_lazy_transformation_service_defers_duckdb_open(self) -> None:
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
                postgres_dsn="postgresql://homelab:homelab@localhost:5432/homelab",
                reporting_backend="postgres",
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            build_lazy_transformation_service(settings)

            self.assertFalse(settings.resolved_analytics_database_path.exists())

    def test_built_app_renders_dashboard_after_account_ingest(self) -> None:
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
            service = build_service(settings)

            ingest_run = service.ingest_file(
                ACCOUNT_FIXTURES / "account_transactions_valid.csv",
                source_name="manual-upload",
            )
            transformation_service = build_transformation_service(settings)
            promote_run(
                ingest_run.run_id,
                account_service=service,
                transformation_service=transformation_service,
            )

            status_code, headers, body = invoke_wsgi_app(app, "GET", "/")

            self.assertEqual(200, status_code)
            self.assertEqual("text/html; charset=utf-8", headers["Content-Type"])
            self.assertIn("Homelab Analytics", body)
            self.assertIn("2365.85", body)
            self.assertIn("Recent ingestion runs", body)


if __name__ == "__main__":
    unittest.main()
