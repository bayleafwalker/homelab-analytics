from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest

from packages.pipelines.account_transaction_inbox import process_account_transaction_inbox
from packages.pipelines.account_transaction_service import AccountTransactionService
from packages.storage.run_metadata import IngestionRunStatus, RunMetadataRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class AccountTransactionInboxTests(unittest.TestCase):
    def test_inbox_processing_moves_valid_and_invalid_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            inbox_dir = temp_root / "inbox"
            processed_dir = temp_root / "processed"
            failed_dir = temp_root / "failed"
            inbox_dir.mkdir()

            valid_inbox_path = inbox_dir / "valid.csv"
            invalid_inbox_path = inbox_dir / "invalid.csv"
            shutil.copyfile(
                FIXTURES / "account_transactions_valid.csv",
                valid_inbox_path,
            )
            shutil.copyfile(
                FIXTURES / "account_transactions_invalid_values.csv",
                invalid_inbox_path,
            )

            service = AccountTransactionService(
                landing_root=temp_root / "landing",
                metadata_repository=RunMetadataRepository(temp_root / "runs.db"),
            )

            result = process_account_transaction_inbox(
                service=service,
                inbox_dir=inbox_dir,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
                source_name="folder-watch",
            )

            self.assertEqual(2, result.discovered_files)
            self.assertEqual(1, result.processed_files)
            self.assertEqual(1, result.rejected_files)
            self.assertEqual(0, len(list(inbox_dir.iterdir())))

            processed_files = list(processed_dir.iterdir())
            failed_files = list(failed_dir.iterdir())
            self.assertEqual(1, len(processed_files))
            self.assertEqual(1, len(failed_files))
            self.assertTrue(processed_files[0].name.endswith("-valid.csv"))
            self.assertTrue(failed_files[0].name.endswith("-invalid.csv"))

            runs = service.list_runs()
            self.assertEqual(2, len(runs))
            self.assertEqual(
                {IngestionRunStatus.LANDED, IngestionRunStatus.REJECTED},
                {run.status for run in runs},
            )


if __name__ == "__main__":
    unittest.main()
