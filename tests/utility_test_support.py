from __future__ import annotations

from pathlib import Path

from packages.pipelines.csv_validation import ColumnType
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

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"

UTILITY_SOURCE_SYSTEM_ID = "utility_portal"
UTILITY_USAGE_CONTRACT_ID = "utility_usage_v1"
UTILITY_BILLS_CONTRACT_ID = "utility_bills_v1"
UTILITY_USAGE_MAPPING_ID = "utility_usage_portal_v1"
UTILITY_BILLS_MAPPING_ID = "utility_bills_portal_v1"
UTILITY_USAGE_ASSET_ID = "utility_usage_asset"
UTILITY_BILLS_ASSET_ID = "utility_bills_asset"
UTILITY_USAGE_DEFINITION_ID = "utility_usage_watch"
UTILITY_BILLS_DEFINITION_ID = "utility_bills_watch"


def create_utility_configuration(
    config_repository: IngestionConfigRepository,
    *,
    include_ingestion_definitions: bool = False,
    usage_inbox: Path | None = None,
    usage_processed: Path | None = None,
    usage_failed: Path | None = None,
    bills_inbox: Path | None = None,
    bills_processed: Path | None = None,
    bills_failed: Path | None = None,
) -> None:
    config_repository.create_source_system(
        SourceSystemCreate(
            source_system_id=UTILITY_SOURCE_SYSTEM_ID,
            name="Utility Portal Export",
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="manual",
        )
    )
    config_repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id=UTILITY_USAGE_CONTRACT_ID,
            dataset_name="utility_usage",
            version=1,
            allow_extra_columns=False,
            columns=(
                DatasetColumnConfig("meter_id", ColumnType.STRING),
                DatasetColumnConfig("meter_name", ColumnType.STRING),
                DatasetColumnConfig("utility_type", ColumnType.STRING),
                DatasetColumnConfig("location", ColumnType.STRING, required=False),
                DatasetColumnConfig("usage_start", ColumnType.DATE),
                DatasetColumnConfig("usage_end", ColumnType.DATE),
                DatasetColumnConfig("usage_quantity", ColumnType.DECIMAL),
                DatasetColumnConfig("usage_unit", ColumnType.STRING),
                DatasetColumnConfig("reading_source", ColumnType.STRING, required=False),
            ),
        )
    )
    config_repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id=UTILITY_BILLS_CONTRACT_ID,
            dataset_name="utility_bills",
            version=1,
            allow_extra_columns=False,
            columns=(
                DatasetColumnConfig("meter_id", ColumnType.STRING),
                DatasetColumnConfig("meter_name", ColumnType.STRING),
                DatasetColumnConfig("provider", ColumnType.STRING, required=False),
                DatasetColumnConfig("utility_type", ColumnType.STRING),
                DatasetColumnConfig("location", ColumnType.STRING, required=False),
                DatasetColumnConfig("billing_period_start", ColumnType.DATE),
                DatasetColumnConfig("billing_period_end", ColumnType.DATE),
                DatasetColumnConfig("billed_amount", ColumnType.DECIMAL),
                DatasetColumnConfig("currency", ColumnType.STRING),
                DatasetColumnConfig("billed_quantity", ColumnType.DECIMAL, required=False),
                DatasetColumnConfig("usage_unit", ColumnType.STRING, required=False),
                DatasetColumnConfig("invoice_date", ColumnType.DATE, required=False),
            ),
        )
    )
    config_repository.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id=UTILITY_USAGE_MAPPING_ID,
            source_system_id=UTILITY_SOURCE_SYSTEM_ID,
            dataset_contract_id=UTILITY_USAGE_CONTRACT_ID,
            version=1,
            rules=(
                ColumnMappingRule("meter_id", source_column="meter_ref"),
                ColumnMappingRule("meter_name", source_column="meter_label"),
                ColumnMappingRule("utility_type", source_column="utility_kind"),
                ColumnMappingRule("location", source_column="site_label"),
                ColumnMappingRule("usage_start", source_column="period_start"),
                ColumnMappingRule("usage_end", source_column="period_end"),
                ColumnMappingRule("usage_quantity", source_column="consumption"),
                ColumnMappingRule("usage_unit", source_column="unit_code"),
                ColumnMappingRule("reading_source", source_column="source_system"),
            ),
        )
    )
    config_repository.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id=UTILITY_BILLS_MAPPING_ID,
            source_system_id=UTILITY_SOURCE_SYSTEM_ID,
            dataset_contract_id=UTILITY_BILLS_CONTRACT_ID,
            version=1,
            rules=(
                ColumnMappingRule("meter_id", source_column="meter_ref"),
                ColumnMappingRule("meter_name", source_column="meter_label"),
                ColumnMappingRule("provider", source_column="provider_name"),
                ColumnMappingRule("utility_type", source_column="utility_kind"),
                ColumnMappingRule("location", source_column="site_label"),
                ColumnMappingRule("billing_period_start", source_column="bill_start"),
                ColumnMappingRule("billing_period_end", source_column="bill_end"),
                ColumnMappingRule("billed_amount", source_column="total_due"),
                ColumnMappingRule("currency", source_column="currency_code"),
                ColumnMappingRule("billed_quantity", source_column="quantity_billed"),
                ColumnMappingRule("usage_unit", source_column="unit_code"),
                ColumnMappingRule("invoice_date", source_column="invoiced_on"),
            ),
        )
    )
    config_repository.create_source_asset(
        SourceAssetCreate(
            source_asset_id=UTILITY_USAGE_ASSET_ID,
            source_system_id=UTILITY_SOURCE_SYSTEM_ID,
            dataset_contract_id=UTILITY_USAGE_CONTRACT_ID,
            column_mapping_id=UTILITY_USAGE_MAPPING_ID,
            name="Utility Usage Export",
            asset_type="dataset",
            transformation_package_id="builtin_utility_usage",
        )
    )
    config_repository.create_source_asset(
        SourceAssetCreate(
            source_asset_id=UTILITY_BILLS_ASSET_ID,
            source_system_id=UTILITY_SOURCE_SYSTEM_ID,
            dataset_contract_id=UTILITY_BILLS_CONTRACT_ID,
            column_mapping_id=UTILITY_BILLS_MAPPING_ID,
            name="Utility Billing Export",
            asset_type="dataset",
            transformation_package_id="builtin_utility_bills",
        )
    )

    if not include_ingestion_definitions:
        return

    required_paths = (
        usage_inbox,
        usage_processed,
        usage_failed,
        bills_inbox,
        bills_processed,
        bills_failed,
    )
    if any(path is None for path in required_paths):
        raise ValueError("Filesystem ingestion definitions require inbox/processed/failed paths.")

    config_repository.create_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=UTILITY_USAGE_DEFINITION_ID,
            source_asset_id=UTILITY_USAGE_ASSET_ID,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path=str(usage_inbox),
            processed_path=str(usage_processed),
            failed_path=str(usage_failed),
            poll_interval_seconds=30,
            enabled=True,
            source_name="folder-watch",
        )
    )
    config_repository.create_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=UTILITY_BILLS_DEFINITION_ID,
            source_asset_id=UTILITY_BILLS_ASSET_ID,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path=str(bills_inbox),
            processed_path=str(bills_processed),
            failed_path=str(bills_failed),
            poll_interval_seconds=30,
            enabled=True,
            source_name="folder-watch",
        )
    )
