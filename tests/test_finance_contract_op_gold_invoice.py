from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from packages.domains.finance.contracts import (
    OP_GOLD_CREDIT_CARD_INVOICE_CONTRACT_ID,
    FinanceDatasetType,
    OPGoldCreditCardInvoicePdfParser,
    load_op_gold_credit_card_invoice_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "finance_contracts"


class FinanceContractOpGoldInvoiceTests(unittest.TestCase):
    def test_parser_detects_op_gold_invoice_pdfs(self) -> None:
        parser = OPGoldCreditCardInvoicePdfParser()
        header_bytes = (FIXTURES / "op_gold_invoice_sample.pdf").read_bytes()

        self.assertEqual(OP_GOLD_CREDIT_CARD_INVOICE_CONTRACT_ID, parser.contract_id)
        self.assertEqual(FinanceDatasetType.STATEMENT_SNAPSHOT, parser.dataset_type)
        self.assertTrue(parser.detect("op_gold_invoice_sample.pdf", header_bytes))
        self.assertFalse(parser.detect("op_gold_invoice_sample.txt", header_bytes))

    def test_parser_extracts_statement_summary_and_line_items(self) -> None:
        parser = OPGoldCreditCardInvoicePdfParser()
        source_bytes = (FIXTURES / "op_gold_invoice_sample.pdf").read_bytes()

        result = parser.parse(source_bytes, "op_gold_invoice_sample.pdf")

        self.assertEqual(FinanceDatasetType.STATEMENT_SNAPSHOT, result.dataset_type)
        self.assertEqual(4, len(result.records))
        self.assertEqual("op-gold-invoice-pdf", result.metadata["source_format"])
        self.assertEqual("fallback-text", result.metadata["extraction_method"])
        self.assertEqual("2026-02-28", result.metadata["statement_date"].isoformat())
        self.assertTrue(
            result.metadata["statement_id"].startswith(
                "op_gold_credit_card_invoice_pdf_v1:2026-02-28:"
            )
        )
        self.assertEqual(3, result.metadata["line_item_count"])

        snapshot = result.records[0]
        self.assertEqual("snapshot", snapshot["record_type"])
        self.assertEqual(Decimal("1200.00"), snapshot["previous_balance"])
        self.assertEqual(Decimal("-500.00"), snapshot["payments_total"])
        self.assertEqual(Decimal("845.30"), snapshot["purchases_total"])
        self.assertEqual(Decimal("12.34"), snapshot["interest_amount"])
        self.assertEqual(Decimal("3.50"), snapshot["service_fee"])
        self.assertEqual(Decimal("200.00"), snapshot["minimum_due"])
        self.assertEqual(Decimal("1561.14"), snapshot["ending_balance"])
        self.assertEqual("high", snapshot["confidence"])

        line_item = result.records[2]
        self.assertEqual("line_item", line_item["record_type"])
        self.assertEqual("Taxi Co", line_item["merchant"])
        self.assertEqual(Decimal("24.10"), line_item["amount"])
        self.assertEqual("medium", line_item["confidence"])

        warning_codes = {warning.code for warning in result.warnings}
        self.assertIn("low_confidence_line_item", warning_codes)

        validation = parser.validate(result)

        self.assertTrue(validation.passed)
        self.assertEqual(4, validation.row_count)
        self.assertEqual(
            [
                "record_type",
                "statement_id",
                "statement_date",
                "period_start",
                "period_end",
                "due_date",
                "amount",
                "confidence",
            ],
            validation.header,
        )
        self.assertEqual([], validation.issues)

    def test_loader_returns_statement_records(self) -> None:
        records = load_op_gold_credit_card_invoice_bytes(
            (FIXTURES / "op_gold_invoice_sample.pdf").read_bytes()
        )

        self.assertEqual(4, len(records))
        self.assertEqual("snapshot", records[0]["record_type"])
        self.assertEqual("Unclear merchant", records[-1]["merchant"])


if __name__ == "__main__":
    unittest.main()
