"""Tests for ScenarioService — loan what-if scenarios.

Covers:
- create_loan_what_if_scenario: extra repayment, rate change, staleness
- get_scenario_comparison: baseline vs projected rows, assumption list
- archive_scenario: soft delete
"""

from __future__ import annotations

import unittest
from decimal import Decimal

from packages.pipelines.scenario_service import (
    archive_scenario,
    create_loan_what_if_scenario,
    ensure_scenario_storage,
    get_scenario,
    get_scenario_assumptions,
    get_scenario_comparison,
    list_scenarios,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _load_fixture_loan(svc: TransformationService, run_id: str = "run-001") -> None:
    svc.load_loan_repayments(
        [
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
            }
        ],
        run_id=run_id,
    )
    svc.refresh_loan_schedule_projected()


class ScenarioExtraRepaymentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_loan(self.svc)

    def test_extra_repayment_reduces_months(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("500"),
        )
        self.assertGreater(result.months_saved, 0)

    def test_extra_repayment_saves_interest(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("500"),
        )
        self.assertGreater(result.interest_saved, Decimal("0"))

    def test_scenario_payoff_earlier_than_baseline(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("500"),
        )
        self.assertIsNotNone(result.new_payoff_date)
        self.assertIsNotNone(result.baseline_payoff_date)
        self.assertLess(result.new_payoff_date, result.baseline_payoff_date)

    def test_proj_loan_schedule_rows_written(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("500"),
        )
        comparison = get_scenario_comparison(self.store, result.scenario_id)
        self.assertIsNotNone(comparison)
        self.assertGreater(len(comparison.scenario_rows), 0)


class ScenarioRateChangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_loan(self.svc)

    def test_rate_decrease_lowers_monthly_payment(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            annual_rate=Decimal("0.025"),
        )
        comparison = get_scenario_comparison(self.store, result.scenario_id)
        # First period: scenario payment should be lower than baseline
        baseline_payment = Decimal(str(comparison.baseline_rows[0]["payment"]))
        scenario_payment = Decimal(str(comparison.scenario_rows[0]["payment"]))
        self.assertLess(scenario_payment, baseline_payment)

    def test_rate_increase_raises_total_interest(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            annual_rate=Decimal("0.065"),
        )
        # interest_saved should be negative (more interest paid)
        self.assertLess(result.interest_saved, Decimal("0"))

    def test_rate_assumption_recorded(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            annual_rate=Decimal("0.025"),
        )
        assumptions = get_scenario_assumptions(self.store, result.scenario_id)
        keys = {a["assumption_key"] for a in assumptions}
        self.assertIn("annual_rate", keys)
        rate_assumption = next(a for a in assumptions if a["assumption_key"] == "annual_rate")
        self.assertEqual(Decimal("0.045"), Decimal(str(rate_assumption["baseline_value"])))
        self.assertEqual(Decimal("0.025"), Decimal(str(rate_assumption["override_value"])))


class ScenarioStalenessTests(unittest.TestCase):
    def test_scenario_is_not_stale_on_same_run(self) -> None:
        store = DuckDBStore.memory()
        svc = TransformationService(store)
        _load_fixture_loan(svc, run_id="run-A")
        result = create_loan_what_if_scenario(store, loan_id="loan-001", extra_repayment=Decimal("200"))
        comparison = get_scenario_comparison(store, result.scenario_id)
        self.assertFalse(comparison.is_stale)

    def test_scenario_is_stale_after_new_run(self) -> None:
        store = DuckDBStore.memory()
        svc = TransformationService(store)
        _load_fixture_loan(svc, run_id="run-A")
        result = create_loan_what_if_scenario(store, loan_id="loan-001", extra_repayment=Decimal("200"))
        # Ingest a second run — changes the canonical run_id
        svc.load_loan_repayments(
            [
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
                    "repayment_date": "2026-03-01",
                    "repayment_month": "2026-03",
                    "payment_amount": "1265.00",
                    "principal_portion": "520.00",
                    "interest_portion": "745.00",
                    "extra_amount": None,
                    "currency": "EUR",
                }
            ],
            run_id="run-B",
        )
        comparison = get_scenario_comparison(store, result.scenario_id)
        self.assertTrue(comparison.is_stale)


class ScenarioAssumptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        svc = TransformationService(self.store)
        _load_fixture_loan(svc)

    def test_assumption_list_contains_all_overrides(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("300"),
            annual_rate=Decimal("0.03"),
        )
        assumptions = get_scenario_assumptions(self.store, result.scenario_id)
        keys = {a["assumption_key"] for a in assumptions}
        self.assertIn("extra_repayment", keys)
        self.assertIn("annual_rate", keys)

    def test_no_assumptions_when_no_overrides(self) -> None:
        # No overrides — just using baseline params
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
        )
        assumptions = get_scenario_assumptions(self.store, result.scenario_id)
        self.assertEqual([], assumptions)


class ScenarioArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        svc = TransformationService(self.store)
        _load_fixture_loan(svc)

    def test_archive_sets_status(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("200"),
        )
        archived = archive_scenario(self.store, result.scenario_id)
        self.assertTrue(archived)
        scenario = get_scenario(self.store, result.scenario_id)
        self.assertEqual("archived", scenario["status"])

    def test_archive_preserves_projection_rows(self) -> None:
        result = create_loan_what_if_scenario(
            self.store,
            loan_id="loan-001",
            extra_repayment=Decimal("200"),
        )
        archive_scenario(self.store, result.scenario_id)
        comparison = get_scenario_comparison(self.store, result.scenario_id)
        self.assertGreater(len(comparison.scenario_rows), 0)

    def test_archive_unknown_scenario_returns_false(self) -> None:
        ensure_scenario_storage(self.store)
        self.assertFalse(archive_scenario(self.store, "nonexistent-id"))


class ScenarioListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_loan(self.svc)

    def test_list_returns_active_scenarios(self) -> None:
        create_loan_what_if_scenario(self.store, loan_id="loan-001", extra_repayment=Decimal("500"))
        create_loan_what_if_scenario(self.store, loan_id="loan-001", annual_rate=Decimal("0.035"))
        rows = list_scenarios(self.store)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(r["status"] == "active" for r in rows))

    def test_list_excludes_archived_by_default(self) -> None:
        result = create_loan_what_if_scenario(self.store, loan_id="loan-001", extra_repayment=Decimal("500"))
        archive_scenario(self.store, result.scenario_id)
        rows = list_scenarios(self.store)
        self.assertEqual(len(rows), 0)

    def test_list_includes_archived_when_requested(self) -> None:
        result = create_loan_what_if_scenario(self.store, loan_id="loan-001", extra_repayment=Decimal("500"))
        archive_scenario(self.store, result.scenario_id)
        rows = list_scenarios(self.store, include_archived=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "archived")

    def test_list_ordered_newest_first(self) -> None:
        r1 = create_loan_what_if_scenario(self.store, loan_id="loan-001", extra_repayment=Decimal("100"))
        r2 = create_loan_what_if_scenario(self.store, loan_id="loan-001", extra_repayment=Decimal("200"))
        rows = list_scenarios(self.store)
        scenario_ids = [r["scenario_id"] for r in rows]
        # r2 was created after r1 — it should appear first
        self.assertEqual(scenario_ids[0], r2.scenario_id)
        self.assertEqual(scenario_ids[1], r1.scenario_id)

    def test_list_empty_when_no_scenarios(self) -> None:
        ensure_scenario_storage(self.store)
        rows = list_scenarios(self.store)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
