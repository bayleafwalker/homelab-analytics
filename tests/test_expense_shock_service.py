"""Tests for expense shock scenarios — create, compare, archive.

Covers:
- create_expense_shock_scenario: increase, decrease, projection rows
- get_expense_shock_comparison: cashflow rows, assumptions
- archive_scenario: reuses shared archive function
- edge cases: no cashflow data raises ValueError, staleness detection
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from packages.domains.finance.pipelines.scenario_service import (
    archive_scenario,
    create_expense_shock_scenario,
    get_expense_shock_comparison,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _load_fixture_cashflow(svc: TransformationService) -> None:
    """Load 3 months of income/expense transactions and refresh cashflow mart."""
    transactions = []
    for month in ["01", "02", "03"]:
        transactions += [
            {
                "booked_at": f"2026-{month}-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            },
            {
                "booked_at": f"2026-{month}-10T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Landlord",
                "amount": "-1200.00",
                "currency": "EUR",
                "description": "rent",
            },
            {
                "booked_at": f"2026-{month}-15T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Supermarket",
                "amount": "-400.00",
                "currency": "EUR",
                "description": "groceries",
            },
        ]
    # Baseline: income=3000, expense=1600, net=1400 per month
    svc.load_transactions(transactions, run_id="run-shock-001")
    svc.refresh_monthly_cashflow()


class ExpenseIncreaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_expense_increase_raises_new_monthly_expense(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        self.assertGreater(result.new_monthly_expense, result.baseline_monthly_expense)

    def test_expense_increase_annual_additional_cost_positive(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        self.assertGreater(result.annual_additional_cost, Decimal("0"))

    def test_annual_additional_cost_equals_monthly_delta_times_12(self) -> None:
        pct = Decimal("0.10")
        result = create_expense_shock_scenario(self.store, expense_pct_delta=pct)
        expected = (result.new_monthly_expense - result.baseline_monthly_expense) * 12
        self.assertAlmostEqual(
            float(result.annual_additional_cost), float(expected), places=2
        )

    def test_10pct_shock_no_deficit_when_income_covers_new_expense(self) -> None:
        # Baseline: income=3000, expense=1600. 10% shock → expense=1760, net=1240 — still positive
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        self.assertIsNone(result.months_until_deficit)

    def test_large_shock_causes_deficit(self) -> None:
        # Baseline: income=3000, expense=1600. 100% shock → expense=3200, net=-200 → deficit period 1
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("1.0")
        )
        self.assertEqual(result.months_until_deficit, 1)

    def test_shock_just_above_income_causes_deficit(self) -> None:
        # income=3000, expense=1600. Need expense > 3000 → pct > 87.5%.
        # 90% shock: expense = 1600 * 1.9 = 3040 > 3000 → deficit
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.90")
        )
        self.assertEqual(result.months_until_deficit, 1)


class ExpenseDecreaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_expense_decrease_lowers_new_monthly_expense(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("-0.10")
        )
        self.assertLess(result.new_monthly_expense, result.baseline_monthly_expense)

    def test_expense_decrease_annual_cost_negative(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("-0.10")
        )
        self.assertLess(result.annual_additional_cost, Decimal("0"))

    def test_expense_decrease_no_deficit(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("-0.50")
        )
        self.assertIsNone(result.months_until_deficit)


class ExpenseProjRowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_proj_cashflow_rows_written_default_12(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        self.assertIsNotNone(comparison)
        self.assertEqual(len(comparison.cashflow_rows), 12)

    def test_proj_cashflow_custom_projection_months(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10"), projection_months=6
        )
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        self.assertEqual(len(comparison.cashflow_rows), 6)

    def test_net_delta_equals_negative_expense_increase_per_period(self) -> None:
        pct = Decimal("0.10")
        result = create_expense_shock_scenario(self.store, expense_pct_delta=pct)
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        expected_delta = -(result.new_monthly_expense - result.baseline_monthly_expense)
        for row in comparison.cashflow_rows:
            self.assertAlmostEqual(float(row["net_delta"]), float(expected_delta), places=2)

    def test_scenario_income_unchanged_from_baseline(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.20")
        )
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        for row in comparison.cashflow_rows:
            self.assertAlmostEqual(
                float(row["scenario_income"]), float(row["baseline_income"]), places=2
            )

    def test_assumption_recorded_with_correct_key(self) -> None:
        pct = Decimal("0.10")
        result = create_expense_shock_scenario(self.store, expense_pct_delta=pct)
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        assumption = next(a for a in comparison.assumptions if a["assumption_key"] == "expense_pct_delta")
        self.assertEqual(assumption["baseline_value"], "0")
        self.assertAlmostEqual(float(assumption["override_value"]), float(pct), places=4)

    def test_custom_label_stored(self) -> None:
        result = create_expense_shock_scenario(
            self.store,
            expense_pct_delta=Decimal("0.15"),
            label="Tariff shock 2026",
        )
        self.assertEqual(result.label, "Tariff shock 2026")

    def test_auto_label_includes_percentage(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        self.assertIn("10.0", result.label)


class ExpenseShockArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_archive_expense_shock_scenario(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        archived = archive_scenario(self.store, result.scenario_id)
        self.assertTrue(archived)

    def test_archive_preserves_cashflow_rows(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        archive_scenario(self.store, result.scenario_id)
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        self.assertEqual(len(comparison.cashflow_rows), 12)


class ExpenseShockStalenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_cashflow(self.svc)

    def test_scenario_not_stale_on_same_run(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        self.assertFalse(comparison.is_stale)

    def test_scenario_stale_after_new_transaction_run(self) -> None:
        result = create_expense_shock_scenario(
            self.store, expense_pct_delta=Decimal("0.10")
        )
        self.svc.load_transactions(
            [{
                "booked_at": "2026-04-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }],
            run_id="run-shock-002",
        )
        self.svc.refresh_monthly_cashflow()
        comparison = get_expense_shock_comparison(self.store, result.scenario_id)
        self.assertTrue(comparison.is_stale)


class ExpenseShockNoCashflowTests(unittest.TestCase):
    def test_no_cashflow_raises_value_error(self) -> None:
        store = DuckDBStore.memory()
        with self.assertRaises(ValueError):
            create_expense_shock_scenario(store, expense_pct_delta=Decimal("0.10"))
