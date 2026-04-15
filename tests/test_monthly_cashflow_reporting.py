import unittest
from decimal import Decimal
from pathlib import Path

from packages.domains.finance.pipelines.cashflow_analytics import summarize_monthly_cashflow
from packages.domains.finance.pipelines.account_transactions import load_canonical_transactions

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class MonthlyCashflowReportingTests(unittest.TestCase):
    def test_monthly_cashflow_summary_aggregates_income_and_expense(self) -> None:
        transactions = load_canonical_transactions(
            FIXTURES / "account_transactions_valid.csv"
        )

        summaries = summarize_monthly_cashflow(transactions)

        self.assertEqual(1, len(summaries))
        summary = summaries[0]
        self.assertEqual("2026-01", summary.booking_month)
        self.assertEqual(Decimal("2450.00"), summary.income)
        self.assertEqual(Decimal("84.15"), summary.expense)
        self.assertEqual(Decimal("2365.85"), summary.net)
        self.assertEqual(2, summary.transaction_count)


if __name__ == "__main__":
    unittest.main()
