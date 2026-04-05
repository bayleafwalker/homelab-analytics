import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.csv_validation import ColumnType
from packages.shared.function_registry import FunctionRegistry, RegisteredFunction
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    SourceSystemCreate,
)
from packages.storage.run_metadata import IngestionRunStatus, RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ConfiguredCsvIngestionServiceTests(unittest.TestCase):
    def test_config_only_csv_source_can_be_landed_without_new_python_code(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            metadata_repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
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
            service = ConfiguredCsvIngestionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
            )

            run = service.ingest_file(
                source_path=FIXTURES / "configured_account_transactions_source.csv",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                column_mapping_id="bank_partner_export_v1",
                source_name="manual-upload",
            )
            landed_content = Path(run.raw_path).read_text()

            self.assertEqual(IngestionRunStatus.LANDED, run.status)
            self.assertEqual("household_account_transactions", run.dataset_name)
            self.assertEqual(
                (
                    "booked_at",
                    "account_id",
                    "counterparty_name",
                    "amount",
                    "currency",
                    "description",
                ),
                run.header,
            )
            self.assertEqual(
                (
                    FIXTURES / "configured_account_transactions_source.csv"
                ).read_text(),
                landed_content,
            )
            manifest = json.loads(Path(run.manifest_path).read_text())
            self.assertIn("canonical_path", manifest)
            self.assertIsNotNone(manifest["canonical_path"])
            self.assertTrue(Path(manifest["canonical_path"]).is_file())
            self.assertEqual(
                {
                    "source_system_id": "bank_partner_export",
                    "dataset_contract_id": "household_account_transactions_v1",
                    "column_mapping_id": "bank_partner_export_v1",
                },
                manifest["context"],
            )

    def test_column_mapping_functions_transform_mapped_values(self) -> None:
        with TemporaryDirectory() as temp_dir:
            config_repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            metadata_repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
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
                        ColumnMappingRule(
                            "counterparty_name",
                            source_column="payee",
                            function_key="normalize_counterparty",
                        ),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                    ),
                )
            )
            function_registry = FunctionRegistry()
            function_registry.register(
                RegisteredFunction(
                    function_key="normalize_counterparty",
                    kind="column_mapping_value",
                    description="Normalize mapped counterparty names.",
                    module="tests.test_configured_csv_ingestion",
                    source="test",
                    handler=lambda *, value, **_: value.upper(),
                )
            )
            service = ConfiguredCsvIngestionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
                function_registry=function_registry,
            )
            source_path = Path(temp_dir) / "source.csv"
            source_path.write_text(
                "\n".join(
                    [
                        "booking_date,account_number,payee,amount_eur",
                        "2026-01-01,ACC-001,coffee shop,12.50",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            run = service.ingest_file(
                source_path=source_path,
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                column_mapping_id="bank_partner_export_v1",
            )
            manifest = json.loads(Path(run.manifest_path).read_text())
            canonical_text = Path(manifest["canonical_path"]).read_text(encoding="utf-8")

            self.assertIn("COFFEE SHOP", canonical_text)


if __name__ == "__main__":
    unittest.main()
