import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.app import create_app
from apps.api.ha_startup import (
    _build_approval_status_state,
    _build_bridge_status_state,
    _compute_contract_renewal_due_count,
    _compute_electricity_cost_forecast_today,
    _compute_maintenance_state,
    _compute_peak_tariff_active,
    build_ha_startup_runtime,
)
from apps.api.main import (
    _build_api_startup_components,
    build_app,
    build_function_registry,
    build_lazy_transformation_service,
    build_reporting_service,
    build_service,
    build_transformation_service,
    main,
)
from packages.domains.finance.manifest import FINANCE_PACK
from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.domains.overview.manifest import OVERVIEW_PACK
from packages.domains.utilities.manifest import UTILITIES_PACK
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.reporting_service import ReportingAccessMode
from packages.platform.runtime.builder import build_container
from packages.shared.external_registry import sync_extension_registry_source
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    ExtensionRegistrySourceCreate,
    IngestionConfigRepository,
    SourceAssetCreate,
    SourceSystemCreate,
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
from tests.external_registry_test_support import (
    create_path_capability_pack_extension,
    create_path_function_extension,
)
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
                settings.resolved_config_database_path,
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

    def test_kernel_container_boots_with_zero_packs_and_exposes_health_routes(self) -> None:
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

            container = build_container(settings, capability_packs=())
            self.assertEqual((), container.capability_packs)

            app = create_app(container)
            with TestClient(app) as client:
                health = client.get("/health")
                ready = client.get("/ready")

            self.assertEqual(200, health.status_code)
            self.assertEqual({"status": "ok"}, health.json())
            self.assertEqual(200, ready.status_code)
            self.assertEqual("ready", ready.json()["status"])

    def test_main_logs_resolved_identity_mode_on_startup_failure(self) -> None:
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
                identity_mode=" local_single_user ",
            )

            mock_logger = Mock()
            with patch("apps.api.main.AppSettings.from_env", return_value=settings), patch(
                "apps.api.main.logging.getLogger",
                return_value=mock_logger,
            ), patch("apps.api.main.build_app", side_effect=ValueError("boom")):
                exit_code = main()

            self.assertEqual(1, exit_code)
            mock_logger.error.assert_called_once()
            self.assertEqual(
                "local_single_user",
                mock_logger.error.call_args.kwargs["extra"]["identity_mode"],
            )

    def test_build_api_startup_components_wires_ha_startup(self) -> None:
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
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )
            container = SimpleNamespace(
                extension_registry="extension-registry",
                control_plane_store="control-plane-store",
                run_metadata_store="run-metadata-store",
                blob_store="blob-store",
            )
            ha_runtime = SimpleNamespace(
                bridge="bridge",
                policy_evaluator="policy-evaluator",
                action_proposal_registry="proposal-registry",
                action_dispatcher="action-dispatcher",
                mqtt_publisher="mqtt-publisher",
            )
            with (
                patch("apps.api.main.build_container", return_value=container),
                patch("apps.api.main.build_service", return_value="account-service"),
                patch(
                    "apps.api.main._runtime_support.build_subscription_service",
                    return_value="subscription-service",
                ),
                patch(
                    "apps.api.main._runtime_support.build_contract_price_service",
                    return_value="contract-price-service",
                ),
                patch(
                    "apps.api.main.build_lazy_transformation_service",
                    return_value="transformation-service",
                ),
                patch(
                    "apps.api.main.build_reporting_service",
                    return_value="reporting-service",
                ),
                patch("apps.api.main.build_session_manager", return_value="session"),
                patch("apps.api.main.build_oidc_provider", return_value="oidc"),
                patch(
                    "apps.api.main.build_machine_jwt_provider",
                    return_value="machine-jwt",
                ),
                patch("apps.api.main.build_proxy_provider", return_value="proxy"),
                patch(
                    "apps.api.main.build_ha_startup_runtime",
                    return_value=ha_runtime,
                ) as mock_build_ha_startup_runtime,
            ):
                runtime = _build_api_startup_components(settings)

            mock_build_ha_startup_runtime.assert_called_once_with(
                settings,
                transformation_service="transformation-service",
                reporting_service="reporting-service",
                capability_packs=[
                    FINANCE_PACK,
                    UTILITIES_PACK,
                    OVERVIEW_PACK,
                    HOMELAB_PACK,
                ],
            )
            self.assertEqual(container, runtime[0])
            self.assertEqual("account-service", runtime[1])
            self.assertEqual("subscription-service", runtime[2])
            self.assertEqual("contract-price-service", runtime[3])
            self.assertEqual("transformation-service", runtime[4])
            self.assertEqual("reporting-service", runtime[5])
            self.assertEqual(ha_runtime, runtime[6])

    def test_build_app_delegates_ha_startup_wiring(self) -> None:
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
                failed_files_dir=(Path(temp_dir) / "failed" / "account-transactions"),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )
            container = SimpleNamespace(
                extension_registry="extension-registry",
                control_plane_store="control-plane-store",
            )
            ha_runtime = SimpleNamespace(
                bridge="bridge",
                policy_evaluator="policy-evaluator",
                action_proposal_registry="proposal-registry",
                action_dispatcher="action-dispatcher",
                mqtt_publisher="mqtt-publisher",
            )
            with (
                patch("apps.api.main.validate_auth_configuration"),
                patch(
                    "apps.api.main._build_api_startup_components",
                    return_value=(
                        container,
                        "account-service",
                        "subscription-service",
                        "contract-price-service",
                        "transformation-service",
                        "reporting-service",
                        ha_runtime,
                    ),
                ) as mock_build_api_startup_components,
                patch("apps.api.main.build_session_manager", return_value="session"),
                patch("apps.api.main.build_oidc_provider", return_value="oidc"),
                patch(
                    "apps.api.main.build_machine_jwt_provider",
                    return_value="machine-jwt",
                ),
                patch("apps.api.main.build_proxy_provider", return_value="proxy"),
                patch("apps.api.main.create_app", return_value=FastAPI()) as mock_create_app,
            ):
                app = build_app(settings)

            mock_build_api_startup_components.assert_called_once_with(settings)
            self.assertIsInstance(app, FastAPI)
            create_kwargs = mock_create_app.call_args.kwargs
            self.assertEqual("account-service", create_kwargs["account_transaction_service"])
            self.assertEqual("subscription-service", create_kwargs["subscription_service"])
            self.assertEqual("contract-price-service", create_kwargs["contract_price_service"])
            self.assertEqual("bridge", create_kwargs["ha_bridge"])
            self.assertEqual("policy-evaluator", create_kwargs["ha_policy_evaluator"])
            self.assertEqual(
                "proposal-registry",
                create_kwargs["ha_action_proposal_registry"],
            )
            self.assertEqual("action-dispatcher", create_kwargs["ha_action_dispatcher"])
            self.assertEqual("mqtt-publisher", create_kwargs["ha_mqtt_publisher"])

    def test_build_function_registry_loads_active_external_functions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            settings = AppSettings(
                data_dir=temp_root,
                landing_root=temp_root / "landing",
                metadata_database_path=temp_root / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    temp_root / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    temp_root / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    temp_root / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
            )
            function_extension = create_path_function_extension(
                temp_root,
                module_name="custom_function_registry_module",
                function_key="normalize_counterparty",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="household-functions",
                    name="Household Functions",
                    source_kind="path",
                    location=str(function_extension.root),
                )
            )
            sync_extension_registry_source(
                repository,
                "household-functions",
                activate=True,
                cache_root=settings.resolved_external_registry_cache_root,
            )

            registry = build_function_registry(settings, config_repository=repository)

            self.assertEqual(
                "normalize_counterparty",
                registry.list(kind="column_mapping_value")[0].function_key,
            )

    def test_build_app_applies_active_external_functions_to_mapping_preview(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            settings = AppSettings(
                data_dir=temp_root,
                landing_root=temp_root / "landing",
                metadata_database_path=temp_root / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    temp_root / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    temp_root / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    temp_root / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
                enable_unsafe_admin=True,
            )
            function_extension = create_path_function_extension(
                temp_root,
                module_name="custom_function_preview_module",
                function_key="normalize_counterparty",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="household-functions",
                    name="Household Functions",
                    source_kind="path",
                    location=str(function_extension.root),
                )
            )
            sync_extension_registry_source(
                repository,
                "household-functions",
                activate=True,
                cache_root=settings.resolved_external_registry_cache_root,
            )
            repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                    ),
                )
            )
            repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule(
                            "counterparty_name",
                            source_column="payee",
                            function_key="normalize_counterparty",
                        ),
                    ),
                )
            )
            client = TestClient(build_app(settings))

            functions_response = client.get("/functions")
            self.assertEqual(200, functions_response.status_code)
            self.assertEqual(
                "normalize_counterparty",
                functions_response.json()["functions"]["column_mapping_value"][0][
                    "function_key"
                ],
            )

            preview_response = client.post(
                "/config/column-mappings/preview",
                json={
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                    "sample_csv": "\n".join(
                        [
                            "booking_date,account_number,payee",
                            "2026-01-01,ACC-001,coffee shop",
                        ]
                    )
                    + "\n",
                    "preview_limit": 5,
                },
            )
            self.assertEqual(200, preview_response.status_code)
            self.assertEqual(
                "normalized:coffee shop",
                preview_response.json()["preview"]["preview_rows"][0][
                    "counterparty_name"
                ],
            )

    def test_build_app_exposes_external_capability_pack_contracts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            extension = create_path_capability_pack_extension(
                temp_root,
                module_name="custom_contract_pack",
                pack_name="custom_contracts",
                publication_key="mart_external_projection",
            )
            settings = AppSettings(
                data_dir=temp_root,
                landing_root=temp_root / "landing",
                metadata_database_path=temp_root / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    temp_root / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    temp_root / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    temp_root / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
                extension_paths=(extension.root,),
                extension_modules=(extension.module_name,),
                enable_unsafe_admin=True,
            )

            client = TestClient(build_app(settings))

            publication_response = client.get("/contracts/publications")
            self.assertEqual(200, publication_response.status_code)
            publication_keys = {
                contract["publication_key"]
                for contract in publication_response.json()["publication_contracts"]
            }
            self.assertIn("mart_external_projection", publication_keys)

            descriptor_response = client.get("/contracts/ui-descriptors")
            self.assertEqual(200, descriptor_response.status_code)
            descriptor_keys = {
                descriptor["key"]
                for descriptor in descriptor_response.json()["ui_descriptors"]
            }
            self.assertIn("custom_contracts-dashboard", descriptor_keys)

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
                identity_mode="local",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_SESSION_SECRET",
            ):
                build_app(settings)

    def test_build_app_accepts_local_single_user_alias(self) -> None:
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
                identity_mode="local_single_user",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_SESSION_SECRET",
            ):
                build_app(settings)

    def test_build_app_rejects_local_single_user_without_break_glass_enabled(self) -> None:
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
                identity_mode="local_single_user",
                session_secret="session-secret",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_BREAK_GLASS_ENABLED=true",
            ):
                build_app(settings)

    def test_build_app_rejects_break_glass_outside_local_single_user_mode(self) -> None:
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
                identity_mode="local",
                session_secret="session-secret",
                break_glass_enabled=True,
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_IDENTITY_MODE=local_single_user",
            ):
                build_app(settings)

    def test_build_app_rejects_invalid_break_glass_cidr_entry(self) -> None:
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
                identity_mode="local_single_user",
                session_secret="session-secret",
                break_glass_enabled=True,
                break_glass_allowed_cidrs=("not-a-cidr",),
            )

            with self.assertRaisesRegex(
                ValueError,
                "Invalid break-glass CIDR entry",
            ):
                build_app(settings)

    def test_build_app_rejects_proxy_auth_mode_without_trusted_cidrs(self) -> None:
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
                identity_mode="proxy",
            )

            with self.assertRaisesRegex(
                ValueError,
                "HOMELAB_ANALYTICS_PROXY_TRUSTED_CIDRS",
            ):
                build_app(settings)

    def test_build_app_accepts_proxy_auth_mode_with_trusted_cidrs(self) -> None:
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
                identity_mode="proxy",
                proxy_trusted_cidrs=("10.0.0.0/8",),
            )

            client = TestClient(build_app(settings))
            response = client.get(
                "/runs",
                headers={"x-forwarded-for": "10.2.3.4"},
            )
            self.assertEqual(401, response.status_code)

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
                identity_mode="local",
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
            with patch(
                "packages.platform.runtime.builder.build_reporting_store",
                return_value=object(),
            ):
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
                        "from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService",
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
            handler_response = client.get("/config/transformation-handlers")
            self.assertEqual(200, handler_response.status_code)
            self.assertTrue(
                any(
                    handler["handler_key"] == "custom_budget_transform"
                    and handler["supported_publications"]
                    == ["mart_budget_projection"]
                    for handler in handler_response.json()["transformation_handlers"]
                )
            )
            publication_response = client.get("/config/publication-keys")
            self.assertEqual(200, publication_response.status_code)
            self.assertTrue(
                any(
                    publication["publication_key"] == "mart_budget_projection"
                    and "custom_budget_transform"
                    in publication["supported_handlers"]
                    and "budget_projection_publication"
                    in publication["reporting_extensions"]
                    for publication in publication_response.json()["publication_keys"]
                )
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

    def test_build_ha_startup_runtime_wires_optional_components_when_configured(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            settings = AppSettings(
                data_dir=temp_root,
                landing_root=temp_root / "landing",
                metadata_database_path=temp_root / "metadata" / "runs.db",
                account_transactions_inbox_dir=(
                    temp_root / "inbox" / "account-transactions"
                ),
                processed_files_dir=(
                    temp_root / "processed" / "account-transactions"
                ),
                failed_files_dir=(
                    temp_root / "failed" / "account-transactions"
                ),
                api_host="127.0.0.1",
                api_port=8090,
                web_host="127.0.0.1",
                web_port=8091,
                worker_poll_interval_seconds=1,
                ha_url="http://ha.local:8123",
                ha_token="test-token",
                ha_mqtt_broker_url="mqtt://broker.local:1883",
            )

            runtime = build_ha_startup_runtime(
                settings,
                transformation_service=Mock(),
                reporting_service=Mock(),
                capability_packs=(),
            )

            self.assertIsNotNone(runtime.bridge)
            self.assertIsNotNone(runtime.action_dispatcher)
            self.assertIsNotNone(runtime.mqtt_publisher)
            self.assertIsNotNone(runtime.policy_evaluator)
            self.assertIsNotNone(runtime.action_proposal_registry)


class MqttSyntheticStateTests(unittest.TestCase):
    def test_peak_tariff_active_uses_weekday_window(self) -> None:
        from datetime import datetime

        self.assertEqual(
            "peak",
            _compute_peak_tariff_active(
                [{"contract_id": "electricity"}],
                now=datetime(2026, 3, 24, 12, 0, 0),
            ),
        )

    def test_peak_tariff_active_returns_unavailable_without_rows(self) -> None:
        self.assertEqual("unavailable", _compute_peak_tariff_active([], now=None))

    def test_electricity_cost_forecast_today_prefers_latest_day_total(self) -> None:
        class _Reporting:
            def get_utility_cost_summary(self, **kwargs):
                return [
                    {"period_day": "2026-03-24", "billed_amount": "4.50"},
                    {"period_day": "2026-03-25", "billed_amount": "3.25"},
                    {"period_day": "2026-03-25", "billed_amount": "1.75"},
                ]

            def get_utility_cost_trend_monthly(self, **kwargs):
                raise AssertionError("fallback should not be used when day rows exist")

        self.assertEqual(
            "5",
            _compute_electricity_cost_forecast_today(
                _Reporting(),
                now=None,
            ),
        )

    def test_electricity_cost_forecast_today_falls_back_to_monthly_trend(self) -> None:
        from datetime import datetime

        class _Reporting:
            def get_utility_cost_summary(self, **kwargs):
                return []

            def get_utility_cost_trend_monthly(self, **kwargs):
                return [{"billing_month": "2026-03", "total_cost": "31.00"}]

        self.assertEqual(
            "1",
            _compute_electricity_cost_forecast_today(
                _Reporting(),
                now=datetime(2026, 3, 15, 12, 0, 0),
            ),
        )

    def test_maintenance_state_uses_service_and_storage_pressure(self) -> None:
        class _Reporting:
            def get_service_health_current(self):
                return [{"state": "running"}, {"state": "degraded"}]

            def get_storage_risk(self):
                return [{"risk_tier": "ok"}, {"risk_tier": "crit"}]

        due_state, issue_count = _compute_maintenance_state(_Reporting())
        self.assertEqual("on", due_state)
        self.assertEqual("2", issue_count)

    def test_contract_renewal_due_count_uses_watchlist_size(self) -> None:
        class _Reporting:
            def get_contract_renewal_watchlist(self):
                return [{"contract_id": "a"}, {"contract_id": "b"}]

        self.assertEqual("2", _compute_contract_renewal_due_count(_Reporting()))


class HaStartupStatusStateTests(unittest.TestCase):
    def test_bridge_status_defaults_without_bridge(self) -> None:
        self.assertEqual(
            {
                "bridge_connected": False,
                "bridge_last_sync_at": None,
                "bridge_reconnect_count": 0,
            },
            _build_bridge_status_state(None),
        )

    def test_bridge_status_uses_bridge_snapshot(self) -> None:
        class _Bridge:
            def get_status(self):
                return {
                    "connected": True,
                    "last_sync_at": "2026-03-28T20:37:00+00:00",
                    "reconnect_count": 3,
                }

        self.assertEqual(
            {
                "bridge_connected": True,
                "bridge_last_sync_at": "2026-03-28T20:37:00+00:00",
                "bridge_reconnect_count": 3,
            },
            _build_bridge_status_state(_Bridge()),
        )

    def test_approval_status_defaults_without_dispatcher(self) -> None:
        self.assertEqual(
            {
                "approval_tracked_count": 0,
                "approval_pending_count": 0,
            },
            _build_approval_status_state(None),
        )

    def test_approval_status_uses_dispatcher_snapshot(self) -> None:
        class _Dispatcher:
            def get_status(self):
                return {
                    "approval_tracked_count": 4,
                    "approval_pending_count": 2,
                }

        self.assertEqual(
            {
                "approval_tracked_count": 4,
                "approval_pending_count": 2,
            },
            _build_approval_status_state(_Dispatcher()),
        )


if __name__ == "__main__":
    unittest.main()
