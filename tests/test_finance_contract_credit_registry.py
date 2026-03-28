from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from packages.domains.finance.contracts import (
    FINNISH_POSITIVE_CREDIT_REGISTRY_CONTRACT_ID,
    FinanceDatasetType,
    PositiveCreditRegistrySnapshotParser,
    load_positive_credit_registry_snapshot_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "finance_contracts"


class FinanceContractCreditRegistryTests(unittest.TestCase):
    def test_parser_detects_positive_credit_registry_exports(self) -> None:
        parser = PositiveCreditRegistrySnapshotParser()
        header_bytes = (FIXTURES / "credit_registry_sample.txt").read_bytes()

        self.assertEqual(FINNISH_POSITIVE_CREDIT_REGISTRY_CONTRACT_ID, parser.contract_id)
        self.assertEqual(
            FinanceDatasetType.EXTERNAL_RECONCILIATION_SNAPSHOT,
            parser.dataset_type,
        )
        self.assertTrue(parser.detect("credit_registry_sample.txt", header_bytes))
        self.assertFalse(parser.detect("credit_registry_sample.csv", header_bytes))

    def test_parser_extracts_snapshot_credit_and_income_records(self) -> None:
        parser = PositiveCreditRegistrySnapshotParser()
        source_bytes = (FIXTURES / "credit_registry_sample.txt").read_bytes()

        result = parser.parse(source_bytes, "credit_registry_sample.txt")

        self.assertEqual(
            FinanceDatasetType.EXTERNAL_RECONCILIATION_SNAPSHOT,
            result.dataset_type,
        )
        self.assertEqual(5, len(result.records))
        self.assertEqual([], result.warnings)
        self.assertEqual("positive-credit-registry-text", result.metadata["source_format"])
        self.assertEqual("OP Suomi Oy", result.metadata["requestor_name"])
        self.assertEqual("PCR-2026-03-15-001", result.metadata["report_reference"])
        self.assertEqual("1234567-8", result.metadata["requester_id"])
        self.assertEqual(2, result.metadata["parsed_credit_count"])
        self.assertEqual(2, result.metadata["parsed_income_count"])

        snapshot = result.records[0]
        self.assertEqual("snapshot", snapshot["record_type"])
        self.assertEqual(2, snapshot["credit_count"])
        self.assertEqual("OP Suomi Oy", snapshot["requestor_name"])

        first_credit = result.records[1]
        self.assertEqual("credit", first_credit["record_type"])
        self.assertEqual("installment", first_credit["credit_type"])
        self.assertEqual("OP Rahoitus Oy", first_credit["creditor"])
        self.assertEqual("L-001", first_credit["credit_identifier"])
        self.assertEqual(Decimal("5000.00"), first_credit["granted_amount"])
        self.assertEqual(Decimal("4200.00"), first_credit["balance"])
        self.assertEqual(Decimal("120.00"), first_credit["monthly_payment"])

        first_income = result.records[3]
        self.assertEqual("income", first_income["record_type"])
        self.assertEqual("2025-12", first_income["income_month"])
        self.assertEqual(Decimal("3100.00"), first_income["reported_amount"])
        self.assertEqual("EUR", first_income["currency"])

        validation = parser.validate(result)

        self.assertTrue(validation.passed)
        self.assertEqual(5, validation.row_count)
        self.assertEqual(
            ["snapshot_at", "report_reference", "requester_id", "credit_count"],
            validation.header,
        )
        self.assertEqual([], validation.issues)

    def test_loader_returns_registry_records(self) -> None:
        records = load_positive_credit_registry_snapshot_bytes(
            (FIXTURES / "credit_registry_sample.txt").read_bytes()
        )

        self.assertEqual(5, len(records))
        self.assertEqual("credit", records[1]["record_type"])
        self.assertEqual("income", records[-1]["record_type"])


if __name__ == "__main__":
    unittest.main()
