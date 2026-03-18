from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from packages.pipelines.csv_validation import ValidationIssue, validate_csv_text
from packages.pipelines.run_context import RunControlContext, merge_run_context
from packages.shared.function_registry import FunctionRegistry, validate_function_key
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.control_plane import ConfiguredCsvBindingStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    resolve_dataset_contract,
)
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunRecord, RunMetadataStore


@dataclass(frozen=True)
class ConfiguredCsvPreview:
    source_header: list[str]
    mapped_header: list[str]
    sample_row_count: int
    preview_rows: list[dict[str, str]]
    issues: list[ValidationIssue]


class ConfiguredCsvIngestionService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        config_repository: ConfiguredCsvBindingStore,
        blob_store: BlobStore | None = None,
        function_registry: FunctionRegistry | None = None,
    ) -> None:
        self.landing_root = landing_root
        self.metadata_repository = metadata_repository
        self.config_repository = config_repository
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.function_registry = function_registry or FunctionRegistry()
        self.landing_service = LandingService(
            blob_store=self.blob_store,
            metadata_repository=self.metadata_repository,
        )

    def ingest_file(
        self,
        source_path: Path,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
        source_asset_id: str | None = None,
        ingestion_definition_id: str | None = None,
        source_name: str = "configured-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        return self.ingest_bytes(
            source_bytes=source_path.read_bytes(),
            file_name=source_path.name,
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
            source_asset_id=source_asset_id,
            ingestion_definition_id=ingestion_definition_id,
            source_name=source_name,
            run_context=run_context,
        )

    def ingest_bytes(
        self,
        *,
        source_bytes: bytes,
        file_name: str,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
        source_asset_id: str | None = None,
        ingestion_definition_id: str | None = None,
        source_name: str = "configured-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        dataset_contract, column_mapping = self._resolve_mapping_config(
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
        )

        mapped_bytes = map_csv_columns(
            source_bytes=source_bytes,
            dataset_contract=dataset_contract,
            column_mapping=column_mapping,
            function_registry=self.function_registry,
        )
        landing_result = self.landing_service.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=resolve_dataset_contract(dataset_contract),
            validation_source_bytes=mapped_bytes,
            canonical_source_bytes=mapped_bytes,
            run_context=merge_run_context(
                run_context,
                source_asset_id=source_asset_id,
                source_system_id=source_system_id,
                dataset_contract_id=dataset_contract_id,
                column_mapping_id=column_mapping_id,
                ingestion_definition_id=ingestion_definition_id,
            ),
        )
        return self.metadata_repository.get_run(landing_result.run_id)

    def _resolve_mapping_config(
        self,
        *,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
    ) -> tuple[DatasetContractConfigRecord, ColumnMappingRecord]:
        source_system = self.config_repository.get_source_system(source_system_id)
        if not source_system.enabled:
            raise ValueError(f"Source system is disabled: {source_system_id}")
        dataset_contract = self.config_repository.get_dataset_contract(dataset_contract_id)
        if dataset_contract.archived:
            raise ValueError(f"Dataset contract is archived: {dataset_contract_id}")
        column_mapping = self.config_repository.get_column_mapping(column_mapping_id)
        if column_mapping.archived:
            raise ValueError(f"Column mapping is archived: {column_mapping_id}")

        if column_mapping.source_system_id != source_system_id:
            raise ValueError(
                "Column mapping source system does not match the requested source system."
            )
        if column_mapping.dataset_contract_id != dataset_contract_id:
            raise ValueError(
                "Column mapping dataset contract does not match the requested dataset contract."
            )
        return dataset_contract, column_mapping

    def preview_mapping(
        self,
        *,
        source_bytes: bytes,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
        preview_limit: int = 5,
    ) -> ConfiguredCsvPreview:
        dataset_contract, column_mapping = self._resolve_mapping_config(
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
        )
        return preview_mapped_csv(
            source_bytes=source_bytes,
            dataset_contract=dataset_contract,
            column_mapping=column_mapping,
            preview_limit=preview_limit,
            function_registry=self.function_registry,
        )


def map_csv_columns(
    *,
    source_bytes: bytes,
    dataset_contract: DatasetContractConfigRecord,
    column_mapping: ColumnMappingRecord,
    function_registry: FunctionRegistry | None = None,
) -> bytes:
    resolved_function_registry = function_registry or FunctionRegistry()
    rules_by_target = {rule.target_column: rule for rule in column_mapping.rules}
    target_columns = [column.name for column in dataset_contract.columns]
    unknown_targets = set(rules_by_target) - set(target_columns)
    if unknown_targets:
        raise ValueError(
            f"Column mapping references unknown target columns: {sorted(unknown_targets)}"
        )

    input_buffer = StringIO(source_bytes.decode("utf-8"))
    reader = csv.DictReader(input_buffer)
    output_buffer = StringIO()
    writer = csv.DictWriter(
        output_buffer,
        fieldnames=target_columns,
        lineterminator="\n",
    )
    writer.writeheader()

    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        normalized_row = {
            key: (value or "").strip()
            for key, value in row.items()
        }

        mapped_row = {}
        for target_column in target_columns:
            rule = rules_by_target.get(target_column)
            value = ""
            if rule is not None:
                if rule.source_column is not None:
                    value = normalized_row.get(rule.source_column, "")
                if not value and rule.default_value is not None:
                    value = rule.default_value
                if rule.function_key is not None:
                    validate_function_key(
                        rule.function_key,
                        function_registry=resolved_function_registry,
                        kind="column_mapping_value",
                    )
                    transformed_value = resolved_function_registry.execute(
                        rule.function_key,
                        value=value,
                        row=normalized_row,
                        target_column=target_column,
                        source_column=rule.source_column,
                        default_value=rule.default_value,
                    )
                    value = "" if transformed_value is None else str(transformed_value)
            mapped_row[target_column] = value
        writer.writerow(mapped_row)

    return output_buffer.getvalue().encode("utf-8")


def preview_mapped_csv(
    *,
    source_bytes: bytes,
    dataset_contract: DatasetContractConfigRecord,
    column_mapping: ColumnMappingRecord,
    preview_limit: int = 5,
    function_registry: FunctionRegistry | None = None,
) -> ConfiguredCsvPreview:
    source_text = source_bytes.decode("utf-8")
    mapped_bytes = map_csv_columns(
        source_bytes=source_bytes,
        dataset_contract=dataset_contract,
        column_mapping=column_mapping,
        function_registry=function_registry,
    )
    validation = validate_csv_text(
        mapped_bytes.decode("utf-8"),
        resolve_dataset_contract(dataset_contract),
    )
    preview_rows = []
    for index, row in enumerate(csv.DictReader(StringIO(mapped_bytes.decode("utf-8")))):
        if index >= max(preview_limit, 0):
            break
        preview_rows.append({key: (value or "") for key, value in row.items()})
    source_header = next(csv.reader(StringIO(source_text)), [])
    return ConfiguredCsvPreview(
        source_header=[column.strip() for column in source_header],
        mapped_header=validation.header,
        sample_row_count=validation.row_count,
        preview_rows=preview_rows,
        issues=validation.issues,
    )
