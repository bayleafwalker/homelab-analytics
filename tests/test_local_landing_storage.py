from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from packages.pipelines.csv_validation import (
    ColumnContract,
    ColumnType,
    DatasetContract,
)
from packages.storage.local_landing import ingest_csv_file
from packages.storage.run_metadata import RunMetadataRepository


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


class LocalLandingStorageTests(unittest.TestCase):
    def test_valid_csv_is_copied_and_manifested(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                landing_root=Path(temp_dir),
                source_name="manual-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )

            self.assertTrue(result.validation.passed)
            self.assertTrue(Path(result.raw_path).is_file())
            self.assertTrue(Path(result.manifest_path).is_file())

            manifest = json.loads(Path(result.manifest_path).read_text())
            self.assertEqual("manual-upload", manifest["source_name"])
            self.assertEqual("account_transactions", manifest["dataset_name"])
            self.assertEqual(2, manifest["row_count"])
            self.assertTrue(manifest["passed"])

    def test_invalid_csv_is_still_landed_with_failed_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            result = ingest_csv_file(
                source_path=FIXTURES / "account_transactions_invalid_values.csv",
                landing_root=Path(temp_dir),
                source_name="manual-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
            )

            manifest = json.loads(Path(result.manifest_path).read_text())

            self.assertFalse(result.validation.passed)
            self.assertFalse(manifest["passed"])
            self.assertEqual(
                {"invalid_date", "invalid_decimal"},
                {issue["code"] for issue in manifest["issues"]},
            )
            self.assertEqual(
                result.sha256,
                manifest["sha256"],
            )

    def test_landing_can_persist_run_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            landing_root = Path(temp_dir) / "landing"
            metadata_repository = RunMetadataRepository(Path(temp_dir) / "runs.db")

            result = ingest_csv_file(
                source_path=FIXTURES / "account_transactions_valid.csv",
                landing_root=landing_root,
                source_name="manual-upload",
                contract=ACCOUNT_TRANSACTION_CONTRACT,
                metadata_repository=metadata_repository,
            )

            persisted = metadata_repository.get_run(result.run_id)

            self.assertEqual(result.run_id, persisted.run_id)
            self.assertEqual("manual-upload", persisted.source_name)
            self.assertEqual("account_transactions_valid.csv", persisted.file_name)
            self.assertTrue(persisted.passed)
            self.assertEqual(2, persisted.row_count)
            self.assertEqual(tuple(result.validation.header), persisted.header)


if __name__ == "__main__":
    unittest.main()
