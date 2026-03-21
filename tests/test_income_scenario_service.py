"""Tests for income change scenarios — create, compare, archive.

Covers:
- create_income_change_scenario: increase, decrease (job loss), projection rows
- get_income_scenario_comparison: cashflow rows, assumptions
- archive_scenario: reuses shared archive function
- edge cases: no cashflow data raises ValueError
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from packages.pipelines.scenario_service import (
    archive_scenario,
    create_income_change_scenario,
    get_income_scenario_comparison,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _load_fixture_cashflow(svc: TransformationService) -> None:
    """Load 3 months of income/expense transactions and refresh cashflow mart."""
    transactions = []
    for month, year in [("01", "2026"), ("02", "2026"), ("03", "2026")]:
        transactions += [
            {
                "booked_at": f"{year}-{month}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": f"{year}-{month}-10T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-1200.00",
                "currency": "EUR",
                "description": "rent",
            },
            {
                "booked_at": f"{year}-{month}-15T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Supermarket",
                "amount": "-400.00",
                "currency": "EUR",
                "description": "groceries",
            },
        ]
    svc.load_transactions(transactions, run_id="run-income-001")
    svc.refresh_monthly_cashflow()


class IncomeIncreaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_income_increase_positive_annual_change(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        self.assertGreater(result.annual_net_change, Decimal("0"))

    def test_income_increase_annual_change_equals_delta_times_12(self) -> None:
        delta = Decimal("500")
        result = create_income_change_scenario(
            self.store, monthly_income_delta=delta
        )
        self.assertEqual(result.annual_net_change, delta * 12)

    def test_income_increase_no_deficit(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        self.assertIsNone(result.months_until_deficit)

    def test_income_increase_new_income_equals_baseline_plus_delta(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        self.assertEqual(
            result.new_monthly_income,
            result.baseline_monthly_income + Decimal("500"),
        )


class IncomeDecreaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_income_decrease_negative_annual_change(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("-500")
        )
        self.assertLess(result.annual_net_change, Decimal("0"))

    def test_job_loss_causes_immediate_deficit(self) -> None:
        # Expense is 1600/month; full income loss (-3000) → deficit from period 1
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("-3000")
        )
        self.assertEqual(result.months_until_deficit, 1)

    def test_partial_income_loss_above_expenses_no_deficit(self) -> None:
        # Income 3000, expense 1600 — losing 1000 still leaves 2000 net
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("-1000")
        )
        self.assertIsNone(result.months_until_deficit)

    def test_income_loss_to_below_expenses_triggers_deficit(self) -> None:
        # Income 3000, expense 1600 — losing 1500 leaves 1500 which is still > expense 1600? No:
        # 3000 - 1500 = 1500 < 1600 expense → deficit
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("-1500")
        )
        self.assertEqual(result.months_until_deficit, 1)


class IncomeProjRowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_proj_cashflow_rows_written(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("200")
        )
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        self.assertIsNotNone(comparison)
        self.assertEqual(len(comparison.cashflow_rows), 12)

    def test_proj_cashflow_custom_projection_months(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("200"), projection_months=6
        )
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        self.assertEqual(len(comparison.cashflow_rows), 6)

    def test_proj_cashflow_net_delta_equals_monthly_delta(self) -> None:
        delta = Decimal("300")
        result = create_income_change_scenario(
            self.store, monthly_income_delta=delta
        )
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        for row in comparison.cashflow_rows:
            self.assertEqual(Decimal(str(row["net_delta"])), delta)

    def test_assumption_recorded(self) -> None:
        delta = Decimal("500")
        result = create_income_change_scenario(self.store, monthly_income_delta=delta)
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        assumption = next(a for a in comparison.assumptions if a["assumption_key"] == "monthly_income_delta")
        self.assertEqual(assumption["baseline_value"], "0")
        self.assertEqual(Decimal(str(assumption["override_value"])), delta)

    def test_assumption_records_delta_not_absolute_income(self) -> None:
        # Reviewer P2: assumption should store the delta (0→500), not absolute income (3000→3500)
        delta = Decimal("500")
        result = create_income_change_scenario(self.store, monthly_income_delta=delta)
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        assumption = next(a for a in comparison.assumptions if a["assumption_key"] == "monthly_income_delta")
        # baseline_value must be "0", not the baseline income amount
        self.assertEqual(assumption["baseline_value"], "0")


class IncomeScenarioArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_archive_income_scenario(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        archived = archive_scenario(self.store, result.scenario_id)
        self.assertTrue(archived)

    def test_archive_preserves_cashflow_rows(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        archive_scenario(self.store, result.scenario_id)
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        self.assertEqual(len(comparison.cashflow_rows), 12)

    def test_archive_unknown_scenario_returns_false(self) -> None:
        archived = archive_scenario(self.store, "nonexistent-id")
        self.assertFalse(archived)


class IncomeScenarioStalenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_scenario_is_not_stale_on_same_run(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        self.assertFalse(comparison.is_stale)

    def test_scenario_is_stale_after_new_transaction_run(self) -> None:
        result = create_income_change_scenario(
            self.store, monthly_income_delta=Decimal("500")
        )
        # Ingest a new run after scenario was created
        self.svc.load_transactions(
            [{
                "booked_at": "2026-04-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }],
            run_id="run-income-002",
        )
        self.svc.refresh_monthly_cashflow()
        comparison = get_income_scenario_comparison(self.store, result.scenario_id)
        self.assertTrue(comparison.is_stale)


class IncomeScenarioNoCashflowTests(unittest.TestCase):
    def test_no_cashflow_raises_value_error(self) -> None:
        store = DuckDBStore.memory()
        # Do NOT load any cashflow data
        with self.assertRaises(ValueError, msg="No cashflow data"):
            create_income_change_scenario(store, monthly_income_delta=Decimal("500"))

    def test_custom_label_stored(self) -> None:
        store = DuckDBStore.memory()
        svc = TransformationService(store)
        _load_fixture_cashflow(svc)
        result = create_income_change_scenario(
            store,
            monthly_income_delta=Decimal("-3000"),
            label="Job loss scenario",
        )
        self.assertEqual(result.label, "Job loss scenario")
