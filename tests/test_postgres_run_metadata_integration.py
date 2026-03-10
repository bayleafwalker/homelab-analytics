import pytest

from packages.pipelines.csv_validation import ValidationIssue
from packages.storage.postgres_run_metadata import PostgresRunMetadataRepository
from packages.storage.run_metadata import IngestionRunCreate, IngestionRunStatus
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_postgres_repository_persists_and_queries_run_metadata() -> None:
    with running_postgres_container() as dsn:
        repository = PostgresRunMetadataRepository(dsn)
        repository.create_run(
            IngestionRunCreate(
                run_id="run-001",
                source_name="manual-upload",
                dataset_name="account_transactions",
                file_name="transactions.csv",
                raw_path="s3://landing/account_transactions/2026/03/09/run-001/transactions.csv",
                manifest_path="s3://landing/account_transactions/2026/03/09/run-001/manifest.json",
                sha256="shared-hash",
                row_count=2,
                header=("booked_at", "amount"),
                status=IngestionRunStatus.LANDED,
                passed=True,
            )
        )
        repository.create_run(
            IngestionRunCreate(
                run_id="run-002",
                source_name="manual-upload",
                dataset_name="account_transactions",
                file_name="transactions-invalid.csv",
                raw_path="s3://landing/account_transactions/2026/03/09/run-002/transactions-invalid.csv",
                manifest_path="s3://landing/account_transactions/2026/03/09/run-002/manifest.json",
                sha256="rejected-hash",
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

        fetched = repository.get_run("run-001")
        landed_runs = repository.list_runs(status=IngestionRunStatus.LANDED)
        rejected_runs = repository.list_runs(status=IngestionRunStatus.REJECTED)
        duplicate_lookup = repository.find_run_by_sha256(
            "shared-hash",
            dataset_name="account_transactions",
        )

        assert fetched.run_id == "run-001"
        assert fetched.header == ("booked_at", "amount")
        assert repository.count_runs() == 2
        assert repository.count_runs(status=IngestionRunStatus.REJECTED) == 1
        assert [run.run_id for run in landed_runs] == ["run-001"]
        assert [run.run_id for run in rejected_runs] == ["run-002"]
        assert duplicate_lookup is not None
        assert duplicate_lookup.run_id == "run-001"
        assert len(repository.get_run("run-002").issues) == 1
