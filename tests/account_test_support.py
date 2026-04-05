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

ACCOUNT_SOURCE_SYSTEM_ID = "bank_partner_export"
ACCOUNT_CONTRACT_ID = "household_account_transactions_v1"
ACCOUNT_MAPPING_ID = "bank_partner_export_v1"
ACCOUNT_ASSET_ID = "bank_partner_transactions"
ACCOUNT_DEFINITION_ID = "bank_partner_watch_folder"


def create_account_configuration(
    config_repository: IngestionConfigRepository,
    *,
    include_ingestion_definitions: bool = False,
    inbox: Path | None = None,
    processed: Path | None = None,
    failed: Path | None = None,
) -> None:
    config_repository.create_source_system(
        SourceSystemCreate(
            source_system_id=ACCOUNT_SOURCE_SYSTEM_ID,
            name="Bank Partner Export",
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="manual",
            description="Manual bank export",
        )
    )
    config_repository.create_dataset_contract(
        DatasetContractConfigCreate(
            dataset_contract_id=ACCOUNT_CONTRACT_ID,
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
            column_mapping_id=ACCOUNT_MAPPING_ID,
            source_system_id=ACCOUNT_SOURCE_SYSTEM_ID,
            dataset_contract_id=ACCOUNT_CONTRACT_ID,
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
            source_asset_id=ACCOUNT_ASSET_ID,
            source_system_id=ACCOUNT_SOURCE_SYSTEM_ID,
            dataset_contract_id=ACCOUNT_CONTRACT_ID,
            column_mapping_id=ACCOUNT_MAPPING_ID,
            name="Bank Partner Transactions",
            asset_type="dataset",
            transformation_package_id="builtin_account_transactions",
            description="Canonicalized household transaction export.",
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
            ingestion_definition_id=ACCOUNT_DEFINITION_ID,
            source_asset_id=ACCOUNT_ASSET_ID,
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
