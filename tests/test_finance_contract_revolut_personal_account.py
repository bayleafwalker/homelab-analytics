from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from packages.domains.finance.contracts import (
    REVOLUT_PERSONAL_ACCOUNT_STATEMENT_CONTRACT_ID,
    FinanceDatasetType,
    RevolutPersonalAccountStatementCsvParser,
    load_revolut_personal_account_transactions_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "finance_contracts"


class FinanceContractRevolutPersonalAccountTests(unittest.TestCase):
    def test_parser_detects_revolut_personal_statement_exports(self) -> None:
        parser = RevolutPersonalAccountStatementCsvParser()
        header_bytes = (FIXTURES / "revolut_personal_account_sample.csv").read_bytes().splitlines()[0]

        self.assertEqual(REVOLUT_PERSONAL_ACCOUNT_STATEMENT_CONTRACT_ID, parser.contract_id)
        self.assertEqual(FinanceDatasetType.TRANSACTION_EVENT_STREAM, parser.dataset_type)
        self.assertTrue(parser.detect("revolut_personal_account_sample.csv", header_bytes))
        self.assertFalse(parser.detect("revolut_personal_account_sample.txt", header_bytes))

    def test_parser_extracts_revolut_rows_and_provider_metadata(self) -> None:
        parser = RevolutPersonalAccountStatementCsvParser()
        source_bytes = (FIXTURES / "revolut_personal_account_sample.csv").read_bytes()

        result = parser.parse(source_bytes, "revolut_personal_account_sample.csv")

        self.assertEqual(FinanceDatasetType.TRANSACTION_EVENT_STREAM, result.dataset_type)
        self.assertEqual(3, len(result.records))
        self.assertEqual([], result.warnings)
        self.assertEqual("revolut-personal-csv", result.metadata["source_format"])
        self.assertEqual("REV-001", result.metadata["account_id"])
        self.assertEqual(
            [
                "Type",
                "Product",
                "Started Date",
                "Completed Date",
                "Description",
                "Amount",
                "Fee",
                "Currency",
                "State",
                "Balance",
            ],
            result.metadata["source_header"],
        )

        first = result.records[0]
        self.assertEqual("REV-001", first["account_id"])
        self.assertEqual("Google Pay deposit by *8221", first["counterparty_name"])
        self.assertEqual(Decimal("159.35"), first["amount"])
        self.assertEqual("income", first["direction"])
        self.assertEqual("Deposit", first["provider_type"])
        self.assertEqual("COMPLETED", first["provider_state"])
        self.assertEqual(Decimal("0.00"), first["fee"])
        self.assertEqual(Decimal("159.35"), first["balance"])

        second = result.records[1]
        self.assertEqual("expense", second["direction"])
        self.assertEqual(Decimal("-15.99"), second["amount"])
        self.assertEqual("2025-01-15", second["value_date"].isoformat())

        validation = parser.validate(result)

        self.assertTrue(validation.passed)
        self.assertEqual(3, validation.row_count)
        self.assertEqual(result.metadata["source_header"], validation.header)
        self.assertEqual([], validation.issues)

    def test_loader_returns_canonical_row_dicts(self) -> None:
        rows = load_revolut_personal_account_transactions_bytes(
            (FIXTURES / "revolut_personal_account_sample.csv").read_bytes()
        )

        self.assertEqual(3, len(rows))
        self.assertEqual("Pharmacy Central", rows[2]["counterparty_name"])
        self.assertEqual(Decimal("0.25"), rows[2]["fee"])


if __name__ == "__main__":
    unittest.main()
