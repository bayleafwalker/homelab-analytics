from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from packages.domains.finance.contracts import (
    OP_ACCOUNT_TRANSACTION_CONTRACT_ID,
    FinanceDatasetType,
    OPAccountTransactionCsvParser,
    load_op_account_transactions_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "finance_contracts"


class FinanceContractOpAccountTests(unittest.TestCase):
    def test_parser_detects_op_semicolon_exports(self) -> None:
        parser = OPAccountTransactionCsvParser()
        header_bytes = (FIXTURES / "op_account_sample.csv").read_bytes().splitlines()[0]

        self.assertEqual(OP_ACCOUNT_TRANSACTION_CONTRACT_ID, parser.contract_id)
        self.assertEqual(FinanceDatasetType.TRANSACTION_EVENT_STREAM, parser.dataset_type)
        self.assertTrue(parser.detect("op_account_sample.csv", header_bytes))
        self.assertFalse(parser.detect("op_account_sample.txt", header_bytes))

    def test_parser_normalizes_rows_and_repayment_enrichment(self) -> None:
        parser = OPAccountTransactionCsvParser()
        source_bytes = (FIXTURES / "op_account_sample.csv").read_bytes()

        result = parser.parse(source_bytes, "op_account_sample.csv")

        self.assertEqual(FinanceDatasetType.TRANSACTION_EVENT_STREAM, result.dataset_type)
        self.assertEqual(3, len(result.records))
        self.assertEqual([], result.warnings)
        self.assertEqual("op-semicolon-csv", result.metadata["source_format"])
        self.assertEqual(
            [
                "Kirjauspäivä",
                "Arvopäivä",
                "Tilinumero",
                "Saaja/Maksaja",
                "Summa",
                "Valuutta",
                "Viesti",
                "Arkistotunnus",
                "Tapahtuman tila",
                "Tapahtumalaji",
            ],
            result.metadata["source_header"],
        )

        first = result.records[0]
        self.assertEqual("CHK-001", first["account_id"])
        self.assertEqual("Electric Utility", first["counterparty_name"])
        self.assertEqual(Decimal("-84.15"), first["amount"])
        self.assertEqual("expense", first["direction"])
        self.assertEqual("OP-ARCH-001", first["archive_id"])
        self.assertEqual("Booked", first["provider_state"])
        self.assertEqual("Debit", first["provider_type"])

        second = result.records[1]
        self.assertEqual(Decimal("100.00"), second["repayment_principal"])
        self.assertEqual(Decimal("15.00"), second["repayment_interest"])
        self.assertEqual(Decimal("5.00"), second["repayment_fees"])
        self.assertEqual(Decimal("900.00"), second["remaining_balance"])
        self.assertEqual("expense", second["direction"])
        self.assertEqual("2026-01-03", second["value_date"].isoformat())

        validation = parser.validate(result)

        self.assertTrue(validation.passed)
        self.assertEqual(3, validation.row_count)
        self.assertEqual(result.metadata["source_header"], validation.header)
        self.assertEqual([], validation.issues)

    def test_loader_returns_canonical_row_dicts(self) -> None:
        rows = load_op_account_transactions_bytes(
            (FIXTURES / "op_account_sample.csv").read_bytes()
        )

        self.assertEqual(3, len(rows))
        self.assertEqual("Employer", rows[2]["counterparty_name"])
        self.assertEqual(Decimal("2450.00"), rows[2]["amount"])


if __name__ == "__main__":
    unittest.main()
