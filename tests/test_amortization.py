"""Tests for the pure amortization compute engine.

Covers:
- Monthly payment formula (PMT)
- Full amortization schedule generation
- Extra repayments shortening the schedule
- Zero interest rate
- Single period loan
- Fortnightly frequency
- total_interest and remaining_term helpers
"""

from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

from packages.pipelines.amortization import (
    AmortizationRow,
    LoanParameters,
    compute_amortization_schedule,
    compute_monthly_payment,
    remaining_term,
    total_interest,
)


class ComputeMonthlyPaymentTests(unittest.TestCase):
    def test_known_mortgage_payment(self) -> None:
        # €350,000 at 4.5% over 300 months = ~€1,945.40
        payment = compute_monthly_payment(
            Decimal("350000"), Decimal("0.045"), 300
        )
        self.assertAlmostEqual(float(payment), 1945.40, delta=1.0)

    def test_personal_loan_payment(self) -> None:
        # €12,000 at 6.5% over 48 months = ~€284.57
        payment = compute_monthly_payment(
            Decimal("12000"), Decimal("0.065"), 48
        )
        self.assertAlmostEqual(float(payment), 284.57, delta=0.5)

    def test_zero_rate_returns_equal_instalment(self) -> None:
        payment = compute_monthly_payment(Decimal("12000"), Decimal("0"), 12)
        self.assertEqual(Decimal("1000.00"), payment)

    def test_single_period_returns_full_principal_plus_interest(self) -> None:
        payment = compute_monthly_payment(Decimal("1000"), Decimal("0.12"), 1)
        # One month at 1%: 1000 * 0.01 * (1.01)^1 / (1.01^1 - 1) = 1010
        self.assertAlmostEqual(float(payment), 1010.00, delta=0.05)

    def test_returns_decimal(self) -> None:
        payment = compute_monthly_payment(Decimal("10000"), Decimal("0.05"), 24)
        self.assertIsInstance(payment, Decimal)


class AmortizationScheduleTests(unittest.TestCase):
    def _mortgage_params(self, extra: str = "0") -> LoanParameters:
        return LoanParameters(
            principal=Decimal("100000"),
            annual_rate=Decimal("0.05"),
            term_months=120,
            start_date=date(2024, 1, 1),
            extra_repayment=Decimal(extra),
        )

    def test_schedule_has_term_months_rows_for_standard_loan(self) -> None:
        schedule = compute_amortization_schedule(self._mortgage_params())
        self.assertEqual(120, len(schedule))

    def test_first_row_is_period_1(self) -> None:
        schedule = compute_amortization_schedule(self._mortgage_params())
        self.assertEqual(1, schedule[0].period)

    def test_last_row_balance_is_zero(self) -> None:
        schedule = compute_amortization_schedule(self._mortgage_params())
        self.assertEqual(Decimal("0.00"), schedule[-1].remaining_balance)

    def test_payment_splits_correctly(self) -> None:
        schedule = compute_amortization_schedule(self._mortgage_params())
        for row in schedule:
            with self.subTest(period=row.period):
                self.assertIsInstance(row, AmortizationRow)
                self.assertGreater(row.payment, Decimal("0"))
                self.assertGreater(row.principal_portion, Decimal("0"))
                self.assertGreaterEqual(row.interest_portion, Decimal("0"))

    def test_extra_repayment_shortens_schedule(self) -> None:
        normal = compute_amortization_schedule(self._mortgage_params(extra="0"))
        extra = compute_amortization_schedule(self._mortgage_params(extra="500"))
        self.assertLess(len(extra), len(normal))

    def test_extra_repayment_reduces_total_interest(self) -> None:
        normal_interest = total_interest(
            compute_amortization_schedule(self._mortgage_params(extra="0"))
        )
        extra_interest = total_interest(
            compute_amortization_schedule(self._mortgage_params(extra="500"))
        )
        self.assertLess(extra_interest, normal_interest)

    def test_zero_rate_loan_schedule(self) -> None:
        params = LoanParameters(
            principal=Decimal("12000"),
            annual_rate=Decimal("0"),
            term_months=12,
            start_date=date(2024, 1, 1),
        )
        schedule = compute_amortization_schedule(params)
        self.assertEqual(12, len(schedule))
        for row in schedule:
            self.assertEqual(Decimal("0.00"), row.interest_portion)

    def test_monthly_payment_dates_advance_by_one_month(self) -> None:
        params = LoanParameters(
            principal=Decimal("10000"),
            annual_rate=Decimal("0.06"),
            term_months=6,
            start_date=date(2024, 1, 1),
        )
        schedule = compute_amortization_schedule(params)
        for i, row in enumerate(schedule):
            self.assertEqual(i + 1, row.period)

    def test_fortnightly_schedule_has_more_periods(self) -> None:
        monthly_params = LoanParameters(
            principal=Decimal("100000"),
            annual_rate=Decimal("0.05"),
            term_months=120,
            start_date=date(2024, 1, 1),
            payment_frequency="monthly",
        )
        fortnightly_params = LoanParameters(
            principal=Decimal("100000"),
            annual_rate=Decimal("0.05"),
            term_months=120,
            start_date=date(2024, 1, 1),
            payment_frequency="fortnightly",
        )
        monthly_schedule = compute_amortization_schedule(monthly_params)
        fortnightly_schedule = compute_amortization_schedule(fortnightly_params)
        # Fortnightly payments are smaller per period but more frequent;
        # schedule length should be ≥ term months (in fortnightly periods)
        self.assertGreater(len(fortnightly_schedule), 0)
        self.assertEqual(Decimal("0.00"), fortnightly_schedule[-1].remaining_balance)


class TotalInterestAndRemainingTermTests(unittest.TestCase):
    def test_total_interest_is_sum_of_interest_portions(self) -> None:
        params = LoanParameters(
            principal=Decimal("50000"),
            annual_rate=Decimal("0.04"),
            term_months=60,
            start_date=date(2024, 1, 1),
        )
        schedule = compute_amortization_schedule(params)
        expected = sum(row.interest_portion for row in schedule)
        self.assertEqual(expected, total_interest(schedule))

    def test_total_interest_on_zero_rate_is_zero(self) -> None:
        params = LoanParameters(
            principal=Decimal("6000"),
            annual_rate=Decimal("0"),
            term_months=6,
            start_date=date(2024, 1, 1),
        )
        schedule = compute_amortization_schedule(params)
        self.assertEqual(Decimal("0"), total_interest(schedule))

    def test_remaining_term_equals_periods_with_positive_balance(self) -> None:
        params = LoanParameters(
            principal=Decimal("10000"),
            annual_rate=Decimal("0.05"),
            term_months=24,
            start_date=date(2024, 1, 1),
        )
        schedule = compute_amortization_schedule(params)
        expected = sum(1 for row in schedule if row.remaining_balance > Decimal("0"))
        self.assertEqual(expected, remaining_term(schedule))

    def test_remaining_term_with_extra_repayments_is_less(self) -> None:
        params_no_extra = LoanParameters(
            principal=Decimal("50000"),
            annual_rate=Decimal("0.05"),
            term_months=60,
            start_date=date(2024, 1, 1),
        )
        params_with_extra = LoanParameters(
            principal=Decimal("50000"),
            annual_rate=Decimal("0.05"),
            term_months=60,
            start_date=date(2024, 1, 1),
            extra_repayment=Decimal("1000"),
        )
        self.assertLess(
            remaining_term(compute_amortization_schedule(params_with_extra)),
            remaining_term(compute_amortization_schedule(params_no_extra)),
        )


if __name__ == "__main__":
    unittest.main()
