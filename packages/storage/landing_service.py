from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from packages.pipelines.csv_validation import (
    DatasetContract,
    ValidationIssue,
    ValidationResult,
    validate_csv_text,
)
from packages.storage.blob import BlobStore
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataStore,
)


@dataclass(frozen=True)
class LandingRunResult:
    run_id: str
    raw_path: str
    manifest_path: str
    canonical_path: str | None
    sha256: str
    validation: ValidationResult


class LandingService:
    def __init__(
        self,
        blob_store: BlobStore,
        metadata_repository: RunMetadataStore | None = None,
    ) -> None:
        self.blob_store = blob_store
        self.metadata_repository = metadata_repository

    def ingest_csv_file(
        self,
        source_path: Path,
        source_name: str,
        contract: DatasetContract,
    ) -> LandingRunResult:
        source_bytes = source_path.read_bytes()
        return self.ingest_csv_bytes(
            source_bytes=source_bytes,
            file_name=source_path.name,
            source_name=source_name,
            contract=contract,
        )

    def ingest_csv_bytes(
        self,
        source_bytes: bytes,
        file_name: str,
        source_name: str,
        contract: DatasetContract,
        validation_source_bytes: bytes | None = None,
        canonical_source_bytes: bytes | None = None,
    ) -> LandingRunResult:
        validated_bytes = (
            source_bytes if validation_source_bytes is None else validation_source_bytes
        )
        source_text = validated_bytes.decode("utf-8")
        validation = validate_csv_text(source_text, contract)

        run_id = uuid4().hex
        landed_at = datetime.now(UTC)
        run_prefix = "/".join(
            [
                contract.dataset_name,
                landed_at.strftime("%Y"),
                landed_at.strftime("%m"),
                landed_at.strftime("%d"),
                run_id,
            ]
        )

        raw_path = self.blob_store.write_bytes(
            f"{run_prefix}/{file_name}",
            source_bytes,
        )
        canonical_path = None
        if canonical_source_bytes is not None:
            canonical_path = self.blob_store.write_bytes(
                f"{run_prefix}/canonical.csv",
                canonical_source_bytes,
            )

        sha256 = hashlib.sha256(source_bytes).hexdigest()

        if self.metadata_repository is not None:
            existing_run = self.metadata_repository.find_run_by_sha256(
                sha256,
                dataset_name=contract.dataset_name,
            )
            if existing_run is not None:
                validation = ValidationResult(
                    header=validation.header,
                    row_count=validation.row_count,
                    issues=[
                        *validation.issues,
                        ValidationIssue(
                            code="duplicate_file",
                            message=(
                                f"File content already landed in run"
                                f" {existing_run.run_id}."
                            ),
                        ),
                    ],
                )

        manifest = {
            "run_id": run_id,
            "source_name": source_name,
            "dataset_name": contract.dataset_name,
            "landed_at": landed_at.isoformat(),
            "raw_path": raw_path,
            "canonical_path": canonical_path,
            "file_name": file_name,
            "sha256": sha256,
            "row_count": validation.row_count,
            "header": validation.header,
            "passed": validation.passed,
            "issues": [asdict(issue) for issue in validation.issues],
        }
        manifest_path = self.blob_store.write_bytes(
            f"{run_prefix}/manifest.json",
            f"{json.dumps(manifest, indent=2)}\n".encode("utf-8"),
        )

        if self.metadata_repository is not None:
            self.metadata_repository.create_run(
                IngestionRunCreate(
                    run_id=run_id,
                    source_name=source_name,
                    dataset_name=contract.dataset_name,
                    file_name=file_name,
                    raw_path=raw_path,
                    manifest_path=manifest_path,
                    sha256=sha256,
                    row_count=validation.row_count,
                    header=tuple(validation.header),
                    status=(
                        IngestionRunStatus.LANDED
                        if validation.passed
                        else IngestionRunStatus.REJECTED
                    ),
                    passed=validation.passed,
                    issues=tuple(validation.issues),
                )
            )

        return LandingRunResult(
            run_id=run_id,
            raw_path=raw_path,
            manifest_path=manifest_path,
            canonical_path=canonical_path,
            sha256=sha256,
            validation=validation,
        )
