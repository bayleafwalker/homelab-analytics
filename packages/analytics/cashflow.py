from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from packages.pipelines.account_transactions import CanonicalTransaction


@dataclass(frozen=True)
class MonthlyCashflowSummary:
    booking_month: str
    income: Decimal
    expense: Decimal
    net: Decimal
    transaction_count: int


def summarize_monthly_cashflow(
    transactions: list[CanonicalTransaction],
) -> list[MonthlyCashflowSummary]:
    grouped: dict[str, dict[str, Decimal | int]] = {}

    for transaction in transactions:
        month_bucket = grouped.setdefault(
            transaction.booking_month,
            {
                "income": Decimal("0"),
                "expense": Decimal("0"),
                "net": Decimal("0"),
                "transaction_count": 0,
            },
        )
        if transaction.amount >= 0:
            month_bucket["income"] += transaction.amount
        else:
            month_bucket["expense"] += abs(transaction.amount)
        month_bucket["net"] += transaction.amount
        month_bucket["transaction_count"] += 1

    return [
        MonthlyCashflowSummary(
            booking_month=booking_month,
            income=values["income"],
            expense=values["expense"],
            net=values["net"],
            transaction_count=values["transaction_count"],
        )
        for booking_month, values in sorted(grouped.items())
    ]
