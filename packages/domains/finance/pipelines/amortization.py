"""Pure loan amortization compute engine.

Zero dependencies on DuckDB, store, or external libraries.
All arithmetic uses Decimal for precision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class LoanParameters:
    principal: Decimal
    annual_rate: Decimal          # e.g. Decimal("0.035") for 3.5%
    term_months: int
    start_date: date
    payment_frequency: str = "monthly"  # monthly | fortnightly | weekly
    extra_repayment: Decimal = Decimal("0")


@dataclass(frozen=True)
class AmortizationRow:
    period: int
    payment_date: date
    payment: Decimal
    principal_portion: Decimal
    interest_portion: Decimal
    extra_repayment: Decimal
    remaining_balance: Decimal


_CENT = Decimal("0.01")
_FOUR = Decimal("0.0001")


def compute_monthly_payment(
    principal: Decimal,
    annual_rate: Decimal,
    term_months: int,
) -> Decimal:
    """Standard PMT formula for monthly payments.

    Returns the fixed monthly payment amount.
    For zero-rate loans returns a simple equal instalment.
    """
    if annual_rate == Decimal("0"):
        return (principal / term_months).quantize(_CENT, rounding=ROUND_HALF_UP)

    monthly_rate = annual_rate / 12
    factor = (1 + monthly_rate) ** term_months
    payment = principal * monthly_rate * factor / (factor - 1)
    return payment.quantize(_CENT, rounding=ROUND_HALF_UP)


def _next_payment_date(current: date, frequency: str, period: int) -> date:
    """Advance date by one payment interval from the start date."""
    from datetime import timedelta

    if frequency == "monthly":
        # Add period months to start_date
        month = current.month + period
        year = current.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(current.day, _days_in_month(year, month))
        return date(year, month, day)
    if frequency == "fortnightly":
        return current + timedelta(weeks=2 * period)
    if frequency == "weekly":
        return current + timedelta(weeks=period)
    # default monthly
    month = current.month + period
    year = current.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(current.day, _days_in_month(year, month))
    return date(year, month, day)


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


def compute_amortization_schedule(params: LoanParameters) -> list[AmortizationRow]:
    """Compute a full reducing-balance amortization schedule.

    Handles optional extra repayments which reduce the outstanding balance.
    The schedule terminates when the balance reaches zero (which may be
    before ``term_months`` if extra repayments are applied).
    """
    if params.payment_frequency == "monthly":
        rate_per_period = params.annual_rate / 12
        base_payment = compute_monthly_payment(
            params.principal, params.annual_rate, params.term_months
        )
    elif params.payment_frequency == "fortnightly":
        rate_per_period = params.annual_rate / 26
        # Fortnightly: equivalent fortnightly payment from monthly
        monthly_payment = compute_monthly_payment(
            params.principal, params.annual_rate, params.term_months
        )
        base_payment = (monthly_payment * 12 / 26).quantize(_CENT, rounding=ROUND_HALF_UP)
    elif params.payment_frequency == "weekly":
        rate_per_period = params.annual_rate / 52
        monthly_payment = compute_monthly_payment(
            params.principal, params.annual_rate, params.term_months
        )
        base_payment = (monthly_payment * 12 / 52).quantize(_CENT, rounding=ROUND_HALF_UP)
    else:
        rate_per_period = params.annual_rate / 12
        base_payment = compute_monthly_payment(
            params.principal, params.annual_rate, params.term_months
        )

    balance = params.principal
    schedule: list[AmortizationRow] = []

    for period in range(1, params.term_months * 10):  # upper bound safety
        if balance <= Decimal("0"):
            break

        interest = (balance * rate_per_period).quantize(_CENT, rounding=ROUND_HALF_UP)
        # Clamp payment to remaining balance + interest on last period
        payment = min(base_payment, balance + interest)
        principal_portion = (payment - interest).quantize(_CENT, rounding=ROUND_HALF_UP)
        extra = min(params.extra_repayment, balance - principal_portion)
        extra = max(extra, Decimal("0"))

        new_balance = (balance - principal_portion - extra).quantize(
            _CENT, rounding=ROUND_HALF_UP
        )

        schedule.append(
            AmortizationRow(
                period=period,
                payment_date=_next_payment_date(params.start_date, params.payment_frequency, period),
                payment=payment,
                principal_portion=principal_portion,
                interest_portion=interest,
                extra_repayment=extra,
                remaining_balance=max(new_balance, Decimal("0")),
            )
        )

        balance = new_balance
        if balance <= Decimal("0"):
            break

    return schedule


def total_interest(schedule: list[AmortizationRow]) -> Decimal:
    """Sum of all interest portions in the schedule."""
    return sum((row.interest_portion for row in schedule), Decimal("0"))


def remaining_term(schedule: list[AmortizationRow]) -> int:
    """Number of periods where balance > 0 after applying the schedule."""
    return sum(1 for row in schedule if row.remaining_balance > Decimal("0"))
