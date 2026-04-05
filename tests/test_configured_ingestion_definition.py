import os
import shutil
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from packages.pipelines.configured_ingestion_definition import (
    ConfiguredIngestionDefinitionService,
)
from packages.pipelines.csv_validation import ColumnType
from packages.shared.secrets import build_secret_env_var_name
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    IngestionDefinitionCreate,
    RequestHeaderSecretRef,
    SourceAssetCreate,
    SourceSystemCreate,
)
from packages.storage.run_metadata import IngestionRunStatus, RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


@contextmanager
def run_csv_server(
    *,
    response_body: bytes,
    expected_authorization: str | None = None,
):
    class CsvHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if expected_authorization is not None:
                self.server.seen_authorization = self.headers.get("Authorization")
                if self.headers.get("Authorization") != expected_authorization:
                    self.send_response(401)
                    self.end_headers()
                    return

            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format, *args):
            del format, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), CsvHandler)
    server.seen_authorization = None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class ConfiguredIngestionDefinitionServiceTests(unittest.TestCase):
    def test_watch_folder_definition_processes_valid_and_invalid_csv_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            inbox_dir = temp_root / "configured-inbox"
            processed_dir = temp_root / "configured-processed"
            failed_dir = temp_root / "configured-failed"
            inbox_dir.mkdir()
            shutil.copyfile(
                FIXTURES / "configured_account_transactions_source.csv",
                inbox_dir / "valid.csv",
            )
            shutil.copyfile(
                FIXTURES / "configured_account_transactions_invalid_source.csv",
                inbox_dir / "invalid.csv",
            )

            config_repository = IngestionConfigRepository(temp_root / "config.db")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
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
            service = ConfiguredIngestionDefinitionService(
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
            )

            result = service.process_ingestion_definition("bank_partner_watch_folder")

            self.assertEqual("bank_partner_watch_folder", result.ingestion_definition_id)
            self.assertEqual(2, result.discovered_files)
            self.assertEqual(1, result.processed_files)
            self.assertEqual(1, result.rejected_files)
            self.assertEqual([], list(inbox_dir.iterdir()))
            self.assertEqual(1, len(list(processed_dir.iterdir())))
            self.assertEqual(1, len(list(failed_dir.iterdir())))

            runs = metadata_repository.list_runs()
            self.assertEqual(2, len(runs))
            self.assertEqual(
                {IngestionRunStatus.LANDED, IngestionRunStatus.REJECTED},
                {run.status for run in runs},
            )

    def test_http_definition_processes_direct_api_csv_pull(self) -> None:
        with TemporaryDirectory() as temp_dir, run_csv_server(
            response_body=(
                FIXTURES / "configured_account_transactions_source.csv"
            ).read_bytes(),
            expected_authorization="Bearer test-token",
        ) as server:
            temp_root = Path(temp_dir)
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
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
                    request_url=(
                        f"http://127.0.0.1:{server.server_address[1]}/transactions.csv"
                    ),
                    request_method="GET",
                    request_headers=(
                        RequestHeaderSecretRef(
                            name="Authorization",
                            secret_name="utility-api",
                            secret_key="bearer-token",
                        ),
                    ),
                    response_format="csv",
                    output_file_name="transactions.csv",
                    request_timeout_seconds=30,
                    enabled=True,
                    source_name="scheduled-api-pull",
                )
            )
            with patch.dict(
                os.environ,
                {
                    build_secret_env_var_name(
                        "utility-api",
                        "bearer-token",
                    ): "Bearer test-token"
                },
                clear=False,
            ):
                service = ConfiguredIngestionDefinitionService(
                    landing_root=temp_root / "landing",
                    metadata_repository=metadata_repository,
                    config_repository=config_repository,
                )

                result = service.process_ingestion_definition("utility_api_pull")

            self.assertEqual(1, result.discovered_files)
            self.assertEqual(1, result.processed_files)
            self.assertEqual(0, result.rejected_files)
            self.assertEqual("Bearer test-token", server.seen_authorization)

            runs = metadata_repository.list_runs()
            self.assertEqual(1, len(runs))
            self.assertEqual(IngestionRunStatus.LANDED, runs[0].status)

    def test_http_definition_processes_batch_extract_csv_pull(self) -> None:
        with TemporaryDirectory() as temp_dir, run_csv_server(
            response_body=(
                FIXTURES / "configured_account_transactions_invalid_source.csv"
            ).read_bytes()
        ) as server:
            temp_root = Path(temp_dir)
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="batch_extract_source",
                    name="Batch Extract Source",
                    source_type="batch-extract",
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
                    column_mapping_id="batch_extract_v1",
                    source_system_id="batch_extract_source",
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
                    source_asset_id="batch_extract_asset",
                    source_system_id="batch_extract_source",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="batch_extract_v1",
                    name="Batch Extract Asset",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )
            config_repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="batch_extract_pull",
                    source_asset_id="batch_extract_asset",
                    transport="http",
                    schedule_mode="batch-extract",
                    source_path="",
                    request_url=f"http://127.0.0.1:{server.server_address[1]}/extract.csv",
                    request_method="GET",
                    response_format="csv",
                    output_file_name="extract.csv",
                    enabled=True,
                    source_name="batch-extract",
                )
            )
            service = ConfiguredIngestionDefinitionService(
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
            )

            result = service.process_ingestion_definition("batch_extract_pull")

            self.assertEqual(1, result.discovered_files)
            self.assertEqual(0, result.processed_files)
            self.assertEqual(1, result.rejected_files)

            runs = metadata_repository.list_runs()
            self.assertEqual(1, len(runs))
            self.assertEqual(IngestionRunStatus.REJECTED, runs[0].status)


if __name__ == "__main__":
    unittest.main()
