import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.domains.finance.pipelines.account_transaction_service import AccountTransactionService
from packages.pipelines.configured_csv_ingestion import ConfiguredCsvIngestionService
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.household_packages import BUILTIN_TRANSFORMATION_PACKAGE_SPECS
from packages.pipelines.household_reporting import PUBLICATION_RELATIONS
from packages.pipelines.promotion import (
    get_builtin_promotion_handler,
    promote_run,
    promote_source_asset_run,
)
from packages.pipelines.promotion_registry import (
    PromotionHandler,
    PromotionHandlerRegistry,
    PromotionRuntime,
    register_domain_canonical_promotion_handler,
)
from packages.pipelines.promotion_types import PromotionResult
from packages.pipelines.transformation_domain_registry import TransformationDomainRegistry
from packages.pipelines.transformation_refresh_registry import PublicationRefreshRegistry
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
    TransformationPackageCreate,
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
            self.assertEqual(
                set(spec.refresh_publication_keys),
                set(spec.refresh_publication_keys) & set(PUBLICATION_RELATIONS),
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

    def test_promote_source_asset_run_uses_injected_promotion_handler_registry(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            config_repository = IngestionConfigRepository(temp_root / "config.db")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            config_repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="household_budget_feed",
                    name="Household Budget Feed",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                )
            )
            config_repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="household_budget_v1",
                    dataset_name="household_budget",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("period_start", ColumnType.DATE),
                        DatasetColumnConfig("category_id", ColumnType.STRING),
                        DatasetColumnConfig("planned_amount", ColumnType.DECIMAL),
                    ),
                )
            )
            config_repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="household_budget_feed_v1",
                    source_system_id="household_budget_feed",
                    dataset_contract_id="household_budget_v1",
                    version=1,
                    rules=(
                        ColumnMappingRule("period_start", source_column="period_start"),
                        ColumnMappingRule("category_id", source_column="category_id"),
                        ColumnMappingRule(
                            "planned_amount",
                            source_column="planned_amount",
                        ),
                    ),
                )
            )
            config_repository.create_transformation_package(
                TransformationPackageCreate(
                    transformation_package_id="custom_budget_v1",
                    name="Custom budget transform",
                    handler_key="custom_budget_transform",
                    version=1,
                )
            )
            source_asset = config_repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="household_budget_asset",
                    source_system_id="household_budget_feed",
                    dataset_contract_id="household_budget_v1",
                    column_mapping_id="household_budget_feed_v1",
                    name="Household Budget Asset",
                    asset_type="dataset",
                    transformation_package_id="custom_budget_v1",
                )
            )
            handler_registry = PromotionHandlerRegistry()
            handler_registry.register(
                PromotionHandler(
                    handler_key="custom_budget_transform",
                    default_publications=("mart_budget_projection",),
                    supported_publications=("mart_budget_projection",),
                    runner=lambda runtime: PromotionResult(
                        run_id=runtime.run_id,
                        facts_loaded=0,
                        marts_refreshed=["mart_budget_projection"],
                        publication_keys=["mart_budget_projection"],
                    ),
                )
            )

            result = promote_source_asset_run(
                "run-custom-budget-001",
                source_asset=source_asset,
                config_repository=config_repository,
                landing_root=temp_root / "landing",
                metadata_repository=metadata_repository,
                transformation_service=TransformationService(DuckDBStore.memory()),
                promotion_handler_registry=handler_registry,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(["mart_budget_projection"], result.marts_refreshed)
            self.assertEqual(["mart_budget_projection"], result.publication_keys)

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

    def test_register_domain_canonical_promotion_handler_registers_domain_and_handler(
        self,
    ) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )
            run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
            publication_refresh_registry = PublicationRefreshRegistry()
            publication_refresh_registry.register("mart_budget_projection", lambda service: 0)
            transformation_domain_registry = TransformationDomainRegistry()
            transformation_service = TransformationService(
                DuckDBStore.memory(),
                domain_registry=transformation_domain_registry,
                publication_refresh_registry=publication_refresh_registry,
            )
            promotion_handler_registry = PromotionHandlerRegistry()

            register_domain_canonical_promotion_handler(
                promotion_handler_registry=promotion_handler_registry,
                transformation_domain_registry=transformation_domain_registry,
                handler_key="custom_budget_transform",
                domain_key="custom_budget_domain",
                default_publications=("mart_budget_projection",),
                refresh_publication_keys=("mart_budget_projection",),
                build_runtime_service=lambda runtime: AccountTransactionService(
                    landing_root=runtime.landing_root,
                    metadata_repository=runtime.metadata_repository,
                    blob_store=runtime.blob_store,
                ),
                get_run=lambda runtime_service, run_id: runtime_service.get_run(run_id),
                get_canonical_rows=lambda runtime_service, run_id: (
                    runtime_service.get_canonical_transactions(run_id)
                ),
                serialize_row=lambda row: {
                    "booked_at": str(row.booked_at),
                    "account_id": row.account_id,
                    "counterparty_name": row.counterparty_name,
                    "amount": str(row.amount),
                    "currency": row.currency,
                    "description": row.description or "",
                },
                load_rows=lambda domain_service, rows, run_id, effective_date, source_system: (
                    domain_service.load_transactions(
                        rows,
                        run_id=run_id,
                        effective_date=effective_date,
                        source_system=source_system,
                    )
                ),
                count_rows=lambda domain_service, run_id: domain_service.count_transactions(
                    run_id=run_id
                ),
                required_header={
                    "booked_at",
                    "account_id",
                    "counterparty_name",
                    "amount",
                    "currency",
                },
                contract_mismatch_reason=(
                    "run does not match the account-transaction canonical contract"
                ),
            )

            result = promotion_handler_registry.get("custom_budget_transform").runner(
                PromotionRuntime(
                    run_id=run.run_id,
                    landing_root=temp_root / "landing",
                    metadata_repository=service.metadata_repository,
                    config_repository=object(),  # type: ignore[arg-type]
                    transformation_service=transformation_service,
                )
            )

            self.assertEqual(("custom_budget_domain",), transformation_domain_registry.domain_keys())
            self.assertEqual(2, transformation_service.count_transactions(run.run_id))
            self.assertEqual(2, result.facts_loaded)
            self.assertEqual(["mart_budget_projection"], result.marts_refreshed)
            self.assertEqual(["mart_budget_projection"], result.publication_keys)


if __name__ == "__main__":
    unittest.main()
