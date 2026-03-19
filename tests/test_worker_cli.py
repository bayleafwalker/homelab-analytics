import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from apps.worker.main import build_service, main
from packages.pipelines.bootstrap_account_transaction_watch import (
    LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID,
)
from packages.pipelines.csv_validation import ColumnType
from packages.shared.secrets import build_secret_env_var_name
from packages.shared.settings import AppSettings
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    ExtensionRegistrySourceCreate,
    IngestionConfigRepository,
    IngestionDefinitionCreate,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceSystemCreate,
)
from tests.external_registry_test_support import (
    create_git_extension_repository,
    create_path_function_extension,
    create_path_pipeline_extension,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class WorkerCliTests(unittest.TestCase):
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            service = build_service(settings)

            self.assertEqual(settings.landing_root, service.landing_root)
            self.assertEqual(
                settings.metadata_database_path,
                service.metadata_repository.database_path,
            )

    def test_cli_ingest_and_report_commands_emit_json(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "ingest-account-transactions",
                    str(FIXTURES / "account_transactions_valid.csv"),
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)

            ingest_payload = json.loads(stdout.getvalue())
            self.assertEqual("landed", ingest_payload["run"]["status"])
            self.assertIn("promotion", ingest_payload)
            self.assertFalse(ingest_payload["promotion"]["skipped"])
            run_id = ingest_payload["run"]["run_id"]

            stdout = io.StringIO()
            exit_code = main(
                ["report-monthly-cashflow", run_id],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            report_payload = json.loads(stdout.getvalue())
            self.assertEqual("2365.8500", report_payload["rows"][0]["net"])

    def test_cli_lists_loaded_extensions(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                ["list-extensions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertIn("landing", payload["extensions"])
            self.assertTrue(
                any(
                    extension["key"] == "account_transactions_canonical"
                    for extension in payload["extensions"]["transformation"]
                )
            )
            monthly_cashflow_extension = next(
                extension
                for extension in payload["extensions"]["reporting"]
                if extension["key"] == "monthly_cashflow_summary"
            )
            self.assertEqual("published", monthly_cashflow_extension["data_access"])
            self.assertEqual([], monthly_cashflow_extension["publication_relations"])

    def test_cli_syncs_path_extension_registry_source_and_loads_activated_extensions(
        self,
    ) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            extension_root = Path(temp_dir) / "custom-extension"
            extension_root.mkdir(parents=True, exist_ok=True)
            module_name = "custom_worker_extension"
            (extension_root / f"{module_name}.py").write_text(
                "\n".join(
                    [
                        "from packages.shared.extensions import LayerExtension",
                        "",
                        "def register_extensions(registry):",
                        "    registry.register(",
                        "        LayerExtension(",
                        '            layer=\"reporting\",',
                        '            key=\"worker_loaded_projection\",',
                        '            kind=\"mart\",',
                        '            description=\"Worker-loaded projection.\",',
                        f'            module=\"{module_name}\",',
                        '            source=\"custom-worker-extension\",',
                        "        )",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (extension_root / "homelab-analytics.registry.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "import_paths": ["."],
                        "extension_modules": [module_name],
                        "function_modules": [],
                        "minimum_platform_version": "0.1.0",
                    }
                ),
                encoding="utf-8",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="worker-custom-extension",
                    name="Worker Custom Extension",
                    source_kind="path",
                    location=str(extension_root),
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "sync-extension-registry-source",
                    "worker-custom-extension",
                    "--activate",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            sync_payload = json.loads(stdout.getvalue())
            self.assertEqual(
                "validated",
                sync_payload["extension_registry_revision"]["sync_status"],
            )
            self.assertEqual(
                "worker-custom-extension",
                sync_payload["extension_registry_activation"][
                    "extension_registry_source_id"
                ],
            )

            stdout = io.StringIO()
            exit_code = main(
                ["list-extensions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    extension["key"] == "worker_loaded_projection"
                    for extension in payload["extensions"]["reporting"]
                )
            )

    def test_cli_syncs_git_extension_registry_source_and_loads_activated_extensions(
        self,
    ) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            git_repository = create_git_extension_repository(
                Path(temp_dir),
                module_name="custom_git_worker_extension",
                extension_key="worker_git_loaded_projection",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="worker-git-extension",
                    name="Worker Git Extension",
                    source_kind="git",
                    location=str(git_repository.repo_root),
                    desired_ref="main",
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "sync-extension-registry-source",
                    "worker-git-extension",
                    "--activate",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            sync_payload = json.loads(stdout.getvalue())
            self.assertEqual(
                git_repository.commit_sha,
                sync_payload["extension_registry_revision"]["resolved_ref"],
            )
            self.assertEqual(
                "validated",
                sync_payload["extension_registry_revision"]["sync_status"],
            )

            stdout = io.StringIO()
            exit_code = main(
                ["list-extensions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    extension["key"] == "worker_git_loaded_projection"
                    for extension in payload["extensions"]["reporting"]
                )
            )

    def test_cli_lists_loaded_functions_from_activated_external_registry(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            function_extension = create_path_function_extension(
                Path(temp_dir),
                module_name="custom_worker_function_module",
                function_key="normalize_counterparty",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="worker-functions",
                    name="Worker Functions",
                    source_kind="path",
                    location=str(function_extension.root),
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "sync-extension-registry-source",
                    "worker-functions",
                    "--activate",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)

            stdout = io.StringIO()
            exit_code = main(
                ["list-functions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                "normalize_counterparty",
                payload["functions"]["column_mapping_value"][0]["function_key"],
            )

    def test_cli_lists_transformation_packages_and_publication_definitions(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                ["list-transformation-packages"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            package_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    package["transformation_package_id"]
                    == "builtin_account_transactions"
                    and package["handler_key"] == "account_transactions"
                    for package in package_payload["transformation_packages"]
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "list-publication-definitions",
                    "--transformation-package-id",
                    "builtin_account_transactions",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            publication_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    definition["publication_definition_id"]
                    == "pub_account_transactions_monthly_cashflow"
                    and definition["publication_key"] == "mart_monthly_cashflow"
                    for definition in publication_payload["publication_definitions"]
                )
            )

    def test_cli_lists_transformation_handlers_and_publication_keys_from_activated_external_registry(
        self,
    ) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            pipeline_extension = create_path_pipeline_extension(
                Path(temp_dir),
                module_name="custom_worker_pipeline_module",
                handler_key="custom_worker_transform",
                publication_key="mart_worker_projection",
                transformation_package_id="custom_worker_package_v1",
            )
            repository = IngestionConfigRepository(settings.resolved_config_database_path)
            repository.create_extension_registry_source(
                ExtensionRegistrySourceCreate(
                    extension_registry_source_id="worker-pipeline-extension",
                    name="Worker Pipeline Extension",
                    source_kind="path",
                    location=str(pipeline_extension.root),
                )
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "sync-extension-registry-source",
                    "worker-pipeline-extension",
                    "--activate",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)

            stdout = io.StringIO()
            exit_code = main(
                ["list-transformation-handlers"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            handler_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    handler["handler_key"] == "custom_worker_transform"
                    and handler["supported_publications"]
                    == ["mart_worker_projection"]
                    for handler in handler_payload["transformation_handlers"]
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                ["list-publication-keys"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            publication_key_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    publication["publication_key"] == "mart_worker_projection"
                    and "custom_worker_transform"
                    in publication["supported_handlers"]
                    and "custom_pipeline_publication"
                    in publication["reporting_extensions"]
                    for publication in publication_key_payload["publication_keys"]
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                ["list-transformation-packages"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            package_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    package["transformation_package_id"] == "custom_worker_package_v1"
                    and package["handler_key"] == "custom_worker_transform"
                    for package in package_payload["transformation_packages"]
                )
            )

            stdout = io.StringIO()
            exit_code = main(
                [
                    "list-publication-definitions",
                    "--transformation-package-id",
                    "custom_worker_package_v1",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            definition_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                any(
                    definition["publication_definition_id"] == "pub_external_pipeline"
                    and definition["publication_key"] == "mart_worker_projection"
                    for definition in definition_payload["publication_definitions"]
                )
            )

    def test_cli_runs_transformation_extension(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "ingest-account-transactions",
                    str(FIXTURES / "account_transactions_valid.csv"),
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            run_id = json.loads(stdout.getvalue())["run"]["run_id"]

            stdout = io.StringIO()
            exit_code = main(
                [
                    "run-transformation-extension",
                    "account_transactions_canonical",
                    run_id,
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("CHK-001", payload["result"][0]["account_id"])
            self.assertEqual("2450.00", payload["result"][1]["amount"])

    def test_cli_runs_reporting_extension(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "ingest-account-transactions",
                    str(FIXTURES / "account_transactions_valid.csv"),
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            run_id = json.loads(stdout.getvalue())["run"]["run_id"]

            stdout = io.StringIO()
            exit_code = main(
                [
                    "run-reporting-extension",
                    "monthly_cashflow_summary",
                    run_id,
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("2365.8500", payload["result"][0]["net"])

    def test_cli_processes_persisted_ingestion_definition(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            inbox_dir = Path(temp_dir) / "configured-inbox"
            processed_dir = Path(temp_dir) / "configured-processed"
            failed_dir = Path(temp_dir) / "configured-failed"
            inbox_dir.mkdir()
            (inbox_dir / "valid.csv").write_text(
                (FIXTURES / "configured_account_transactions_source.csv").read_text()
            )

            config_repository = IngestionConfigRepository(
                settings.landing_root.parent / "config.db"
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                        DatasetColumnConfig(
                            "description",
                            ColumnType.STRING,
                            required=False,
                        ),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                        ColumnMappingRule("description", source_column="memo"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            config_repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="bank_partner_watch_folder",
                    source_asset_id="bank_partner_transactions",
                    transport="filesystem",
                    schedule_mode="watch-folder",
                    source_path=str(inbox_dir),
                    file_pattern="*.csv",
                    processed_path=str(processed_dir),
                    failed_path=str(failed_dir),
                    poll_interval_seconds=30,
                    enabled=True,
                    source_name="folder-watch",
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                ["process-ingestion-definition", "bank_partner_watch_folder"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["result"]["processed_files"])
            self.assertEqual(0, payload["result"]["rejected_files"])

    def test_cli_bootstraps_account_transaction_watch_folder_into_configured_flow(
        self,
    ) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            settings.account_transactions_inbox_dir.mkdir(parents=True)
            (
                settings.account_transactions_inbox_dir / "valid.csv"
            ).write_text((FIXTURES / "account_transactions_valid.csv").read_text())

            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                ["process-account-transactions-inbox"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["result"]["discovered_files"])
            self.assertEqual(1, payload["result"]["processed_files"])
            self.assertEqual(0, payload["result"]["rejected_files"])
            self.assertEqual([], list(settings.account_transactions_inbox_dir.iterdir()))
            self.assertEqual(1, len(list(settings.processed_files_dir.iterdir())))
            self.assertEqual([], list(settings.failed_files_dir.iterdir()))

            config_repository = IngestionConfigRepository(
                settings.landing_root.parent / "config.db"
            )
            ingestion_definition = config_repository.get_ingestion_definition(
                LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID
            )
            self.assertEqual(
                str(settings.account_transactions_inbox_dir),
                ingestion_definition.source_path,
            )
            self.assertEqual(
                str(settings.processed_files_dir),
                ingestion_definition.processed_path,
            )
            self.assertEqual(
                str(settings.failed_files_dir),
                ingestion_definition.failed_path,
            )

    def test_cli_processes_http_ingestion_definition(self) -> None:
        from tests.test_configured_ingestion_definition import run_csv_server

        with TemporaryDirectory() as temp_dir, run_csv_server(
            response_body=(
                FIXTURES / "configured_account_transactions_source.csv"
            ).read_bytes(),
            expected_authorization="Bearer worker-token",
        ) as server:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            config_repository = IngestionConfigRepository(
                settings.landing_root.parent / "config.db"
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="utility_api",
                    name="Utility API",
                    source_type="api",
                    transport="http",
                    schedule_mode="scheduled",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                        DatasetColumnConfig(
                            "description",
                            ColumnType.STRING,
                            required=False,
                        ),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="utility_api_v1",
                    source_system_id="utility_api",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                        ColumnMappingRule("description", source_column="memo"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="utility_api_asset",
                    source_system_id="utility_api",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="utility_api_v1",
                    name="Utility API Asset",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            config_repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="utility_api_pull",
                    source_asset_id="utility_api_asset",
                    transport="http",
                    schedule_mode="direct-api",
                    source_path="",
                    request_url=f"http://127.0.0.1:{server.server_address[1]}/api.csv",
                    request_method="GET",
                    request_headers=(
                        RequestHeaderSecretRef(
                            name="Authorization",
                            secret_name="utility-api",
                            secret_key="bearer-token",
                        ),
                    ),
                    response_format="csv",
                    output_file_name="api.csv",
                    request_timeout_seconds=30,
                    enabled=True,
                    source_name="scheduled-api-pull",
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with patch.dict(
                os.environ,
                {
                    build_secret_env_var_name(
                        "utility-api",
                        "bearer-token",
                    ): "Bearer worker-token"
                },
                clear=False,
            ):
                exit_code = main(
                    ["process-ingestion-definition", "utility_api_pull"],
                    stdout=stdout,
                    stderr=stderr,
                    settings=settings,
                )

            self.assertEqual(0, exit_code)
            self.assertEqual("Bearer worker-token", server.seen_authorization)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["result"]["processed_files"])
            self.assertEqual(0, payload["result"]["rejected_files"])

    def test_cli_verify_config_reports_valid_graph(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            config_repository = IngestionConfigRepository(
                settings.resolved_config_database_path
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            config_repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="bank_partner_watch_folder",
                    source_asset_id="bank_partner_transactions",
                    transport="filesystem",
                    schedule_mode="watch-folder",
                    source_path="/tmp/inbox",
                    file_pattern="*.csv",
                    processed_path="/tmp/processed",
                    failed_path="/tmp/failed",
                    poll_interval_seconds=30,
                    enabled=True,
                    source_name="folder-watch",
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                ["verify-config", "--source-asset-id", "bank_partner_transactions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["report"]["passed"])
            self.assertEqual([], payload["report"]["issues"])
            self.assertEqual(
                "bank_partner_transactions",
                payload["report"]["scope"]["source_asset_id"],
            )

    def test_cli_verify_config_returns_nonzero_with_json_report_for_invalid_graph(
        self,
    ) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            config_repository = IngestionConfigRepository(
                settings.resolved_config_database_path
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("not_in_contract", default_value="bad"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                ["verify-config", "--source-asset-id", "bank_partner_transactions"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(1, exit_code)
            self.assertEqual("", stderr.getvalue())
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["report"]["passed"])
            self.assertEqual(
                {
                    "missing_required_mapping",
                    "unknown_target_column",
                },
                {issue["code"] for issue in payload["report"]["issues"]},
            )

    def test_cli_ingest_configured_csv_command(self) -> None:
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
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )

            config_repository = IngestionConfigRepository(
                settings.resolved_config_database_path
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                        DatasetColumnConfig(
                            "description",
                            ColumnType.STRING,
                            required=False,
                        ),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                        ColumnMappingRule("description", source_column="memo"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    transformation_package_id="builtin_account_transactions",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                )
            )

            source_file = FIXTURES / "configured_account_transactions_source.csv"
            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                [
                    "ingest-configured-csv",
                    str(source_file),
                    "--source-asset-id", "bank_partner_transactions",
                    "--source-name", "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual("landed", payload["run"]["status"])
            self.assertEqual("manual-upload", payload["run"]["source_name"])
            self.assertIn("promotion", payload)
            self.assertFalse(payload["promotion"]["skipped"])

    def test_promote_run_command_loads_facts_and_refreshes_marts(self) -> None:
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
                analytics_database_path=Path(temp_dir) / "analytics" / "warehouse.duckdb",
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            # Ingest first
            exit_code = main(
                [
                    "ingest-account-transactions",
                    str(FIXTURES / "account_transactions_valid.csv"),
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            run_id = json.loads(stdout.getvalue())["run"]["run_id"]

            # Re-promoting the same run should be a no-op.
            stdout = io.StringIO()
            exit_code = main(
                ["promote-run", run_id],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            promo_payload = json.loads(stdout.getvalue())
            promo = promo_payload["promotion"]
            self.assertEqual(run_id, promo["run_id"])
            self.assertTrue(promo["skipped"])
            self.assertEqual("run already promoted", promo["skip_reason"])
            self.assertEqual(0, promo["facts_loaded"])
            self.assertIn("mart_monthly_cashflow", promo["marts_refreshed"])
            self.assertIn("mart_monthly_cashflow_by_counterparty", promo["marts_refreshed"])

    def test_process_ingestion_definition_command_returns_promotions(self) -> None:
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
                analytics_database_path=Path(temp_dir) / "analytics" / "warehouse.duckdb",
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            inbox_dir = Path(temp_dir) / "configured-inbox"
            processed_dir = Path(temp_dir) / "configured-processed"
            failed_dir = Path(temp_dir) / "configured-failed"
            inbox_dir.mkdir()
            (inbox_dir / "valid.csv").write_text(
                (FIXTURES / "configured_account_transactions_source.csv").read_text()
            )

            config_repository = IngestionConfigRepository(
                settings.resolved_config_database_path
            )
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_partner_export",
                    name="Bank Partner Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_account_transactions_v1",
                    dataset_name="household_account_transactions",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("booked_at", ColumnType.DATE),
                        DatasetColumnConfig("account_id", ColumnType.STRING),
                        DatasetColumnConfig("counterparty_name", ColumnType.STRING),
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                        DatasetColumnConfig(
                            "description",
                            ColumnType.STRING,
                            required=False,
                        ),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_partner_export_v1",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                        ColumnMappingRule("description", source_column="memo"),
                    ),
                )
            )
            config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_partner_transactions",
                    source_system_id="bank_partner_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_partner_export_v1",
                    name="Bank Partner Transactions",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            config_repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="bank_partner_watch_folder",
                    source_asset_id="bank_partner_transactions",
                    transport="filesystem",
                    schedule_mode="watch-folder",
                    source_path=str(inbox_dir),
                    file_pattern="*.csv",
                    processed_path=str(processed_dir),
                    failed_path=str(failed_dir),
                    poll_interval_seconds=30,
                    enabled=True,
                    source_name="folder-watch",
                )
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            exit_code = main(
                ["process-ingestion-definition", "bank_partner_watch_folder"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )

            self.assertEqual(0, exit_code)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(1, payload["result"]["processed_files"])
            self.assertEqual(1, len(payload["promotions"]))
            self.assertFalse(payload["promotions"][0]["skipped"])

    def test_ingest_subscriptions_and_report_summary_commands(self) -> None:
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
                analytics_database_path=Path(temp_dir) / "analytics" / "warehouse.duckdb",
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            # Ingest subscriptions file
            exit_code = main(
                [
                    "ingest-subscriptions",
                    str(FIXTURES / "subscriptions_valid.csv"),
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            ingest_payload = json.loads(stdout.getvalue())
            self.assertEqual("landed", ingest_payload["run"]["status"])
            self.assertIn("promotion", ingest_payload)
            promo = ingest_payload["promotion"]
            self.assertFalse(promo["skipped"])
            self.assertEqual(5, promo["facts_loaded"])
            self.assertEqual(
                ["mart_subscription_summary", "mart_upcoming_fixed_costs_30d"],
                promo["marts_refreshed"],
            )

            # Report subscription summary
            stdout = io.StringIO()
            exit_code = main(
                ["report-subscription-summary"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            report_payload = json.loads(stdout.getvalue())
            self.assertIn("rows", report_payload)
            self.assertEqual(5, len(report_payload["rows"]))

            # Filter by active status
            stdout = io.StringIO()
            exit_code = main(
                ["report-subscription-summary", "--status", "active"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            active_payload = json.loads(stdout.getvalue())
            self.assertTrue(
                all(r["status"] == "active" for r in active_payload["rows"])
            )

    def test_ingest_contract_prices_and_report_commands(self) -> None:
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
                analytics_database_path=Path(temp_dir) / "analytics" / "warehouse.duckdb",
                api_host="0.0.0.0",
                api_port=8080,
                web_host="0.0.0.0",
                web_port=8081,
                worker_poll_interval_seconds=1,
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            exit_code = main(
                [
                    "ingest-contract-prices",
                    str(FIXTURES / "contract_prices_valid.csv"),
                    "--source-name",
                    "manual-upload",
                ],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            ingest_payload = json.loads(stdout.getvalue())
            self.assertEqual("landed", ingest_payload["run"]["status"])
            self.assertIn("promotion", ingest_payload)
            self.assertFalse(ingest_payload["promotion"]["skipped"])
            self.assertEqual(
                [
                    "mart_contract_price_current",
                    "mart_electricity_price_current",
                    "mart_contract_review_candidates",
                    "mart_contract_renewal_watchlist",
                ],
                ingest_payload["promotion"]["marts_refreshed"],
            )

            stdout = io.StringIO()
            exit_code = main(
                ["report-contract-prices"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            contract_payload = json.loads(stdout.getvalue())
            self.assertEqual(3, len(contract_payload["rows"]))
            self.assertEqual(
                {"broadband", "electricity"},
                {row["contract_type"] for row in contract_payload["rows"]},
            )

            stdout = io.StringIO()
            exit_code = main(
                ["report-electricity-prices"],
                stdout=stdout,
                stderr=stderr,
                settings=settings,
            )
            self.assertEqual(0, exit_code)
            electricity_payload = json.loads(stdout.getvalue())
            self.assertEqual(2, len(electricity_payload["rows"]))
            self.assertTrue(
                all(
                    row["contract_type"] == "electricity"
                    for row in electricity_payload["rows"]
                )
            )


if __name__ == "__main__":
    unittest.main()
