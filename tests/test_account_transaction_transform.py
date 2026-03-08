from decimal import Decimal
from pathlib import Path
import unittest

from packages.pipelines.account_transactions import (
    load_canonical_transactions,
    load_canonical_transactions_bytes,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class AccountTransactionTransformTests(unittest.TestCase):
    def test_csv_is_transformed_to_canonical_transactions(self) -> None:
        transactions = load_canonical_transactions(
            FIXTURES / "account_transactions_valid.csv"
        )

        self.assertEqual(2, len(transactions))

        first = transactions[0]
        self.assertEqual("CHK-001", first.account_id)
        self.assertEqual("Electric Utility", first.counterparty_name)
        self.assertEqual(Decimal("-84.15"), first.amount)
        self.assertEqual("expense", first.direction)
        self.assertEqual("2026-01", first.booking_month)

        second = transactions[1]
        self.assertEqual("Employer", second.counterparty_name)
        self.assertEqual(Decimal("2450.00"), second.amount)
        self.assertEqual("income", second.direction)

    def test_csv_bytes_are_transformed_to_canonical_transactions(self) -> None:
        transactions = load_canonical_transactions_bytes(
            (FIXTURES / "account_transactions_valid.csv").read_bytes()
        )

        self.assertEqual(2, len(transactions))
        self.assertEqual(Decimal("2365.85"), sum(t.amount for t in transactions))


if __name__ == "__main__":
    unittest.main()
