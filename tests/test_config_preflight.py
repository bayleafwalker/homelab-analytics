from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.config_preflight import run_config_preflight
from packages.pipelines.csv_validation import ColumnType
from packages.pipelines.promotion_registry import get_default_promotion_handler_registry
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionConfigRepository,
    IngestionDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)


class ConfigPreflightTests(unittest.TestCase):
    def test_preflight_passes_for_valid_scoped_source_asset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
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
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
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
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("currency", default_value="EUR"),
                    ),
                )
            )
            repository.create_source_asset(
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
            repository.create_ingestion_definition(
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

            report = run_config_preflight(
                repository,
                source_asset_id="bank_partner_transactions",
            )

            self.assertTrue(report.passed)
            self.assertEqual((), report.issues)
            self.assertEqual("bank_partner_transactions", report.scope.source_asset_id)
            self.assertEqual(1, report.checked.source_assets)
            self.assertEqual(1, report.checked.ingestion_definitions)

    def test_preflight_reports_mapping_contract_mismatches(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
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
                        DatasetColumnConfig("amount", ColumnType.DECIMAL),
                        DatasetColumnConfig("currency", ColumnType.STRING),
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
                        ColumnMappingRule("counterparty_name", source_column="payee"),
                        ColumnMappingRule("amount", source_column="amount_eur"),
                        ColumnMappingRule("not_in_contract", default_value="bad"),
                    ),
                )
            )
            repository.create_source_asset(
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

            report = run_config_preflight(repository)

            self.assertFalse(report.passed)
            self.assertIn(
                "missing_required_mapping",
                {issue.code for issue in report.issues},
            )
            self.assertIn(
                "unknown_target_column",
                {issue.code for issue in report.issues},
            )

    def test_preflight_reports_invalid_persisted_publication_keys(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            with repository._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO publication_definitions (
                        publication_definition_id,
                        transformation_package_id,
                        publication_key,
                        name,
                        description,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "pub_invalid_projection",
                        "builtin_account_transactions",
                        "mart_unknown_projection",
                        "Invalid projection",
                        None,
                        "2026-03-10T00:00:00+00:00",
                    ),
                )
                connection.commit()

            report = run_config_preflight(repository)

            self.assertFalse(report.passed)
            self.assertEqual(
                ["unknown_publication_key"],
                [issue.code for issue in report.issues],
            )

    def test_preflight_reports_unsupported_persisted_publication_mappings(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = IngestionConfigRepository(Path(temp_dir) / "config.db")
            with repository._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO publication_definitions (
                        publication_definition_id,
                        transformation_package_id,
                        publication_key,
                        name,
                        description,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "pub_invalid_builtin_mapping",
                        "builtin_account_transactions",
                        "mart_contract_price_current",
                        "Invalid built-in mapping",
                        None,
                        "2026-03-10T00:00:00+00:00",
                    ),
                )
                connection.commit()

            report = run_config_preflight(
                repository,
                promotion_handler_registry=get_default_promotion_handler_registry(),
            )

            self.assertFalse(report.passed)
            self.assertEqual(
                ["unsupported_publication_key"],
                [issue.code for issue in report.issues],
            )

    def test_preflight_reports_invalid_http_ingestion_definition_fields(self) -> None:
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
                        DatasetColumnConfig("measured_at", ColumnType.DATETIME),
                        DatasetColumnConfig("meter_id", ColumnType.STRING),
                        DatasetColumnConfig("kilowatt_hours", ColumnType.DECIMAL),
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
                        ColumnMappingRule("measured_at", source_column="measured_at"),
                        ColumnMappingRule("meter_id", source_column="meter_id"),
                        ColumnMappingRule(
                            "kilowatt_hours",
                            source_column="kilowatt_hours",
                        ),
                    ),
                )
            )
            repository.create_source_asset(
                SourceAssetCreate(
                    source_asset_id="utility_api_asset",
                    source_system_id="utility_api",
                    dataset_contract_id="utility_usage_v1",
                    column_mapping_id="utility_api_v1",
                    name="Utility API Asset",
                    asset_type="dataset",
                    transformation_package_id="builtin_utility_usage",
                )
            )
            repository.create_ingestion_definition(
                IngestionDefinitionCreate(
                    ingestion_definition_id="utility_api_pull",
                    source_asset_id="utility_api_asset",
                    transport="http",
                    schedule_mode="direct-api",
                    source_path="",
                    enabled=True,
                    source_name="scheduled-api-pull",
                )
            )

            report = run_config_preflight(
                repository,
                ingestion_definition_id="utility_api_pull",
            )

            self.assertFalse(report.passed)
            self.assertEqual(
                {
                    "missing_request_url",
                    "missing_request_method",
                    "missing_response_format",
                    "missing_output_file_name",
                },
                {issue.code for issue in report.issues},
            )


if __name__ == "__main__":
    unittest.main()
