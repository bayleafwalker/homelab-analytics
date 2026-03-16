from __future__ import annotations

from dataclasses import dataclass

from packages.shared.extensions import ExtensionRegistry
from packages.storage.control_plane import ConfigCatalogStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    IngestionDefinitionRecord,
    PublicationDefinitionRecord,
    SourceAssetRecord,
    SourceSystemRecord,
    TransformationPackageRecord,
    validate_publication_key,
)


@dataclass(frozen=True)
class ConfigPreflightIssue:
    code: str
    entity_type: str
    entity_id: str
    message: str


@dataclass(frozen=True)
class ConfigPreflightCounts:
    source_systems: int
    dataset_contracts: int
    column_mappings: int
    source_assets: int
    transformation_packages: int
    publication_definitions: int
    ingestion_definitions: int


@dataclass(frozen=True)
class ConfigPreflightScope:
    source_asset_id: str | None = None
    ingestion_definition_id: str | None = None


@dataclass(frozen=True)
class ConfigPreflightReport:
    passed: bool
    scope: ConfigPreflightScope
    checked: ConfigPreflightCounts
    issues: tuple[ConfigPreflightIssue, ...]


def run_config_preflight(
    config_repository: ConfigCatalogStore,
    *,
    extension_registry: ExtensionRegistry | None = None,
    source_asset_id: str | None = None,
    ingestion_definition_id: str | None = None,
) -> ConfigPreflightReport:
    if source_asset_id and ingestion_definition_id:
        raise ValueError(
            "verify-config accepts either --source-asset-id or --ingestion-definition-id, not both"
        )

    all_source_systems = {
        source_system.source_system_id: source_system
        for source_system in config_repository.list_source_systems()
    }
    all_dataset_contracts = {
        dataset_contract.dataset_contract_id: dataset_contract
        for dataset_contract in config_repository.list_dataset_contracts()
    }
    all_column_mappings = {
        column_mapping.column_mapping_id: column_mapping
        for column_mapping in config_repository.list_column_mappings()
    }
    all_source_assets = {
        source_asset.source_asset_id: source_asset
        for source_asset in config_repository.list_source_assets()
    }
    all_transformation_packages = {
        transformation_package.transformation_package_id: transformation_package
        for transformation_package in config_repository.list_transformation_packages()
    }
    all_publication_definitions = config_repository.list_publication_definitions()
    all_ingestion_definitions = config_repository.list_ingestion_definitions()

    scoped_source_asset_ids = _resolve_scoped_source_asset_ids(
        config_repository=config_repository,
        source_asset_id=source_asset_id,
        ingestion_definition_id=ingestion_definition_id,
        all_ingestion_definitions=all_ingestion_definitions,
    )
    scoped_source_assets = [
        all_source_assets[source_asset_key]
        for source_asset_key in scoped_source_asset_ids
        if source_asset_key in all_source_assets
    ]
    scoped_ingestion_definitions = _resolve_scoped_ingestion_definitions(
        ingestion_definition_id=ingestion_definition_id,
        source_asset_id=source_asset_id,
        all_ingestion_definitions=all_ingestion_definitions,
    )
    scoped_column_mappings = {
        source_asset.column_mapping_id: all_column_mappings[source_asset.column_mapping_id]
        for source_asset in scoped_source_assets
        if source_asset.column_mapping_id in all_column_mappings
    }
    scoped_dataset_contracts = {
        source_asset.dataset_contract_id: all_dataset_contracts[
            source_asset.dataset_contract_id
        ]
        for source_asset in scoped_source_assets
        if source_asset.dataset_contract_id in all_dataset_contracts
    }
    scoped_source_systems = {
        source_asset.source_system_id: all_source_systems[source_asset.source_system_id]
        for source_asset in scoped_source_assets
        if source_asset.source_system_id in all_source_systems
    }
    scoped_transformation_package_ids = {
        source_asset.transformation_package_id
        for source_asset in scoped_source_assets
        if source_asset.transformation_package_id is not None
    }
    if source_asset_id is None and ingestion_definition_id is None:
        scoped_column_mappings = all_column_mappings
        scoped_dataset_contracts = all_dataset_contracts
        scoped_source_systems = all_source_systems
        scoped_source_assets = list(all_source_assets.values())
        scoped_transformation_package_ids = set(all_transformation_packages)
        scoped_ingestion_definitions = all_ingestion_definitions

    scoped_transformation_packages = {
        transformation_package_id: all_transformation_packages[transformation_package_id]
        for transformation_package_id in scoped_transformation_package_ids
        if transformation_package_id in all_transformation_packages
    }
    scoped_publication_definitions = [
        publication_definition
        for publication_definition in all_publication_definitions
        if (
            source_asset_id is None
            and ingestion_definition_id is None
            or publication_definition.transformation_package_id
            in scoped_transformation_package_ids
        )
    ]

    issues: list[ConfigPreflightIssue] = []
    _check_column_mappings(
        issues=issues,
        column_mappings=scoped_column_mappings,
        dataset_contracts=all_dataset_contracts,
        source_systems=all_source_systems,
    )
    _check_source_assets(
        issues=issues,
        source_assets=scoped_source_assets,
        source_systems=all_source_systems,
        dataset_contracts=all_dataset_contracts,
        column_mappings=all_column_mappings,
        transformation_packages=all_transformation_packages,
    )
    _check_publication_definitions(
        issues=issues,
        publication_definitions=scoped_publication_definitions,
        transformation_packages=all_transformation_packages,
        extension_registry=extension_registry,
    )
    _check_ingestion_definitions(
        issues=issues,
        ingestion_definitions=scoped_ingestion_definitions,
        source_assets=all_source_assets,
        source_systems=all_source_systems,
    )

    return ConfigPreflightReport(
        passed=not issues,
        scope=ConfigPreflightScope(
            source_asset_id=source_asset_id,
            ingestion_definition_id=ingestion_definition_id,
        ),
        checked=ConfigPreflightCounts(
            source_systems=len(scoped_source_systems),
            dataset_contracts=len(scoped_dataset_contracts),
            column_mappings=len(scoped_column_mappings),
            source_assets=len(scoped_source_assets),
            transformation_packages=len(scoped_transformation_packages),
            publication_definitions=len(scoped_publication_definitions),
            ingestion_definitions=len(scoped_ingestion_definitions),
        ),
        issues=tuple(issues),
    )


def _resolve_scoped_source_asset_ids(
    *,
    config_repository: ConfigCatalogStore,
    source_asset_id: str | None,
    ingestion_definition_id: str | None,
    all_ingestion_definitions: list[IngestionDefinitionRecord],
) -> list[str]:
    if source_asset_id is not None:
        config_repository.get_source_asset(source_asset_id)
        return [source_asset_id]
    if ingestion_definition_id is not None:
        ingestion_definition = config_repository.get_ingestion_definition(
            ingestion_definition_id
        )
        return [ingestion_definition.source_asset_id]
    return sorted(
        {
            ingestion_definition.source_asset_id
            for ingestion_definition in all_ingestion_definitions
        }
        | {
            source_asset.source_asset_id
            for source_asset in config_repository.list_source_assets()
        }
    )


def _resolve_scoped_ingestion_definitions(
    *,
    ingestion_definition_id: str | None,
    source_asset_id: str | None,
    all_ingestion_definitions: list[IngestionDefinitionRecord],
) -> list[IngestionDefinitionRecord]:
    if ingestion_definition_id is not None:
        return [
            ingestion_definition
            for ingestion_definition in all_ingestion_definitions
            if ingestion_definition.ingestion_definition_id == ingestion_definition_id
        ]
    if source_asset_id is not None:
        return [
            ingestion_definition
            for ingestion_definition in all_ingestion_definitions
            if ingestion_definition.source_asset_id == source_asset_id
        ]
    return all_ingestion_definitions


def _check_column_mappings(
    *,
    issues: list[ConfigPreflightIssue],
    column_mappings: dict[str, ColumnMappingRecord],
    dataset_contracts: dict[str, DatasetContractConfigRecord],
    source_systems: dict[str, SourceSystemRecord],
) -> None:
    for column_mapping in column_mappings.values():
        dataset_contract = dataset_contracts.get(column_mapping.dataset_contract_id)
        if dataset_contract is None:
            issues.append(
                _issue(
                    code="missing_dataset_contract",
                    entity_type="column_mapping",
                    entity_id=column_mapping.column_mapping_id,
                    message=(
                        "Column mapping references an unknown dataset contract: "
                        f"{column_mapping.dataset_contract_id}"
                    ),
                )
            )
            continue
        if column_mapping.source_system_id not in source_systems:
            issues.append(
                _issue(
                    code="missing_source_system",
                    entity_type="column_mapping",
                    entity_id=column_mapping.column_mapping_id,
                    message=(
                        "Column mapping references an unknown source system: "
                        f"{column_mapping.source_system_id}"
                    ),
                )
            )
        _check_mapping_against_contract(
            issues=issues,
            column_mapping=column_mapping,
            dataset_contract=dataset_contract,
        )


def _check_mapping_against_contract(
    *,
    issues: list[ConfigPreflightIssue],
    column_mapping: ColumnMappingRecord,
    dataset_contract: DatasetContractConfigRecord,
) -> None:
    contract_columns = {column.name: column for column in dataset_contract.columns}
    mapped_targets = {rule.target_column for rule in column_mapping.rules}
    unknown_targets = sorted(mapped_targets - set(contract_columns))
    missing_required_targets = sorted(
        column_name
        for column_name, column in contract_columns.items()
        if column.required and column_name not in mapped_targets
    )

    for target_column in unknown_targets:
        issues.append(
            _issue(
                code="unknown_target_column",
                entity_type="column_mapping",
                entity_id=column_mapping.column_mapping_id,
                message=(
                    "Column mapping targets a column not present in the dataset contract: "
                    f"{target_column}"
                ),
            )
        )
    for target_column in missing_required_targets:
        issues.append(
            _issue(
                code="missing_required_mapping",
                entity_type="column_mapping",
                entity_id=column_mapping.column_mapping_id,
                message=(
                    "Column mapping does not cover a required dataset contract column: "
                    f"{target_column}"
                ),
            )
        )


def _check_source_assets(
    *,
    issues: list[ConfigPreflightIssue],
    source_assets: list[SourceAssetRecord],
    source_systems: dict[str, SourceSystemRecord],
    dataset_contracts: dict[str, DatasetContractConfigRecord],
    column_mappings: dict[str, ColumnMappingRecord],
    transformation_packages: dict[str, TransformationPackageRecord],
) -> None:
    for source_asset in source_assets:
        source_system = source_systems.get(source_asset.source_system_id)
        dataset_contract = dataset_contracts.get(source_asset.dataset_contract_id)
        column_mapping = column_mappings.get(source_asset.column_mapping_id)

        if source_system is None:
            issues.append(
                _issue(
                    code="missing_source_system",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset references an unknown source system: "
                        f"{source_asset.source_system_id}"
                    ),
                )
            )
        if dataset_contract is None:
            issues.append(
                _issue(
                    code="missing_dataset_contract",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset references an unknown dataset contract: "
                        f"{source_asset.dataset_contract_id}"
                    ),
                )
            )
        if column_mapping is None:
            issues.append(
                _issue(
                    code="missing_column_mapping",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset references an unknown column mapping: "
                        f"{source_asset.column_mapping_id}"
                    ),
                )
            )
        if (
            source_asset.transformation_package_id is not None
            and source_asset.transformation_package_id not in transformation_packages
        ):
            issues.append(
                _issue(
                    code="missing_transformation_package",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset references an unknown transformation package: "
                        f"{source_asset.transformation_package_id}"
                    ),
                )
            )
        if column_mapping is not None and column_mapping.source_system_id != source_asset.source_system_id:
            issues.append(
                _issue(
                    code="source_system_binding_mismatch",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset and column mapping bind different source systems: "
                        f"{source_asset.source_system_id} != {column_mapping.source_system_id}"
                    ),
                )
            )
        if (
            column_mapping is not None
            and column_mapping.dataset_contract_id != source_asset.dataset_contract_id
        ):
            issues.append(
                _issue(
                    code="dataset_contract_binding_mismatch",
                    entity_type="source_asset",
                    entity_id=source_asset.source_asset_id,
                    message=(
                        "Source asset and column mapping bind different dataset contracts: "
                        f"{source_asset.dataset_contract_id} != {column_mapping.dataset_contract_id}"
                    ),
                )
            )


def _check_publication_definitions(
    *,
    issues: list[ConfigPreflightIssue],
    publication_definitions: list[PublicationDefinitionRecord],
    transformation_packages: dict[str, TransformationPackageRecord],
    extension_registry: ExtensionRegistry | None,
) -> None:
    for publication_definition in publication_definitions:
        if (
            publication_definition.transformation_package_id
            not in transformation_packages
        ):
            issues.append(
                _issue(
                    code="missing_transformation_package",
                    entity_type="publication_definition",
                    entity_id=publication_definition.publication_definition_id,
                    message=(
                        "Publication definition references an unknown transformation package: "
                        f"{publication_definition.transformation_package_id}"
                    ),
                )
            )
        try:
            validate_publication_key(
                publication_definition.publication_key,
                extension_registry=extension_registry,
            )
        except ValueError as exc:
            issues.append(
                _issue(
                    code="unknown_publication_key",
                    entity_type="publication_definition",
                    entity_id=publication_definition.publication_definition_id,
                    message=str(exc),
                )
            )


def _check_ingestion_definitions(
    *,
    issues: list[ConfigPreflightIssue],
    ingestion_definitions: list[IngestionDefinitionRecord],
    source_assets: dict[str, SourceAssetRecord],
    source_systems: dict[str, SourceSystemRecord],
) -> None:
    for ingestion_definition in ingestion_definitions:
        source_asset = source_assets.get(ingestion_definition.source_asset_id)
        if source_asset is None:
            issues.append(
                _issue(
                    code="missing_source_asset",
                    entity_type="ingestion_definition",
                    entity_id=ingestion_definition.ingestion_definition_id,
                    message=(
                        "Ingestion definition references an unknown source asset: "
                        f"{ingestion_definition.source_asset_id}"
                    ),
                )
            )
            continue

        source_system = source_systems.get(source_asset.source_system_id)
        if (
            source_system is not None
            and ingestion_definition.transport != source_system.transport
        ):
            issues.append(
                _issue(
                    code="transport_mismatch",
                    entity_type="ingestion_definition",
                    entity_id=ingestion_definition.ingestion_definition_id,
                    message=(
                        "Ingestion definition transport does not match its source system: "
                        f"{ingestion_definition.transport} != {source_system.transport}"
                    ),
                )
            )

        if (
            ingestion_definition.transport == "filesystem"
            and not ingestion_definition.source_path
        ):
            issues.append(
                _issue(
                    code="missing_source_path",
                    entity_type="ingestion_definition",
                    entity_id=ingestion_definition.ingestion_definition_id,
                    message="Filesystem ingestion definition requires source_path.",
                )
            )
        if ingestion_definition.transport == "http":
            if not ingestion_definition.request_url:
                issues.append(
                    _issue(
                        code="missing_request_url",
                        entity_type="ingestion_definition",
                        entity_id=ingestion_definition.ingestion_definition_id,
                        message="HTTP ingestion definition requires request_url.",
                    )
                )
            if not ingestion_definition.request_method:
                issues.append(
                    _issue(
                        code="missing_request_method",
                        entity_type="ingestion_definition",
                        entity_id=ingestion_definition.ingestion_definition_id,
                        message="HTTP ingestion definition requires request_method.",
                    )
                )
            if not ingestion_definition.response_format:
                issues.append(
                    _issue(
                        code="missing_response_format",
                        entity_type="ingestion_definition",
                        entity_id=ingestion_definition.ingestion_definition_id,
                        message="HTTP ingestion definition requires response_format.",
                    )
                )
            if not ingestion_definition.output_file_name:
                issues.append(
                    _issue(
                        code="missing_output_file_name",
                        entity_type="ingestion_definition",
                        entity_id=ingestion_definition.ingestion_definition_id,
                        message="HTTP ingestion definition requires output_file_name.",
                    )
                )


def _issue(
    *,
    code: str,
    entity_type: str,
    entity_id: str,
    message: str,
) -> ConfigPreflightIssue:
    return ConfigPreflightIssue(
        code=code,
        entity_type=entity_type,
        entity_id=entity_id,
        message=message,
    )
