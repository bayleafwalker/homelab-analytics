from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.pipelines.csv_validation import ColumnType
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    IngestionConfigRepository,
    RequestHeaderSecretRef,
    PublicationDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
    TransformationPackageCreate,
    resolve_dataset_contract,
)


class IngestionConfigRepositoryTests(unittest.TestCase):
    def test_repository_persists_source_contract_and_mapping_entities(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

            source_system = repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_csv_export",
                    name="Bank CSV Export",
                    source_type="file-drop",
                    transport="filesystem",
                    schedule_mode="manual",
                    description="Manual household bank CSV export.",
                )
            )
            dataset_contract = repository.create_dataset_contract(
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
            column_mapping = repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_csv_export_v1",
                    source_system_id=source_system.source_system_id,
                    dataset_contract_id=dataset_contract.dataset_contract_id,
                    version=1,
                    rules=(
                        ColumnMappingRule("booked_at", source_column="booking_date"),
                        ColumnMappingRule("account_id", source_column="account_number"),
                        ColumnMappingRule(
                            "counterparty_name",
                            source_column="payee",
                        ),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule(
                            "currency",
                            default_value="EUR",
                        ),
                        ColumnMappingRule(
                            "description",
                            source_column="memo",
                        ),
                    ),
                )
            )

            self.assertEqual(source_system, repository.get_source_system(source_system.source_system_id))
            self.assertEqual(
                dataset_contract,
                repository.get_dataset_contract(dataset_contract.dataset_contract_id),
            )
            self.assertEqual(
                column_mapping,
                repository.get_column_mapping(column_mapping.column_mapping_id),
            )
            self.assertEqual(1, len(repository.list_source_systems()))
            self.assertEqual(1, len(repository.list_dataset_contracts()))
            self.assertEqual(1, len(repository.list_column_mappings()))

    def test_dataset_contract_config_resolves_to_runtime_contract(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            dataset_contract = repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="utility_usage_v1",
                    dataset_name="utility_usage",
                    version=1,
                    allow_extra_columns=False,
                    columns=(
                        DatasetColumnConfig("measured_at", ColumnType.DATETIME),
                        DatasetColumnConfig("meter_id", ColumnType.STRING),
                        DatasetColumnConfig("kilowatt_hours", ColumnType.DECIMAL),
                    ),
                )
            )

            resolved = resolve_dataset_contract(dataset_contract)

            self.assertEqual("utility_usage", resolved.dataset_name)
            self.assertEqual(
                ["measured_at", "meter_id", "kilowatt_hours"],
                [column.name for column in resolved.columns],
            )
            self.assertEqual(
                [ColumnType.DATETIME, ColumnType.STRING, ColumnType.DECIMAL],
                [column.type for column in resolved.columns],
            )
            self.assertFalse(resolved.allow_extra_columns)

    def test_repository_persists_source_assets_and_ingestion_definitions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="bank_csv_export",
                    name="Bank CSV Export",
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
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
                    ),
                )
            )
            repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="bank_csv_export_v1",
                    source_system_id="bank_csv_export",
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

            source_asset = repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="bank_csv_household_transactions",
                    source_system_id="bank_csv_export",
                    dataset_contract_id="household_account_transactions_v1",
                    column_mapping_id="bank_csv_export_v1",
                    name="Household Transactions CSV",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                    description="Canonicalized household transaction export.",
                )
            )
            ingestion_definition = repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="bank_csv_watch_folder",
                    source_asset_id=source_asset.source_asset_id,
                    transport="filesystem",
                    schedule_mode="watch-folder",
                    source_path="/tmp/homelab/inbox",
                    file_pattern="*.csv",
                    processed_path="/tmp/homelab/processed",
                    failed_path="/tmp/homelab/failed",
                    poll_interval_seconds=30,
                    enabled=True,
                    source_name="folder-watch",
                )
            )

            self.assertEqual(
                source_asset,
                repository.get_source_asset(source_asset.source_asset_id),
            )
            self.assertEqual(
                ingestion_definition,
                repository.get_ingestion_definition(
                    ingestion_definition.ingestion_definition_id
                ),
            )
            self.assertEqual(1, len(repository.list_source_assets()))
            self.assertEqual(1, len(repository.list_ingestion_definitions()))
            self.assertEqual(
                "builtin_account_transactions",
                repository.get_source_asset(source_asset.source_asset_id).transformation_package_id,
            )

    def test_repository_persists_http_ingestion_definition_fields(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            repository.create_source_system(
                SourceSystemCreate(
                    source_system_id="utility_api",
                    name="Utility API",
                    source_type="api",
                    transport="http",
                    schedule_mode="scheduled",
                )
            )
            repository.create_dataset_contract(
                DatasetContractConfigCreate(
                    dataset_contract_id="utility_usage_v1",
                    dataset_name="utility_usage",
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
            repository.create_column_mapping(
                ColumnMappingCreate(
                    column_mapping_id="utility_api_v1",
                    source_system_id="utility_api",
                    dataset_contract_id="utility_usage_v1",
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
            repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="utility_api_asset",
                    source_system_id="utility_api",
                    dataset_contract_id="utility_usage_v1",
                    column_mapping_id="utility_api_v1",
                    name="Utility Usage API Asset",
                    asset_type="dataset",
                    transformation_package_id="builtin_account_transactions",
                )
            )

            ingestion_definition = repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="utility_api_pull",
                    source_asset_id="utility_api_asset",
                    transport="http",
                    schedule_mode="direct-api",
                    source_path="",
                    request_url="https://example.invalid/usage.csv",
                    request_method="GET",
                    request_headers=(
                        RequestHeaderSecretRef(
                            name="Authorization",
                            secret_name="utility-api",
                            secret_key="bearer-token",
                        ),
                    ),
                    response_format="csv",
                    output_file_name="usage.csv",
                    request_timeout_seconds=45,
                    enabled=True,
                    source_name="scheduled-api-pull",
                )
            )

            self.assertEqual(
                ingestion_definition,
                repository.get_ingestion_definition(
                    ingestion_definition.ingestion_definition_id
                ),
            )
            self.assertEqual(
                (
                    RequestHeaderSecretRef(
                        name="Authorization",
                        secret_name="utility-api",
                        secret_key="bearer-token",
                    ),
                ),
                ingestion_definition.request_headers,
            )
            self.assertEqual("csv", ingestion_definition.response_format)
            self.assertEqual("usage.csv", ingestion_definition.output_file_name)

    def test_repository_exposes_transformation_packages_and_publications(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")

            builtin_ids = {
                package.transformation_package_id
                for package in repository.list_transformation_packages()
            }
            self.assertIn("builtin_account_transactions", builtin_ids)
            self.assertIn("builtin_subscriptions", builtin_ids)
            self.assertIn("builtin_contract_prices", builtin_ids)

            custom_package = repository.create_transformation_package(
                TransformationPackageCreate(
                    transformation_package_id="custom_household_costs",
                    name="Custom household costs",
                    handler_key="custom.household_costs",
                    version=1,
                )
            )
            publication = repository.create_publication_definition(
                PublicationDefinitionCreate(
                    publication_definition_id="pub_household_costs_monthly",
                    transformation_package_id=custom_package.transformation_package_id,
                    publication_key="mart_household_costs_monthly",
                    name="Household costs monthly",
                )
            )

            self.assertEqual(
                custom_package,
                repository.get_transformation_package("custom_household_costs"),
            )
            self.assertEqual(
                publication,
                repository.get_publication_definition("pub_household_costs_monthly"),
            )
            self.assertEqual(
                ["pub_household_costs_monthly"],
                [
                    item.publication_definition_id
                    for item in repository.list_publication_definitions(
                        transformation_package_id="custom_household_costs"
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
