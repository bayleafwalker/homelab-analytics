"""Authoritative Postgres integration coverage for run-metadata semantics."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest

from packages.pipelines.csv_validation import ValidationIssue
from packages.storage.postgres_run_metadata import PostgresRunMetadataRepository
from packages.storage.run_metadata import IngestionRunCreate, IngestionRunStatus
from tests.postgres_test_support import running_postgres_container

pytestmark = [pytest.mark.integration, pytest.mark.slow]


@pytest.fixture(scope="module")
def postgres_dsn() -> Iterator[str]:
    with running_postgres_container() as dsn:
        yield dsn


@pytest.fixture
def repository(postgres_dsn: str) -> PostgresRunMetadataRepository:
    # Isolate each test with a unique schema while reusing the container.
    schema = f"control_{uuid.uuid4().hex[:8]}"
    return PostgresRunMetadataRepository(postgres_dsn, schema=schema)


def _run(
    run_id: str,
    *,
    dataset_name: str = "account_transactions",
    file_name: str = "transactions.csv",
    sha256: str,
    status: IngestionRunStatus = IngestionRunStatus.LANDED,
    passed: bool = True,
    header: tuple[str, ...] = ("booked_at", "amount"),
    row_count: int = 1,
    issues: tuple[ValidationIssue, ...] = (),
    created_at: datetime,
) -> IngestionRunCreate:
    return IngestionRunCreate(
        run_id=run_id,
        source_name="manual-upload",
        dataset_name=dataset_name,
        file_name=file_name,
        raw_path=f"s3://landing/{dataset_name}/{run_id}/{file_name}",
        manifest_path=f"s3://landing/{dataset_name}/{run_id}/manifest.json",
        sha256=sha256,
        row_count=row_count,
        header=header,
        status=status,
        passed=passed,
        issues=issues,
        created_at=created_at,
    )


def test_postgres_repository_persists_validation_issues_and_status_filters(
    repository: PostgresRunMetadataRepository,
) -> None:
    base = datetime(2026, 3, 9, tzinfo=UTC)
    repository.create_run(
        _run(
            "run-001",
            sha256="shared-hash",
            row_count=2,
            created_at=base,
        )
    )
    repository.create_run(
        _run(
            "run-002",
            file_name="transactions-invalid.csv",
            sha256="rejected-hash",
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
            created_at=base + timedelta(minutes=1),
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


def test_postgres_repository_list_runs_supports_pagination(
    repository: PostgresRunMetadataRepository,
) -> None:
    base = datetime(2026, 3, 10, tzinfo=UTC)
    for index in range(4):
        repository.create_run(
            _run(
                f"run-{index:02d}",
                sha256=f"hash-{index}",
                created_at=base + timedelta(minutes=index),
            )
        )

    first_page = repository.list_runs(limit=2, offset=0)
    second_page = repository.list_runs(limit=2, offset=2)
    all_runs = repository.list_runs()

    assert len(first_page) == 2
    assert len(second_page) == 2
    assert len(all_runs) == 4
    assert not ({run.run_id for run in first_page} & {run.run_id for run in second_page})


def test_postgres_repository_count_runs_supports_dataset_status_and_date_filters(
    repository: PostgresRunMetadataRepository,
) -> None:
    base = datetime(2026, 3, 11, tzinfo=UTC)
    repository.create_run(
        _run(
            "run-account-landed",
            dataset_name="account_transactions",
            sha256="hash-account-landed",
            status=IngestionRunStatus.LANDED,
            passed=True,
            created_at=base,
        )
    )
    repository.create_run(
        _run(
            "run-account-rejected",
            dataset_name="account_transactions",
            sha256="hash-account-rejected",
            status=IngestionRunStatus.REJECTED,
            passed=False,
            created_at=base + timedelta(minutes=1),
        )
    )
    repository.create_run(
        _run(
            "run-card-landed",
            dataset_name="card_transactions",
            sha256="hash-card-landed",
            status=IngestionRunStatus.LANDED,
            passed=True,
            created_at=base + timedelta(minutes=2),
        )
    )

    assert repository.count_runs() == 3
    assert repository.count_runs(dataset_name="account_transactions") == 2
    assert repository.count_runs(status=IngestionRunStatus.REJECTED) == 1
    assert repository.count_runs(status=IngestionRunStatus.LANDED) == 2
    assert repository.count_runs(from_date=base + timedelta(minutes=1)) == 2
    assert repository.count_runs(to_date=base + timedelta(minutes=1)) == 2


def test_postgres_repository_find_run_by_sha256_can_be_scoped_to_dataset(
    repository: PostgresRunMetadataRepository,
) -> None:
    base = datetime(2026, 3, 12, tzinfo=UTC)
    repository.create_run(
        _run(
            "run-account-early",
            dataset_name="account_transactions",
            sha256="shared-hash",
            created_at=base,
        )
    )
    repository.create_run(
        _run(
            "run-card",
            dataset_name="card_transactions",
            sha256="shared-hash",
            created_at=base + timedelta(minutes=1),
        )
    )
    repository.create_run(
        _run(
            "run-account-late",
            dataset_name="account_transactions",
            sha256="shared-hash",
            created_at=base + timedelta(minutes=2),
        )
    )

    account_run = repository.find_run_by_sha256(
        "shared-hash",
        dataset_name="account_transactions",
    )
    card_run = repository.find_run_by_sha256(
        "shared-hash",
        dataset_name="card_transactions",
    )
    first_global = repository.find_run_by_sha256("shared-hash")

    assert account_run is not None
    assert card_run is not None
    assert first_global is not None
    assert account_run.run_id == "run-account-early"
    assert card_run.run_id == "run-card"
    assert first_global.run_id == "run-account-early"
