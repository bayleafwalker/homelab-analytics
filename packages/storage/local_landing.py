from __future__ import annotations

from pathlib import Path

from packages.pipelines.csv_validation import DatasetContract
from packages.storage.blob import FilesystemBlobStore
from packages.storage.landing_service import LandingRunResult, LandingService
from packages.storage.run_metadata import RunMetadataStore


def ingest_csv_file(
    source_path: Path,
    landing_root: Path,
    source_name: str,
    contract: DatasetContract,
    metadata_repository: RunMetadataStore | None = None,
) -> LandingRunResult:
    landing_service = LandingService(
        blob_store=FilesystemBlobStore(landing_root),
        metadata_repository=metadata_repository,
    )
    return landing_service.ingest_csv_file(
        source_path=source_path,
        source_name=source_name,
        contract=contract,
    )
