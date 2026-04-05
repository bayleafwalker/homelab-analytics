"""SQLite run-metadata coverage for local bootstrap smoke only."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.csv_validation import ValidationIssue
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataRepository,
)


def test_sqlite_run_metadata_smoke_persists_and_reads_run() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
        repository.create_run(
            IngestionRunCreate(
                run_id="run-001",
                source_name="manual-upload",
                dataset_name="account_transactions",
                file_name="transactions.csv",
                raw_path="/landing/run-001/transactions.csv",
                manifest_path="/landing/run-001/manifest.json",
                sha256="abc123",
                row_count=2,
                header=("booked_at", "amount"),
                status=IngestionRunStatus.LANDED,
                passed=True,
            )
        )

        fetched = repository.get_run("run-001")

    assert fetched.run_id == "run-001"
    assert fetched.status == IngestionRunStatus.LANDED
    assert fetched.header == ("booked_at", "amount")
    assert fetched.issues == []


def test_sqlite_run_metadata_smoke_supports_rejected_runs_and_status_filtering() -> None:
    with TemporaryDirectory() as temp_dir:
        repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
        repository.create_run(
            IngestionRunCreate(
                run_id="run-landed",
                source_name="manual-upload",
                dataset_name="account_transactions",
                file_name="transactions.csv",
                raw_path="/landing/run-landed/transactions.csv",
                manifest_path="/landing/run-landed/manifest.json",
                sha256="hash-landed",
                row_count=2,
                header=("booked_at", "amount"),
                status=IngestionRunStatus.LANDED,
                passed=True,
            )
        )
        repository.create_run(
            IngestionRunCreate(
                run_id="run-rejected",
                source_name="manual-upload",
                dataset_name="account_transactions",
                file_name="transactions-invalid.csv",
                raw_path="/landing/run-rejected/transactions-invalid.csv",
                manifest_path="/landing/run-rejected/manifest.json",
                sha256="hash-rejected",
                row_count=1,
                header=("booked_at", "amount"),
                status=IngestionRunStatus.REJECTED,
                passed=False,
                issues=(
                    ValidationIssue(
                        code="invalid_decimal",
                        message="Column 'amount' must contain a decimal value.",
                        column="amount",
                        row_number=2,
                    ),
                ),
            )
        )

        rejected_runs = repository.list_runs(status=IngestionRunStatus.REJECTED)
        landed_count = repository.count_runs(status=IngestionRunStatus.LANDED)
        rejected_count = repository.count_runs(status=IngestionRunStatus.REJECTED)

        assert [run.run_id for run in rejected_runs] == ["run-rejected"]
        assert len(rejected_runs[0].issues) == 1
        assert landed_count == 1
        assert rejected_count == 1
