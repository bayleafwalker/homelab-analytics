from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.promotion import promote_run
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    SourceSystemCreate,
)
from packages.storage.run_metadata import RunMetadataRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class PromotionTests(unittest.TestCase):
    def test_promote_run_is_idempotent_for_same_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            account_service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            transformation_service = TransformationService(DuckDBStore.memory())

            run = account_service.ingest_file(FIXTURES / "account_transactions_valid.csv")

            first = promote_run(
                run.run_id,
                account_service=account_service,
                transformation_service=transformation_service,
            )
            second = promote_run(
                run.run_id,
                account_service=account_service,
                transformation_service=transformation_service,
            )

            self.assertFalse(first.skipped)
            self.assertEqual(2, first.facts_loaded)
            self.assertTrue(second.skipped)
            self.assertEqual("run already promoted", second.skip_reason)
            self.assertEqual(0, second.facts_loaded)
            self.assertEqual(2, transformation_service.count_transactions(run.run_id))

    def test_promote_run_uses_canonical_projection_for_configured_csv_runs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
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
            ingestion_service = ConfiguredCsvIngestionService(
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
            )
            account_service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
            )
            transformation_service = TransformationService(DuckDBStore.memory())

            run = ingestion_service.ingest_file(
                source_path=FIXTURES / "configured_account_transactions_source.csv",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                column_mapping_id="bank_partner_export_v1",
                source_name="manual-upload",
            )

            result = promote_run(
                run.run_id,
                account_service=account_service,
                transformation_service=transformation_service,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(2, result.facts_loaded)
            rows = transformation_service.get_monthly_cashflow()
            self.assertEqual(1, len(rows))
            self.assertEqual("2026-01", rows[0]["booking_month"])


if __name__ == "__main__":
    unittest.main()
