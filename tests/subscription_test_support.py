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

SUBSCRIPTION_SOURCE_SYSTEM_ID = "subscription_portal"
SUBSCRIPTION_CONTRACT_ID = "subscriptions_v1"
SUBSCRIPTION_MAPPING_ID = "subscriptions_portal_v1"
SUBSCRIPTION_ASSET_ID = "subscription_asset"
SUBSCRIPTION_DEFINITION_ID = "subscription_watch_folder"


def create_subscription_configuration(
    config_repository: IngestionConfigRepository,
    *,
    include_ingestion_definitions: bool = False,
    inbox: Path | None = None,
    processed: Path | None = None,
    failed: Path | None = None,
) -> None:
    config_repository.create_source_system(
        SourceSystemCreate(
            source_system_id=SUBSCRIPTION_SOURCE_SYSTEM_ID,
            name="Subscription Portal Export",
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="manual",
        )
    )
    config_repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id=SUBSCRIPTION_CONTRACT_ID,
            dataset_name="subscriptions",
            version=1,
            allow_extra_columns=False,
            columns=(
                DatasetColumnConfig("service_name", ColumnType.STRING),
                DatasetColumnConfig("provider", ColumnType.STRING),
                DatasetColumnConfig("billing_cycle", ColumnType.STRING),
                DatasetColumnConfig("amount", ColumnType.DECIMAL),
                DatasetColumnConfig("currency", ColumnType.STRING),
                DatasetColumnConfig("start_date", ColumnType.DATE),
                DatasetColumnConfig("end_date", ColumnType.DATE, required=False),
            ),
        )
    )
    config_repository.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id=SUBSCRIPTION_MAPPING_ID,
            source_system_id=SUBSCRIPTION_SOURCE_SYSTEM_ID,
            dataset_contract_id=SUBSCRIPTION_CONTRACT_ID,
            version=1,
            rules=(
                ColumnMappingRule("service_name", source_column="service_name"),
                ColumnMappingRule("provider", source_column="provider"),
                ColumnMappingRule("billing_cycle", source_column="billing_cycle"),
                ColumnMappingRule("amount", source_column="amount"),
                ColumnMappingRule("currency", source_column="currency"),
                ColumnMappingRule("start_date", source_column="start_date"),
                ColumnMappingRule("end_date", source_column="end_date"),
            ),
        )
    )
    config_repository.create_source_asset(
        SourceAssetCreate(
            source_asset_id=SUBSCRIPTION_ASSET_ID,
            source_system_id=SUBSCRIPTION_SOURCE_SYSTEM_ID,
            dataset_contract_id=SUBSCRIPTION_CONTRACT_ID,
            column_mapping_id=SUBSCRIPTION_MAPPING_ID,
            name="Subscription Export",
            asset_type="dataset",
            transformation_package_id="builtin_subscriptions",
        )
    )

    if not include_ingestion_definitions:
        return

    required_paths = (inbox, processed, failed)
    if any(path is None for path in required_paths):
        raise ValueError(
            "Filesystem ingestion definitions require inbox, processed, and failed paths."
        )

    config_repository.create_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=SUBSCRIPTION_DEFINITION_ID,
            source_asset_id=SUBSCRIPTION_ASSET_ID,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path=str(inbox),
            file_pattern="*.csv",
            processed_path=str(processed),
            failed_path=str(failed),
            poll_interval_seconds=30,
            enabled=True,
            source_name="folder-watch",
        )
    )
