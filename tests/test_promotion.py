import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.builtin_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.promotion import (
    get_builtin_promotion_handler,
    promote_run,
    promote_source_asset_run,
)
from packages.pipelines.transformation_service import TransformationService
from packages.shared.extensions import ExtensionPublication, ExtensionRegistry, LayerExtension
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import (
    _BUILTIN_PUBLICATION_DEFINITIONS,
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    PublicationDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class PromotionTests(unittest.TestCase):
    def test_builtin_promotion_handlers_align_with_builtin_publication_definitions(
        self,
    ) -> None:
        builtins_by_package = {}
        for publication in _BUILTIN_PUBLICATION_DEFINITIONS:
            builtins_by_package.setdefault(
                publication.transformation_package_id,
                [],
            ).append(publication.publication_key)

        for spec in BUILTIN_TRANSFORMATION_PACKAGE_SPECS:
            handler = get_builtin_promotion_handler(spec.handler_key)
            self.assertEqual(
                tuple(builtins_by_package[spec.transformation_package_id]),
                handler.default_publications,
            )

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

    def test_promote_source_asset_run_allows_extension_publication_keys(self) -> None:
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
            source_asset = config_repository.create_source_asset(
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
            extension_registry = ExtensionRegistry()
            extension_registry.register(
                LayerExtension(
                    layer="reporting",
                    key="budget_projection_publication",
                    kind="mart",
                    description="Published budget projection relation.",
                    module="tests.budget_projection_publication",
                    source="tests",
                    data_access="published",
                    publication_relations=(
                        ExtensionPublication(
                            relation_name="mart_budget_projection",
                            columns=(
                                ("booking_month", "VARCHAR NOT NULL"),
                                ("net", "DECIMAL(18,4) NOT NULL"),
                            ),
                            source_query="SELECT booking_month, net FROM mart_monthly_cashflow",
                            order_by="booking_month",
                        ),
                    ),
                )
            )
            config_repository.create_publication_definition(
                PublicationDefinitionCreate(
                    publication_definition_id="pub_budget_projection",
                    transformation_package_id="builtin_account_transactions",
                    publication_key="mart_budget_projection",
                    name="Budget projection",
                ),
                extension_registry=extension_registry,
            )
            ingestion_service = ConfiguredCsvIngestionService(
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                config_repository=config_repository,
            )
            transformation_service = TransformationService(DuckDBStore.memory())

            run = ingestion_service.ingest_file(
                source_path=FIXTURES / "configured_account_transactions_source.csv",
                source_system_id="bank_partner_export",
                dataset_contract_id="household_account_transactions_v1",
                column_mapping_id="bank_partner_export_v1",
                source_name="manual-upload",
            )

            result = promote_source_asset_run(
                run.run_id,
                source_asset=source_asset,
                config_repository=config_repository,
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                transformation_service=transformation_service,
                extension_registry=extension_registry,
            )

            self.assertFalse(result.skipped)
            self.assertIn("mart_budget_projection", result.publication_keys)


if __name__ == "__main__":
    unittest.main()
