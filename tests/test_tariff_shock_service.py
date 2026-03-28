"""Tests for tariff shock scenarios.

Covers:
- create_tariff_shock_scenario: tariff increase/decrease and projection rows
- get_tariff_shock_comparison: assumptions, cashflow rows, staleness
- edge cases: no utility trend data raises ValueError
"""
from __future__ import annotations

import unittest
from decimal import Decimal

from packages.pipelines.scenario_service import (
    create_tariff_shock_scenario,
    get_tariff_shock_comparison,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

UTILITY_BILL_ROWS = [
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "provider": "City Power",
        "utility_type": "electricity",
        "location": "home",
        "billing_period_start": "2026-01-01",
        "billing_period_end": "2026-01-31",
        "billed_amount": "95.00",
        "currency": "EUR",
        "billed_quantity": "350",
        "usage_unit": "kWh",
        "invoice_date": "2026-02-05",
    },
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "provider": "City Power",
        "utility_type": "electricity",
        "location": "home",
        "billing_period_start": "2026-02-01",
        "billing_period_end": "2026-02-28",
        "billed_amount": "88.00",
        "currency": "EUR",
        "billed_quantity": "310",
        "usage_unit": "kWh",
        "invoice_date": "2026-03-05",
    },
]

UTILITY_USAGE_ROWS = [
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "utility_type": "electricity",
        "location": "home",
        "usage_start": "2026-01-01",
        "usage_end": "2026-01-31",
        "usage_quantity": "350",
        "usage_unit": "kWh",
        "reading_source": "smart-meter",
    },
    {
        "meter_id": "elec-001",
        "meter_name": "Main Meter",
        "utility_type": "electricity",
        "location": "home",
        "usage_start": "2026-02-01",
        "usage_end": "2026-02-28",
        "usage_quantity": "310",
        "usage_unit": "kWh",
        "reading_source": "smart-meter",
    },
]


def _load_fixture_data(svc: TransformationService) -> None:
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
    svc.load_transactions(transactions, run_id="run-tariff-001")
    svc.refresh_monthly_cashflow()

    svc.load_bills(UTILITY_BILL_ROWS, run_id="run-bill-001")
    svc.load_utility_usage(UTILITY_USAGE_ROWS, run_id="run-usage-001")
    svc.refresh_utility_cost_summary()
    svc.refresh_utility_cost_trend_monthly()


class TariffShockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_data(self.svc)

    def test_tariff_increase_raises_new_monthly_utility_cost(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        self.assertGreater(
            result.new_monthly_utility_cost, result.baseline_monthly_utility_cost
        )

    def test_tariff_decrease_lowers_new_monthly_utility_cost(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("-0.10")
        )
        self.assertLess(
            result.new_monthly_utility_cost, result.baseline_monthly_utility_cost
        )

    def test_annual_additional_cost_matches_monthly_delta_times_12(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        expected = (result.new_monthly_utility_cost - result.baseline_monthly_utility_cost) * 12
        self.assertAlmostEqual(
            float(result.annual_additional_cost), float(expected), places=2
        )


class TariffShockProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = DuckDBStore.memory()
        self.svc = TransformationService(self.store)
        _load_fixture_data(self.svc)

    def test_proj_cashflow_rows_written_default_12(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        comparison = get_tariff_shock_comparison(self.store, result.scenario_id)
        self.assertIsNotNone(comparison)
        self.assertEqual(len(comparison.cashflow_rows), 12)

    def test_custom_label_stored(self) -> None:
        result = create_tariff_shock_scenario(
            self.store,
            tariff_pct_delta=Decimal("0.15"),
            label="Electricity tariff shock 2026",
        )
        self.assertEqual(result.label, "Electricity tariff shock 2026")

    def test_auto_label_includes_percentage_and_utility(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        self.assertIn("10.0", result.label)
        self.assertIn("electricity", result.label)

    def test_assumptions_recorded_with_tariff_keys(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        comparison = get_tariff_shock_comparison(self.store, result.scenario_id)
        assumption_keys = {a["assumption_key"] for a in comparison.assumptions}
        self.assertIn("tariff_pct_delta", assumption_keys)
        self.assertIn("baseline_utility_cost", assumption_keys)

    def test_scenario_stale_after_new_utility_run(self) -> None:
        result = create_tariff_shock_scenario(
            self.store, tariff_pct_delta=Decimal("0.10")
        )
        self.svc.load_bills(
            [
                {
                    "meter_id": "elec-001",
                    "meter_name": "Main Meter",
                    "provider": "City Power",
                    "utility_type": "electricity",
                    "location": "home",
                    "billing_period_start": "2026-03-01",
                    "billing_period_end": "2026-03-31",
                    "billed_amount": "110.00",
                    "currency": "EUR",
                    "billed_quantity": "355",
                    "usage_unit": "kWh",
                    "invoice_date": "2026-04-05",
                }
            ],
            run_id="run-bill-002",
        )
        self.svc.load_utility_usage(
            [
                {
                    "meter_id": "elec-001",
                    "meter_name": "Main Meter",
                    "utility_type": "electricity",
                    "location": "home",
                    "usage_start": "2026-03-01",
                    "usage_end": "2026-03-31",
                    "usage_quantity": "355",
                    "usage_unit": "kWh",
                    "reading_source": "smart-meter",
                }
            ],
            run_id="run-usage-002",
        )
        self.svc.refresh_utility_cost_summary()
        self.svc.refresh_utility_cost_trend_monthly()

        comparison = get_tariff_shock_comparison(self.store, result.scenario_id)
        self.assertTrue(comparison.is_stale)


class TariffShockNoUtilityTests(unittest.TestCase):
    def test_no_utility_trend_raises_value_error(self) -> None:
        store = DuckDBStore.memory()
        svc = TransformationService(store)
        transactions = [
            {
                "booked_at": "2026-01-03T08:00:00+00:00",
                "account_id": "checking",
                "counterparty_name": "Employer",
                "amount": "3000.00",
                "currency": "EUR",
                "description": "salary",
            }
        ]
        svc.load_transactions(transactions, run_id="run-no-utility-001")
        svc.refresh_monthly_cashflow()
        with self.assertRaises(ValueError):
            create_tariff_shock_scenario(store, tariff_pct_delta=Decimal("0.10"))
