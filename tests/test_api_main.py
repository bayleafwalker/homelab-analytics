import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

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
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
    SourceAssetCreate,
)
from tests.account_test_support import (
    ACCOUNT_CONTRACT_ID,
    ACCOUNT_MAPPING_ID,
    ACCOUNT_SOURCE_SYSTEM_ID,
    create_account_configuration,
)
from tests.account_test_support import (
    FIXTURES as ACCOUNT_FIXTURES,
)
from tests.contract_price_test_support import FIXTURES as CONTRACT_PRICE_FIXTURES
from tests.subscription_test_support import FIXTURES as SUBSCRIPTION_FIXTURES


class ApiMainTests(unittest.TestCase):
    def test_build_service_uses_settings_paths(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )

            transformation_service = build_transformation_service(settings)

            self.assertTrue(settings.resolved_analytics_database_path.exists())
            transformation_service.store.close()

    def test_build_app_returns_fastapi_app(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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

    def test_built_app_loads_custom_pipeline_registries_for_configured_promotion(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            module_name = f"test_custom_pipeline_runtime_{uuid4().hex}"
            module_path = Path(temp_dir) / f"{module_name}.py"
            module_path.write_text(
                "\n".join(
                    [
                        "from packages.pipelines.account_transaction_service import AccountTransactionService",
                        "from packages.pipelines.pipeline_catalog import (",
                        "    PipelinePackageSpec,",
                        "    PipelinePublicationSpec,",
                        ")",
                        "from packages.pipelines.promotion_registry import (",
                        "    register_domain_canonical_promotion_handler,",
                        ")",
                        "from packages.shared.extensions import (",
                        "    ExtensionPublication,",
                        "    LayerExtension,",
                        ")",
                        "",
                        "ACCOUNT_TRANSACTION_HEADER = {",
                        '    "booked_at",',
                        '    "account_id",',
                        '    "counterparty_name",',
                        '    "amount",',
                        '    "currency",',
                        "}",
                        "",
                        "def register_extensions(registry):",
                        "    registry.register(",
                        "        LayerExtension(",
                        '            layer="reporting",',
                        '            key="budget_projection_publication",',
                        '            kind="mart",',
                        '            description="Custom budget projection relation.",',
                        f'            module="{module_name}",',
                        f'            source="{module_name}",',
                        '            data_access="published",',
                        "            publication_relations=(",
                        "                ExtensionPublication(",
                        '                    relation_name="mart_budget_projection",',
                        '                    columns=(("booking_month", "VARCHAR NOT NULL"),),',
                        '                    source_query="SELECT booking_month FROM mart_monthly_cashflow",',
                        '                    order_by="booking_month",',
                        "                ),",
                        "            ),",
                        "        )",
                        "    )",
                        "",
                        "def register_pipeline_registries(*, pipeline_catalog_registry, promotion_handler_registry, transformation_domain_registry, publication_refresh_registry):",
                        "    pipeline_catalog_registry.register(",
                        "        PipelinePackageSpec(",
                        '            transformation_package_id="custom_budget_v1",',
                        '            handler_key="custom_budget_transform",',
                        '            name="Custom budget transform",',
                        "            version=1,",
                        '            description="Custom budget extension package.",',
                        "            publications=(",
                        "                PipelinePublicationSpec(",
                        '                    publication_definition_id="pub_budget_projection",',
                        '                    publication_key="mart_budget_projection",',
                        '                    name="Budget projection",',
                        "                ),",
                        "            ),",
                        "        )",
                        "    )",
                        "    publication_refresh_registry.register(",
                        '        "mart_budget_projection",',
                        "        lambda service: 0,",
                        "    )",
                        "    register_domain_canonical_promotion_handler(",
                        "        promotion_handler_registry=promotion_handler_registry,",
                        "        transformation_domain_registry=transformation_domain_registry,",
                        '        handler_key="custom_budget_transform",',
                        '        domain_key="custom_budget_domain",',
                        '        default_publications=("mart_budget_projection",),',
                        '        refresh_publication_keys=("mart_budget_projection",),',
                        "        build_runtime_service=lambda runtime: AccountTransactionService(",
                        "            landing_root=runtime.landing_root,",
                        "            metadata_repository=runtime.metadata_repository,",
                        "            blob_store=runtime.blob_store,",
                        "        ),",
                        "        get_run=lambda service, run_id: service.get_run(run_id),",
                        "        get_canonical_rows=lambda service, run_id: service.get_canonical_transactions(run_id),",
                        "        serialize_row=lambda row: {",
                        '            "booked_at": str(row.booked_at),',
                        '            "account_id": row.account_id,',
                        '            "counterparty_name": row.counterparty_name,',
                        '            "amount": str(row.amount),',
                        '            "currency": row.currency,',
                        '            "description": row.description or "",',
                        "        },",
                        "        load_rows=lambda service, rows, run_id, effective_date, source_system: service.load_transactions(",
                        "            rows,",
                        "            run_id=run_id,",
                        "            effective_date=effective_date,",
                        "            source_system=source_system,",
                        "        ),",
                        "        count_rows=lambda service, run_id: service.count_transactions(run_id=run_id),",
                        "        required_header=ACCOUNT_TRANSACTION_HEADER,",
                        '        contract_mismatch_reason="run does not match the account-transaction canonical contract",',
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
                extension_paths=(Path(temp_dir),),
                extension_modules=(module_name,),
                enable_unsafe_admin=True,
            )
            config_repository = IngestionConfigRepository(settings.resolved_config_database_path)
            create_account_configuration(config_repository)

            client = TestClient(build_app(settings))
            synced_repository = IngestionConfigRepository(
                settings.resolved_config_database_path
            )
            self.assertEqual(
                "custom_budget_transform",
                synced_repository.get_transformation_package(
                    "custom_budget_v1"
                ).handler_key,
            )
            self.assertEqual(
                "mart_budget_projection",
                synced_repository.get_publication_definition(
                    "pub_budget_projection"
                ).publication_key,
            )
            synced_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="custom_budget_asset",
                    source_system_id=ACCOUNT_SOURCE_SYSTEM_ID,
                    dataset_contract_id=ACCOUNT_CONTRACT_ID,
                    column_mapping_id=ACCOUNT_MAPPING_ID,
                    name="Custom Budget Asset",
                    asset_type="dataset",
                    transformation_package_id="custom_budget_v1",
                )
            )

            ingest_response = client.post(
                "/ingest/configured-csv",
                json={
                    "source_path": str(
                        ACCOUNT_FIXTURES / "configured_account_transactions_source.csv"
                    ),
                    "source_asset_id": "custom_budget_asset",
                    "source_name": "manual-upload",
                },
            )

            self.assertEqual(201, ingest_response.status_code)
            self.assertEqual(
                ["mart_budget_projection"],
                ingest_response.json()["promotion"]["marts_refreshed"],
            )
            self.assertEqual(
                ["mart_budget_projection"],
                ingest_response.json()["promotion"]["publication_keys"],
            )

    def test_built_app_supports_subscription_ingest_and_summary_reporting(self) -> None:
        with TemporaryDirectory() as temp_dir:
            settings = AppSettings(
                data_dir=Path(temp_dir),
                landing_root=Path(temp_dir) / "landing",
                metadata_database_path=Path(temp_dir) / "metadata" / "runs.db",
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                account_transactions_inbox_dir=(Path(temp_dir) / "inbox" / "account-transactions"),
                processed_files_dir=(Path(temp_dir) / "processed" / "account-transactions"),
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
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
                    "source_path": str(CONTRACT_PRICE_FIXTURES / "contract_prices_valid.csv"),
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
