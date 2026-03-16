from __future__ import annotations

from packages.pipelines.csv_validation import ColumnType
from packages.storage.control_plane import ConfigCatalogStore
from packages.storage.ingestion_config import (
    ColumnMappingCreate,
    ColumnMappingRule,
    DatasetColumnConfig,
    DatasetContractConfigCreate,
    IngestionDefinitionCreate,
    SourceAssetCreate,
    SourceSystemCreate,
)

LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID = (
    "legacy_account_transaction_watch_source"
)
LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID = (
    "legacy_account_transaction_watch_contract_v1"
)
LEGACY_ACCOUNT_TRANSACTION_WATCH_COLUMN_MAPPING_ID = (
    "legacy_account_transaction_watch_mapping_v1"
)
LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_ASSET_ID = (
    "legacy_account_transaction_watch_asset"
)
LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID = (
    "legacy_account_transaction_watch_folder"
)


def ensure_account_transaction_watch_definition(
    config_repository: ConfigCatalogStore,
    *,
    source_path: str,
    processed_path: str,
    failed_path: str,
    poll_interval_seconds: int,
    source_name: str = "folder-watch",
) -> str:
    _ensure_source_system(config_repository)
    _ensure_dataset_contract(config_repository)
    _ensure_column_mapping(config_repository)
    _ensure_source_asset(config_repository)
    _ensure_ingestion_definition(
        config_repository,
        source_path=source_path,
        processed_path=processed_path,
        failed_path=failed_path,
        poll_interval_seconds=poll_interval_seconds,
        source_name=source_name,
    )
    return LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID


def _ensure_source_system(config_repository: ConfigCatalogStore) -> None:
    try:
        existing = config_repository.get_source_system(
            LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID
        )
    except KeyError:
        config_repository.create_source_system(
            SourceSystemCreate(
                source_system_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID,
                name="Legacy account transaction watch folder",
                source_type="file-drop",
                transport="filesystem",
                schedule_mode="watch-folder",
                description=(
                    "Bootstrap compatibility binding for account transaction inbox commands."
                ),
                enabled=True,
            )
        )
        return

    config_repository.update_source_system(
        SourceSystemCreate(
            source_system_id=existing.source_system_id,
            name=existing.name,
            source_type="file-drop",
            transport="filesystem",
            schedule_mode="watch-folder",
            description=existing.description,
            enabled=True,
            created_at=existing.created_at,
        )
    )


def _ensure_dataset_contract(config_repository: ConfigCatalogStore) -> None:
    try:
        config_repository.get_dataset_contract(
            LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID
        )
    except KeyError:
        config_repository.create_dataset_contract(
            DatasetContractConfigCreate(
                dataset_contract_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID,
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


def _ensure_column_mapping(config_repository: ConfigCatalogStore) -> None:
    try:
        config_repository.get_column_mapping(
            LEGACY_ACCOUNT_TRANSACTION_WATCH_COLUMN_MAPPING_ID
        )
    except KeyError:
        config_repository.create_column_mapping(
            ColumnMappingCreate(
                column_mapping_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_COLUMN_MAPPING_ID,
                source_system_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID,
                dataset_contract_id=(
                    LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID
                ),
                version=1,
                rules=(
                    ColumnMappingRule("booked_at", source_column="booked_at"),
                    ColumnMappingRule("account_id", source_column="account_id"),
                    ColumnMappingRule(
                        "counterparty_name",
                        source_column="counterparty_name",
                    ),
                    ColumnMappingRule("amount", source_column="amount"),
                    ColumnMappingRule("currency", source_column="currency"),
                    ColumnMappingRule("description", source_column="description"),
                ),
            )
        )


def _ensure_source_asset(config_repository: ConfigCatalogStore) -> None:
    try:
        existing = config_repository.get_source_asset(
            LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_ASSET_ID
        )
    except KeyError:
        config_repository.create_source_asset(
            SourceAssetCreate(
                source_asset_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_ASSET_ID,
                source_system_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID,
                dataset_contract_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID,
                column_mapping_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_COLUMN_MAPPING_ID,
                transformation_package_id="builtin_account_transactions",
                name="Legacy account transaction watch asset",
                asset_type="dataset",
                description=(
                    "Bootstrap compatibility asset for account transaction inbox commands."
                ),
                enabled=True,
                archived=False,
            )
        )
        return

    config_repository.update_source_asset(
        SourceAssetCreate(
            source_asset_id=existing.source_asset_id,
            source_system_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_SYSTEM_ID,
            dataset_contract_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_DATASET_CONTRACT_ID,
            column_mapping_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_COLUMN_MAPPING_ID,
            transformation_package_id="builtin_account_transactions",
            name=existing.name,
            asset_type=existing.asset_type,
            description=existing.description,
            enabled=True,
            archived=False,
            created_at=existing.created_at,
        )
    )


def _ensure_ingestion_definition(
    config_repository: ConfigCatalogStore,
    *,
    source_path: str,
    processed_path: str,
    failed_path: str,
    poll_interval_seconds: int,
    source_name: str,
) -> None:
    create = IngestionDefinitionCreate(
        ingestion_definition_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID,
        source_asset_id=LEGACY_ACCOUNT_TRANSACTION_WATCH_SOURCE_ASSET_ID,
        transport="filesystem",
        schedule_mode="watch-folder",
        source_path=source_path,
        file_pattern="*.csv",
        processed_path=processed_path,
        failed_path=failed_path,
        poll_interval_seconds=poll_interval_seconds,
        enabled=True,
        archived=False,
        source_name=source_name,
    )
    try:
        existing = config_repository.get_ingestion_definition(
            LEGACY_ACCOUNT_TRANSACTION_WATCH_INGESTION_DEFINITION_ID
        )
    except KeyError:
        config_repository.create_ingestion_definition(create)
        return

    config_repository.update_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=create.ingestion_definition_id,
            source_asset_id=create.source_asset_id,
            transport=create.transport,
            schedule_mode=create.schedule_mode,
            source_path=create.source_path,
            file_pattern=create.file_pattern,
            processed_path=create.processed_path,
            failed_path=create.failed_path,
            poll_interval_seconds=create.poll_interval_seconds,
            enabled=True,
            archived=False,
            source_name=create.source_name,
            created_at=existing.created_at,
        )
    )
