"""ContractPriceService — landing + canonical accessor for temporal pricing data."""

from __future__ import annotations

import json
from pathlib import Path

from packages.domains.finance.pipelines.contract_prices import (
    CanonicalContractPrice,
    load_canonical_contract_prices_bytes,
)
from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.pipelines.run_context import RunControlContext
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunRecord, RunMetadataStore

CONTRACT_PRICE_CONTRACT = DatasetContract(
    dataset_name="contract_prices",
    columns=(
        ColumnContract("contract_name", ColumnType.STRING),
        ColumnContract("provider", ColumnType.STRING),
        ColumnContract("contract_type", ColumnType.STRING),
        ColumnContract("price_component", ColumnType.STRING),
        ColumnContract("billing_cycle", ColumnType.STRING),
        ColumnContract("unit_price", ColumnType.DECIMAL),
        ColumnContract("currency", ColumnType.STRING),
        ColumnContract("quantity_unit", ColumnType.STRING, required=False),
        ColumnContract("valid_from", ColumnType.DATE),
        ColumnContract("valid_to", ColumnType.DATE, required=False),
    ),
    allow_extra_columns=False,
)


class ContractPriceService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        blob_store: BlobStore | None = None,
    ) -> None:
        self.landing_root = landing_root
        self.metadata_repository = metadata_repository
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.landing_service = LandingService(
            blob_store=self.blob_store,
            metadata_repository=self.metadata_repository,
        )

    def ingest_file(
        self,
        source_path: Path,
        source_name: str = "manual-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        return self.ingest_bytes(
            source_bytes=source_path.read_bytes(),
            file_name=source_path.name,
            source_name=source_name,
            run_context=run_context,
        )

    def ingest_bytes(
        self,
        *,
        source_bytes: bytes,
        file_name: str,
        source_name: str = "manual-upload",
        run_context: RunControlContext | None = None,
    ) -> IngestionRunRecord:
        landing_result = self.landing_service.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=CONTRACT_PRICE_CONTRACT,
            run_context=run_context,
        )
        return self.metadata_repository.get_run(landing_result.run_id)

    def get_run(self, run_id: str) -> IngestionRunRecord:
        return self.metadata_repository.get_run(run_id)

    def get_canonical_contract_prices(self, run_id: str) -> list[CanonicalContractPrice]:
        run = self.get_run(run_id)
        if not run.passed:
            return []

        source_locator = run.raw_path
        manifest = json.loads(self.blob_store.read_bytes(run.manifest_path).decode("utf-8"))
        canonical_path = manifest.get("canonical_path")
        if canonical_path:
            source_locator = canonical_path

        source_bytes = self.blob_store.read_bytes(source_locator)
        return load_canonical_contract_prices_bytes(source_bytes)
