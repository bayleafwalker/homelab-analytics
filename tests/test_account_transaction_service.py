from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.storage.blob import InMemoryBlobStore
from packages.storage.run_metadata import IngestionRunStatus, RunMetadataRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class AccountTransactionServiceTests(unittest.TestCase):
    def test_service_ingests_valid_csv_and_exposes_cashflow_report(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=repository,
            )

            run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
            runs = service.list_runs()
            summaries = service.get_monthly_cashflow(run.run_id)

            self.assertEqual(IngestionRunStatus.LANDED, run.status)
            self.assertEqual(1, len(runs))
            self.assertEqual(run.run_id, runs[0].run_id)
            self.assertEqual(1, len(summaries))
            self.assertEqual(Decimal("2365.85"), summaries[0].net)

    def test_service_returns_no_cashflow_for_rejected_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=repository,
            )

            run = service.ingest_file(
                FIXTURES / "account_transactions_invalid_values.csv"
            )

            self.assertEqual(IngestionRunStatus.REJECTED, run.status)
            self.assertEqual([], service.get_monthly_cashflow(run.run_id))

    def test_service_can_report_from_in_memory_blob_store(self) -> None:
        with TemporaryDirectory() as temp_dir:
            repository = RunMetadataRepository(Path(temp_dir) / "runs.db")
            service = AccountTransactionService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=repository,
                blob_store=InMemoryBlobStore(),
            )

            run = service.ingest_file(FIXTURES / "account_transactions_valid.csv")
            summaries = service.get_monthly_cashflow(run.run_id)

            self.assertEqual(IngestionRunStatus.LANDED, run.status)
            self.assertEqual(Decimal("2365.85"), summaries[0].net)


if __name__ == "__main__":
    unittest.main()
