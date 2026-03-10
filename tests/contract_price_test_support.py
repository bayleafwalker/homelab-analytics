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

CONTRACT_PRICE_SOURCE_SYSTEM_ID = "contract_price_portal"
CONTRACT_PRICE_CONTRACT_ID = "contract_prices_v1"
CONTRACT_PRICE_MAPPING_ID = "contract_prices_portal_v1"
CONTRACT_PRICE_ASSET_ID = "contract_price_asset"
CONTRACT_PRICE_DEFINITION_ID = "contract_price_watch_folder"


def create_contract_price_configuration(
    config_repository: IngestionConfigRepository,
    *,
    include_ingestion_definitions: bool = False,
    inbox: Path | None = None,
    processed: Path | None = None,
    failed: Path | None = None,
) -> None:
    config_repository.create_source_system(
        SourceSystemCreate(
            source_system_id=CONTRACT_PRICE_SOURCE_SYSTEM_ID,
            name="Contract Price Export",
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="manual",
        )
    )
    config_repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id=CONTRACT_PRICE_CONTRACT_ID,
            dataset_name="contract_prices",
            version=1,
            allow_extra_columns=False,
            columns=(
                DatasetColumnConfig("contract_name", ColumnType.STRING),
                DatasetColumnConfig("provider", ColumnType.STRING),
                DatasetColumnConfig("contract_type", ColumnType.STRING),
                DatasetColumnConfig("price_component", ColumnType.STRING),
                DatasetColumnConfig("billing_cycle", ColumnType.STRING),
                DatasetColumnConfig("unit_price", ColumnType.DECIMAL),
                DatasetColumnConfig("currency", ColumnType.STRING),
                DatasetColumnConfig("quantity_unit", ColumnType.STRING, required=False),
                DatasetColumnConfig("valid_from", ColumnType.DATE),
                DatasetColumnConfig("valid_to", ColumnType.DATE, required=False),
            ),
        )
    )
    config_repository.create_column_mapping(
        ColumnMappingCreate(
            column_mapping_id=CONTRACT_PRICE_MAPPING_ID,
            source_system_id=CONTRACT_PRICE_SOURCE_SYSTEM_ID,
            dataset_contract_id=CONTRACT_PRICE_CONTRACT_ID,
            version=1,
            rules=(
                ColumnMappingRule("contract_name", source_column="contract_name"),
                ColumnMappingRule("provider", source_column="provider"),
                ColumnMappingRule("contract_type", source_column="contract_type"),
                ColumnMappingRule("price_component", source_column="price_component"),
                ColumnMappingRule("billing_cycle", source_column="billing_cycle"),
                ColumnMappingRule("unit_price", source_column="unit_price"),
                ColumnMappingRule("currency", source_column="currency"),
                ColumnMappingRule("quantity_unit", source_column="quantity_unit"),
                ColumnMappingRule("valid_from", source_column="valid_from"),
                ColumnMappingRule("valid_to", source_column="valid_to"),
            ),
        )
    )
    config_repository.create_source_asset(
        SourceAssetCreate(
            source_asset_id=CONTRACT_PRICE_ASSET_ID,
            source_system_id=CONTRACT_PRICE_SOURCE_SYSTEM_ID,
            dataset_contract_id=CONTRACT_PRICE_CONTRACT_ID,
            column_mapping_id=CONTRACT_PRICE_MAPPING_ID,
            name="Contract Price Export",
            asset_type="dataset",
            transformation_package_id="builtin_contract_prices",
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
            ingestion_definition_id=CONTRACT_PRICE_DEFINITION_ID,
            source_asset_id=CONTRACT_PRICE_ASSET_ID,
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
