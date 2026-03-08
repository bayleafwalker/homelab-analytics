from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.ingestion_config import (
    ColumnMappingRecord,
    DatasetContractConfigRecord,
    IngestionConfigRepository,
    resolve_dataset_contract,
)
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunRecord, RunMetadataStore


class ConfiguredCsvIngestionService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        config_repository: IngestionConfigRepository,
        blob_store: BlobStore | None = None,
    ) -> None:
        self.landing_root = landing_root
        self.metadata_repository = metadata_repository
        self.config_repository = config_repository
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
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
        source_name: str = "configured-upload",
    ) -> IngestionRunRecord:
        return self.ingest_bytes(
            source_bytes=source_path.read_bytes(),
            file_name=source_path.name,
            source_system_id=source_system_id,
            dataset_contract_id=dataset_contract_id,
            column_mapping_id=column_mapping_id,
            source_name=source_name,
        )

    def ingest_bytes(
        self,
        *,
        source_bytes: bytes,
        file_name: str,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
        source_name: str = "configured-upload",
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
        )
        landing_result = self.landing_service.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=resolve_dataset_contract(dataset_contract),
            validation_source_bytes=mapped_bytes,
            canonical_source_bytes=mapped_bytes,
        )
        return self.metadata_repository.get_run(landing_result.run_id)

    def _resolve_mapping_config(
        self,
        *,
        source_system_id: str,
        dataset_contract_id: str,
        column_mapping_id: str,
    ) -> tuple[DatasetContractConfigRecord, ColumnMappingRecord]:
        self.config_repository.get_source_system(source_system_id)
        dataset_contract = self.config_repository.get_dataset_contract(dataset_contract_id)
        column_mapping = self.config_repository.get_column_mapping(column_mapping_id)

        if column_mapping.source_system_id != source_system_id:
            raise ValueError(
                "Column mapping source system does not match the requested source system."
            )
        if column_mapping.dataset_contract_id != dataset_contract_id:
            raise ValueError(
                "Column mapping dataset contract does not match the requested dataset contract."
            )
        return dataset_contract, column_mapping


def map_csv_columns(
    *,
    source_bytes: bytes,
    dataset_contract: DatasetContractConfigRecord,
    column_mapping: ColumnMappingRecord,
) -> bytes:
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

        mapped_row = {}
        for target_column in target_columns:
            rule = rules_by_target.get(target_column)
            value = ""
            if rule is not None:
                if rule.source_column is not None:
                    value = (row.get(rule.source_column) or "").strip()
                if not value and rule.default_value is not None:
                    value = rule.default_value
            mapped_row[target_column] = value
        writer.writerow(mapped_row)

    return output_buffer.getvalue().encode("utf-8")
