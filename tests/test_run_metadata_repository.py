import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.csv_validation import ValidationIssue
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataRepository,
)


class RunMetadataRepositoryTests(unittest.TestCase):
    def test_repository_persists_and_reads_run_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            created = repository.create_run(
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

            self.assertEqual(created.run_id, fetched.run_id)
            self.assertEqual("manual-upload", fetched.source_name)
            self.assertEqual(("booked_at", "amount"), fetched.header)
            self.assertEqual(IngestionRunStatus.LANDED, fetched.status)
            self.assertTrue(fetched.passed)
            self.assertEqual([], fetched.issues)

    def test_repository_records_validation_issues(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            repository.create_run(
                IngestionRunCreate(
                    run_id="run-002",
                    source_name="manual-upload",
                    dataset_name="account_transactions",
                    file_name="transactions.csv",
                    raw_path="/landing/run-002/transactions.csv",
                    manifest_path="/landing/run-002/manifest.json",
                    sha256="def456",
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

            fetched = repository.get_run("run-002")

            self.assertEqual(IngestionRunStatus.REJECTED, fetched.status)
            self.assertFalse(fetched.passed)
            self.assertEqual(1, len(fetched.issues))
            self.assertEqual("invalid_decimal", fetched.issues[0].code)


    def test_list_runs_filters_by_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            for i, (run_id, status, passed) in enumerate(
                [
                    ("run-a", IngestionRunStatus.LANDED, True),
                    ("run-b", IngestionRunStatus.REJECTED, False),
                    ("run-c", IngestionRunStatus.LANDED, True),
                ]
            ):
                repository.create_run(
                    IngestionRunCreate(
                        run_id=run_id,
                        source_name="test",
                        dataset_name="account_transactions",
                        file_name=f"f{i}.csv",
                        raw_path=f"/landing/{run_id}/f.csv",
                        manifest_path=f"/landing/{run_id}/m.json",
                        sha256=f"hash{i}",
                        row_count=1,
                        header=("booked_at",),
                        status=status,
                        passed=passed,
                    )
                )

            landed = repository.list_runs(status=IngestionRunStatus.LANDED)
            rejected = repository.list_runs(status=IngestionRunStatus.REJECTED)

            self.assertEqual(2, len(landed))
            self.assertTrue(all(r.status == IngestionRunStatus.LANDED for r in landed))
            self.assertEqual(1, len(rejected))
            self.assertEqual("run-b", rejected[0].run_id)

    def test_list_runs_supports_pagination(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            for i in range(4):
                repository.create_run(
                    IngestionRunCreate(
                        run_id=f"run-{i:02d}",
                        source_name="test",
                        dataset_name="account_transactions",
                        file_name=f"f{i}.csv",
                        raw_path=f"/landing/run-{i:02d}/f.csv",
                        manifest_path=f"/landing/run-{i:02d}/m.json",
                        sha256=f"hash{i}",
                        row_count=1,
                        header=("booked_at",),
                        status=IngestionRunStatus.LANDED,
                        passed=True,
                    )
                )

            first_page = repository.list_runs(limit=2, offset=0)
            second_page = repository.list_runs(limit=2, offset=2)
            all_runs = repository.list_runs()

            self.assertEqual(2, len(first_page))
            self.assertEqual(2, len(second_page))
            self.assertEqual(4, len(all_runs))
            self.assertFalse({r.run_id for r in first_page} & {r.run_id for r in second_page})

    def test_count_runs_with_filters(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            for i, (status, ds) in enumerate(
                [
                    (IngestionRunStatus.LANDED, "account_transactions"),
                    (IngestionRunStatus.REJECTED, "account_transactions"),
                    (IngestionRunStatus.LANDED, "card_transactions"),
                ]
            ):
                repository.create_run(
                    IngestionRunCreate(
                        run_id=f"run-{i}",
                        source_name="test",
                        dataset_name=ds,
                        file_name=f"f{i}.csv",
                        raw_path=f"/landing/run-{i}/f.csv",
                        manifest_path=f"/landing/run-{i}/m.json",
                        sha256=f"hash{i}",
                        row_count=1,
                        header=("booked_at",),
                        status=status,
                        passed=status == IngestionRunStatus.LANDED,
                    )
                )

            self.assertEqual(3, repository.count_runs())
            self.assertEqual(2, repository.count_runs(dataset_name="account_transactions"))
            self.assertEqual(1, repository.count_runs(status=IngestionRunStatus.REJECTED))
            self.assertEqual(2, repository.count_runs(status=IngestionRunStatus.LANDED))

    def test_find_run_by_sha256_can_be_scoped_to_dataset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            repository.create_run(
                IngestionRunCreate(
                    run_id="run-account",
                    source_name="test",
                    dataset_name="account_transactions",
                    file_name="a.csv",
                    raw_path="/landing/run-account/a.csv",
                    manifest_path="/landing/run-account/m.json",
                    sha256="shared-hash",
                    row_count=1,
                    header=("booked_at",),
                    status=IngestionRunStatus.LANDED,
                    passed=True,
                )
            )
            repository.create_run(
                IngestionRunCreate(
                    run_id="run-card",
                    source_name="test",
                    dataset_name="card_transactions",
                    file_name="c.csv",
                    raw_path="/landing/run-card/c.csv",
                    manifest_path="/landing/run-card/m.json",
                    sha256="shared-hash",
                    row_count=1,
                    header=("booked_at",),
                    status=IngestionRunStatus.LANDED,
                    passed=True,
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

            self.assertEqual("run-account", account_run.run_id)
            self.assertEqual("run-card", card_run.run_id)


if __name__ == "__main__":
    unittest.main()
