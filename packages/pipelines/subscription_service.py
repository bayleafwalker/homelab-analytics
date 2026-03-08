"""SubscriptionService — landing + canonical accessor for the subscription domain.

Mirrors ``AccountTransactionService``'s structure: validates against a
dataset contract, stores the raw bytes in the blob store, records run
metadata, and can load canonical rows for promotion.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.pipelines.subscriptions import (
    CanonicalSubscription,
    load_canonical_subscriptions_bytes,
)
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunRecord, RunMetadataStore


SUBSCRIPTION_CONTRACT = DatasetContract(
    dataset_name="subscriptions",
    columns=(
        ColumnContract("service_name", ColumnType.STRING),
        ColumnContract("provider", ColumnType.STRING),
        ColumnContract("billing_cycle", ColumnType.STRING),
        ColumnContract("amount", ColumnType.DECIMAL),
        ColumnContract("currency", ColumnType.STRING),
        ColumnContract("start_date", ColumnType.DATE),
        ColumnContract("end_date", ColumnType.DATE, required=False),
    ),
    allow_extra_columns=False,
)


class SubscriptionService:
    """Ingest subscription register CSVs and expose canonical rows for promotion."""

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
    ) -> IngestionRunRecord:
        return self.ingest_bytes(
            source_bytes=source_path.read_bytes(),
            file_name=source_path.name,
            source_name=source_name,
        )

    def ingest_bytes(
        self,
        *,
        source_bytes: bytes,
        file_name: str,
        source_name: str = "manual-upload",
    ) -> IngestionRunRecord:
        landing_result = self.landing_service.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=SUBSCRIPTION_CONTRACT,
        )
        return self.metadata_repository.get_run(landing_result.run_id)

    def get_run(self, run_id: str) -> IngestionRunRecord:
        return self.metadata_repository.get_run(run_id)

    def get_canonical_subscriptions(self, run_id: str) -> list[CanonicalSubscription]:
        run = self.get_run(run_id)
        if not run.passed:
            return []

        source_locator = run.raw_path
        manifest = json.loads(self.blob_store.read_bytes(run.manifest_path).decode("utf-8"))
        canonical_path = manifest.get("canonical_path")
        if canonical_path:
            source_locator = canonical_path

        source_bytes = self.blob_store.read_bytes(source_locator)
        return load_canonical_subscriptions_bytes(source_bytes)
