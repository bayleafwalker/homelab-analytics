from pathlib import Path
import unittest

from packages.pipelines.csv_validation import (
    ColumnContract,
    ColumnType,
    DatasetContract,
    validate_csv_text,
)


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


class CsvLandingValidationTests(unittest.TestCase):
    def test_valid_csv_passes_contract_and_type_checks(self) -> None:
        content = (FIXTURES / "account_transactions_valid.csv").read_text()

        result = validate_csv_text(content, ACCOUNT_TRANSACTION_CONTRACT)

        self.assertTrue(result.passed)
        self.assertEqual(2, result.row_count)
        self.assertEqual([], result.issues)

    def test_missing_required_column_fails_validation(self) -> None:
        content = (FIXTURES / "account_transactions_missing_column.csv").read_text()

        result = validate_csv_text(content, ACCOUNT_TRANSACTION_CONTRACT)

        self.assertFalse(result.passed)
        self.assertIn("currency", {issue.column for issue in result.issues})
        self.assertIn(
            "missing_required_column",
            {issue.code for issue in result.issues},
        )

    def test_invalid_typed_values_are_reported_with_row_context(self) -> None:
        content = (FIXTURES / "account_transactions_invalid_values.csv").read_text()

        result = validate_csv_text(content, ACCOUNT_TRANSACTION_CONTRACT)

        self.assertFalse(result.passed)
        self.assertEqual(1, result.row_count)
        self.assertEqual(
            {"invalid_date", "invalid_decimal"},
            {issue.code for issue in result.issues},
        )
        self.assertEqual({2}, {issue.row_number for issue in result.issues})


if __name__ == "__main__":
    unittest.main()
