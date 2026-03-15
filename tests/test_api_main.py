import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.main import (
    build_app,
    build_lazy_transformation_service,
    build_reporting_service,
    build_service,
    build_transformation_service,
)
from packages.pipelines.reporting_service import ReportingAccessMode
from packages.shared.settings import AppSettings
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.contract_price_test_support import FIXTURES as CONTRACT_PRICE_FIXTURES
from tests.subscription_test_support import FIXTURES as SUBSCRIPTION_FIXTURES


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

    def test_build_app_rejects_local_auth_without_session_secret(self) -> None:
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
                auth_mode="local",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_SESSION_SECRET",
            ):
                build_app(settings)

    def test_build_app_requires_explicit_local_bootstrap_flag(self) -> None:
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
                auth_mode="local",
                session_secret="session-secret",
                bootstrap_admin_username="admin",
                bootstrap_admin_password="admin-password",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN=true",
            ):
                build_app(settings)

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

    def test_build_reporting_service_uses_published_mode_for_postgres_reporting(self) -> None:
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

            transformation_service = build_transformation_service(settings)
            with patch("apps.api.main.build_reporting_store", return_value=object()):
                reporting_service = build_reporting_service(
                    settings,
                    transformation_service,
                )

            self.assertEqual(ReportingAccessMode.PUBLISHED, reporting_service._access_mode)
            transformation_service.store.close()

    def test_built_app_supports_account_ingest_and_monthly_cashflow_reporting(self) -> None:
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
            client = TestClient(build_app(settings))

            ingest_response = client.post(
                "/ingest",
                json={
                    "source_path": str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(201, ingest_response.status_code)
            report_response = client.get("/reports/monthly-cashflow")
            self.assertEqual(200, report_response.status_code)
            self.assertEqual("2365.8500", report_response.json()["rows"][0]["net"])

    def test_built_app_supports_subscription_ingest_and_summary_reporting(self) -> None:
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
            client = TestClient(build_app(settings))

            ingest_response = client.post(
                "/ingest/subscriptions",
                json={
                    "source_path": str(SUBSCRIPTION_FIXTURES / "subscriptions_valid.csv"),
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(201, ingest_response.status_code)
            report_response = client.get("/reports/subscription-summary")
            self.assertEqual(200, report_response.status_code)
            self.assertEqual(5, len(report_response.json()["rows"]))

    def test_built_app_supports_contract_price_ingest_and_reporting(self) -> None:
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
            client = TestClient(build_app(settings))

            ingest_response = client.post(
                "/ingest/contract-prices",
                json={
                    "source_path": str(
                        CONTRACT_PRICE_FIXTURES / "contract_prices_valid.csv"
                    ),
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(201, ingest_response.status_code)
            contract_response = client.get("/reports/contract-prices")
            electricity_response = client.get("/reports/electricity-prices")
            self.assertEqual(200, contract_response.status_code)
            self.assertEqual(200, electricity_response.status_code)
            self.assertEqual(3, len(contract_response.json()["rows"]))
            self.assertEqual(2, len(electricity_response.json()["rows"]))


if __name__ == "__main__":
    unittest.main()
