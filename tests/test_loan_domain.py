"""Tests for the loan domain — landing, transformation, promotion, and marts.

Covers:
- CanonicalLoanRepayment parsing
- LoanService landing contract validation
- TransformationService load + mart refresh
- promote_loan_repayment_run
"""

from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.builtin_promotion_handlers import promote_loan_repayment_run
from packages.pipelines.loan_service import (
    CanonicalLoanRepayment,
    LoanService,
    load_canonical_loan_repayments_bytes,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import RunMetadataRepository

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class CanonicalLoanRepaymentTests(unittest.TestCase):
    def test_load_valid_csv_returns_all_rows(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        self.assertEqual(6, len(repayments))

    def test_repayment_is_frozen_dataclass(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        r = repayments[0]
        self.assertIsInstance(r, CanonicalLoanRepayment)
        with self.assertRaises((AttributeError, TypeError)):
            r.loan_id = "changed"  # type: ignore[misc]

    def test_repayment_month_is_yyyy_mm(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        for r in repayments:
            self.assertRegex(r.repayment_month, r"^\d{4}-\d{2}$")

    def test_loan_definition_fields_populated_from_csv(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        mortgage = next(r for r in repayments if r.loan_id == "mortgage-001")
        self.assertEqual("Home Mortgage", mortgage.loan_name)
        self.assertEqual("First National Bank", mortgage.lender)
        self.assertEqual("mortgage", mortgage.loan_type)
        self.assertEqual(Decimal("350000.00"), mortgage.principal)

    def test_payment_amount_is_decimal(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        for r in repayments:
            self.assertIsInstance(r.payment_amount, Decimal)

    def test_optional_portions_parsed_correctly(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        with_portions = [r for r in repayments if r.principal_portion is not None]
        self.assertGreater(len(with_portions), 0)
        for r in with_portions:
            self.assertIsInstance(r.principal_portion, Decimal)
            self.assertIsInstance(r.interest_portion, Decimal)

    def test_extra_amount_none_when_empty(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        for r in repayments:
            self.assertIsNone(r.extra_amount)

    def test_two_distinct_loan_ids(self) -> None:
        repayments = load_canonical_loan_repayments_bytes(
            (FIXTURES / "loan_repayments_valid.csv").read_bytes()
        )
        loan_ids = {r.loan_id for r in repayments}
        self.assertEqual({"mortgage-001", "personal-001"}, loan_ids)


class LoanServiceTests(unittest.TestCase):
    def _make_service(self, temp_dir: str) -> LoanService:
        return LoanService(
            landing_root=Path(temp_dir) / "landing",
            metadata_repository=RunMetadataRepository(Path(temp_dir) / "runs.db"),
        )

    def test_ingest_valid_csv_creates_landed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "loan_repayments_valid.csv")
            self.assertEqual("landed", run.status.value)
            self.assertEqual("loan_repayments", run.dataset_name)

    def test_get_canonical_repayments_returns_rows_for_passed_run(self) -> None:
        with TemporaryDirectory() as temp_dir:
            svc = self._make_service(temp_dir)
            run = svc.ingest_file(FIXTURES / "loan_repayments_valid.csv")
            repayments = svc.get_canonical_loan_repayments(run.run_id)
            self.assertEqual(6, len(repayments))
            self.assertIsInstance(repayments[0], CanonicalLoanRepayment)


class LoanTransformationTests(unittest.TestCase):
    def _make_rows(self) -> list[dict]:
        return [
            {
                "loan_id": "loan-001",
                "loan_name": "Test Mortgage",
                "lender": "Test Bank",
                "loan_type": "mortgage",
                "principal": "200000.00",
                "annual_rate": "0.045",
                "term_months": "240",
                "start_date": "2023-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2026-01-01",
                "repayment_month": "2026-01",
                "payment_amount": "1265.00",
                "principal_portion": "515.00",
                "interest_portion": "750.00",
                "extra_amount": None,
                "currency": "EUR",
            },
            {
                "loan_id": "loan-001",
                "loan_name": "Test Mortgage",
                "lender": "Test Bank",
                "loan_type": "mortgage",
                "principal": "200000.00",
                "annual_rate": "0.045",
                "term_months": "240",
                "start_date": "2023-01-01",
                "payment_frequency": "monthly",
                "repayment_date": "2026-02-01",
                "repayment_month": "2026-02",
                "payment_amount": "1265.00",
                "principal_portion": "517.00",
                "interest_portion": "748.00",
                "extra_amount": None,
                "currency": "EUR",
            },
        ]

    def test_load_loan_repayments_inserts_facts(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        inserted = svc.load_loan_repayments(self._make_rows(), run_id="run-loan-001")
        self.assertEqual(2, inserted)

    def test_load_loan_repayments_empty_returns_zero(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        self.assertEqual(0, svc.load_loan_repayments([]))

    def test_count_loan_repayments(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-loan-001")
        self.assertEqual(2, svc.count_loan_repayments())
        self.assertEqual(2, svc.count_loan_repayments("run-loan-001"))
        self.assertEqual(0, svc.count_loan_repayments("run-other"))

    def test_load_loan_repayments_upserts_dim_loan(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        loans = svc.get_current_loans()
        loan_ids = {row["loan_id"] for row in loans}
        self.assertIn("loan-001", loan_ids)

    def test_refresh_loan_schedule_projected(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        count = svc.refresh_loan_schedule_projected()
        # 240-month mortgage should produce 240 schedule rows
        self.assertEqual(240, count)

    def test_refresh_loan_repayment_variance(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        count = svc.refresh_loan_repayment_variance()
        self.assertGreater(count, 0)

    def test_refresh_loan_overview(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        svc.refresh_loan_repayment_variance()
        count = svc.refresh_loan_overview()
        self.assertEqual(1, count)

    def test_get_loan_overview_returns_rows(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        svc.refresh_loan_repayment_variance()
        svc.refresh_loan_overview()
        rows = svc.get_loan_overview()
        self.assertEqual(1, len(rows))
        self.assertEqual("loan-001", rows[0]["loan_id"])
        self.assertEqual("Test Mortgage", rows[0]["loan_name"])

    def test_get_loan_schedule_filtered_by_loan_id(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        rows = svc.get_loan_schedule_projected(loan_id="loan-001")
        self.assertEqual(240, len(rows))

    def test_get_loan_schedule_unknown_loan_id_returns_empty(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        rows = svc.get_loan_schedule_projected(loan_id="unknown")
        self.assertEqual([], rows)

    def test_get_loan_repayment_variance_filtered_by_loan_id(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        svc.refresh_loan_repayment_variance()
        rows = svc.get_loan_repayment_variance(loan_id="loan-001")
        self.assertGreater(len(rows), 0)

    def test_loan_overview_balance_estimate(self) -> None:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_loan_repayments(self._make_rows(), run_id="run-001")
        svc.refresh_loan_schedule_projected()
        svc.refresh_loan_overview()
        rows = svc.get_loan_overview()
        self.assertGreater(Decimal(str(rows[0]["current_balance_estimate"])), Decimal("0"))


class PromoteLoanRepaymentRunTests(unittest.TestCase):
    def test_promote_loan_repayment_run_loads_facts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            loan_svc = LoanService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = loan_svc.ingest_file(FIXTURES / "loan_repayments_valid.csv")
            result = promote_loan_repayment_run(
                run.run_id,
                loan_service=loan_svc,
                transformation_service=ts,
            )

            self.assertFalse(result.skipped)
            self.assertEqual(6, result.facts_loaded)
            self.assertIn("mart_loan_schedule_projected", result.marts_refreshed)
            self.assertIn("mart_loan_repayment_variance", result.marts_refreshed)
            self.assertIn("mart_loan_overview", result.marts_refreshed)
            self.assertEqual(6, ts.count_loan_repayments())

    def test_promote_already_promoted_run_returns_skipped(self) -> None:
        with TemporaryDirectory() as temp_dir:
            loan_svc = LoanService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = loan_svc.ingest_file(FIXTURES / "loan_repayments_valid.csv")
            promote_loan_repayment_run(
                run.run_id,
                loan_service=loan_svc,
                transformation_service=ts,
            )
            result2 = promote_loan_repayment_run(
                run.run_id,
                loan_service=loan_svc,
                transformation_service=ts,
            )

            self.assertTrue(result2.skipped)
            self.assertEqual("run already promoted", result2.skip_reason)
            self.assertEqual(6, ts.count_loan_repayments())

    def test_promote_loan_run_materialises_schedule(self) -> None:
        with TemporaryDirectory() as temp_dir:
            loan_svc = LoanService(
                landing_root=Path(temp_dir) / "landing",
                metadata_repository=RunMetadataRepository(
                    Path(temp_dir) / "runs.db"
                ),
            )
            ts = TransformationService(DuckDBStore.memory())

            run = loan_svc.ingest_file(FIXTURES / "loan_repayments_valid.csv")
            promote_loan_repayment_run(
                run.run_id,
                loan_service=loan_svc,
                transformation_service=ts,
            )

            schedule = ts.get_loan_schedule_projected()
            self.assertGreater(len(schedule), 0)

            overview = ts.get_loan_overview()
            self.assertEqual(2, len(overview))  # mortgage-001 + personal-001


if __name__ == "__main__":
    unittest.main()
