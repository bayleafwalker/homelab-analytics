from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from packages.pipelines.csv_validation import (
    ColumnContract,
    ColumnType,
    DatasetContract,
)
from packages.storage.blob import FilesystemBlobStore
from packages.storage.landing_service import LandingService
from packages.storage.run_metadata import IngestionRunStatus, RunMetadataRepository


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


ACCOUNT_TRANSACTION_CONTRACT = DatasetContract(
    dataset_name="account_transactions",
    columns=(
        ColumnContract("booked_at", ColumnType.DATE),
        ColumnContract("account_id", ColumnType.STRING),
        ColumnContract("counterparty_name", ColumnType.STRING),
        ColumnContract("amount", ColumnType.DECIMAL),
        ColumnContract("currency", ColumnType.STRING),
        ColumnContract("description", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

CARD_TRANSACTION_CONTRACT = DatasetContract(
    dataset_name="card_transactions",
    columns=ACCOUNT_TRANSACTION_CONTRACT.columns,
    allow_extra_columns=ACCOUNT_TRANSACTION_CONTRACT.allow_extra_columns,
)


class LandingServiceTests(unittest.TestCase):
    def test_landing_service_uses_blob_store_and_metadata_store(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            blob_store = FilesystemBlobStore(temp_root / "landing")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            service = LandingService(blob_store, metadata_repository)

            result = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                source_name="manual-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )

            self.assertTrue(Path(result.raw_path).is_file())
            self.assertTrue(Path(result.manifest_path).is_file())
            self.assertEqual(
                b"booked_at,account_id,counterparty_name,amount,currency,description\n"
                b"2026-01-02,CHK-001,Electric Utility,-84.15,EUR,Monthly bill\n"
                b"2026-01-03,CHK-001,Employer,2450.00,EUR,Salary\n",
                blob_store.read_bytes(result.raw_path),
            )

            manifest = json.loads(Path(result.manifest_path).read_text())
            persisted = metadata_repository.get_run(result.run_id)
            self.assertEqual("manual-upload", manifest["source_name"])
            self.assertEqual(IngestionRunStatus.LANDED, persisted.status)

    def test_duplicate_file_is_rejected_with_duplicate_file_issue(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            blob_store = FilesystemBlobStore(temp_root / "landing")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            service = LandingService(blob_store, metadata_repository)

            first = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                source_name="first-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )
            self.assertTrue(first.validation.passed)

            second = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                source_name="second-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )

            self.assertFalse(second.validation.passed)
            issue_codes = [i.code for i in second.validation.issues]
            self.assertIn("duplicate_file", issue_codes)
            duplicate_issue = next(
                i for i in second.validation.issues if i.code == "duplicate_file"
            )
            self.assertIn(first.run_id, duplicate_issue.message)

    def test_duplicate_detection_ignores_previously_rejected_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            blob_store = FilesystemBlobStore(temp_root / "landing")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            service = LandingService(blob_store, metadata_repository)

            # Land an invalid file — stored as REJECTED
            first = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_missing_column.csv",
                source_name="first-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )
            self.assertFalse(first.validation.passed)

            # Landing the same bytes again must NOT inject a duplicate_file issue
            second = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_missing_column.csv",
                source_name="second-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )
            issue_codes = [i.code for i in second.validation.issues]
            self.assertNotIn("duplicate_file", issue_codes)

    def test_duplicate_detection_is_scoped_to_dataset(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            blob_store = FilesystemBlobStore(temp_root / "landing")
            metadata_repository = RunMetadataRepository(temp_root / "runs.db")
            service = LandingService(blob_store, metadata_repository)

            first = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                source_name="account-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )
            self.assertTrue(first.validation.passed)

            second = service.ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                source_name="card-upload",
                contract=CARD_TRANSACTION_CONTRACT,
            )

            self.assertTrue(second.validation.passed)
            self.assertNotIn(
                "duplicate_file",
                [issue.code for issue in second.validation.issues],
            )


if __name__ == "__main__":
    unittest.main()
