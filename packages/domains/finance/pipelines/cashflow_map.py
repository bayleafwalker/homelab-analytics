"""Cashflow map: a four-column money-flow graph for one booking month.

The map is built only from already-published reporting rows
(``mart_monthly_cashflow``, ``mart_monthly_cashflow_by_counterparty`` and
``mart_spend_by_category_monthly``). It never reads landing or transformation
state directly, so the web Cashflow Map stays on the reporting layer.

Columns, left to right::

    income sources  ->  money in  ->  regular | occasional | kept  ->  destinations

Every number is traceable to publication rows, and every modelling choice the
map makes (excluding matched transfers, grouping small payees, classifying
payees as regular) is reported back as a disclosure so the UI can say so.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Mapping, Sequence

CASHFLOW_MAP_PUBLICATIONS = (
    "mart_monthly_cashflow",
    "mart_monthly_cashflow_by_counterparty",
    "mart_spend_by_category_monthly",
)

ZERO = Decimal("0")
CENT = Decimal("0.01")
MAX_SOURCES = 5
MAX_DESTINATIONS_PER_BUCKET = 7
TREND_MONTHS = 6
REGULARITY_WINDOW = 4
REGULARITY_MIN_HITS = 3
UNCATEGORISED_LABEL = "Uncategorised"


@dataclass(frozen=True)
class _Flow:
    key: str
    label: str
    amount: Decimal
    transaction_count: int


def _dec(value: Any) -> Decimal:
    if value is None or value == "":
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT))


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isascii() and ch.isalnum() else "-" for ch in value)
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "unnamed"


def _shift_month(month: str, delta: int) -> str:
    year, mon = (int(part) for part in month.split("-", 1))
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _month_gap(older: str, newer: str) -> int:
    oy, om = (int(part) for part in older.split("-", 1))
    ny, nm = (int(part) for part in newer.split("-", 1))
    return (ny * 12 + nm) - (oy * 12 + om)


def cashflow_map_window(month: str) -> tuple[str, str]:
    """Return the (from_month, to_month) range of rows the builder needs."""
    return _shift_month(month, -(TREND_MONTHS - 1)), month


def match_internal_transfers(
    counterparty_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Pair same-month income and expense rows with identical amounts.

    Money moved between the household's own accounts shows up twice: once as
    an expense on the sending account and once as income on the receiving
    one. Counting both inflates "money in" and "money out" equally. Rows are
    paired greedily, largest first, and only when the amounts match to the
    cent and the counterparties differ. This is a heuristic, which is why the
    map reports every pair it excluded.
    """
    incomes: list[tuple[str, Decimal]] = []
    expenses: list[tuple[str, Decimal]] = []
    for row in counterparty_rows:
        name = str(row.get("counterparty_name") or "")
        income = _dec(row.get("income"))
        expense = _dec(row.get("expense"))
        if income > ZERO and expense == ZERO:
            incomes.append((name, income))
        elif expense > ZERO and income == ZERO:
            expenses.append((name, expense))
    incomes.sort(key=lambda item: item[1], reverse=True)
    expenses.sort(key=lambda item: item[1], reverse=True)
    used_expense: set[int] = set()
    pairs: list[dict[str, Any]] = []
    for income_name, income_amount in incomes:
        for index, (expense_name, expense_amount) in enumerate(expenses):
            if index in used_expense or expense_name == income_name:
                continue
            if expense_amount.quantize(CENT) == income_amount.quantize(CENT):
                used_expense.add(index)
                pairs.append(
                    {
                        "income_counterparty": income_name,
                        "expense_counterparty": expense_name,
                        "amount": income_amount,
                    }
                )
                break
    return pairs


def _group_small(
    flows: list[_Flow], limit: int, other_label: str, other_key: str
) -> tuple[list[_Flow], list[str]]:
    ordered = sorted(flows, key=lambda flow: (-flow.amount, flow.label))
    if len(ordered) <= limit:
        return ordered, []
    kept = ordered[: limit - 1]
    rest = ordered[limit - 1 :]
    grouped = _Flow(
        key=other_key,
        label=other_label.format(count=len(rest)),
        amount=sum((flow.amount for flow in rest), ZERO),
        transaction_count=sum(flow.transaction_count for flow in rest),
    )
    return [*kept, grouped], [flow.label for flow in rest]


def build_cashflow_map(
    *,
    monthly_rows: Sequence[Mapping[str, Any]],
    counterparty_rows: Sequence[Mapping[str, Any]],
    category_rows: Sequence[Mapping[str, Any]],
    month: str | None = None,
    currency: str | None = None,
    include_transfers: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    """Build the cashflow map payload for ``month`` (defaults to the latest)."""
    months_available = sorted(
        {str(row["booking_month"]) for row in monthly_rows if row.get("booking_month")}
    )
    disclosures: list[dict[str, str]] = []
    base: dict[str, Any] = {
        "month": month,
        "months_available": months_available,
        "previous_month": None,
        "next_month": None,
        "currency": currency or None,
        "include_transfers": include_transfers,
        "grouping": "counterparty",
        "totals": {
            "income": "0.00",
            "expense": "0.00",
            "net": "0.00",
            "mapped_income": "0.00",
            "mapped_expense": "0.00",
            "kept": "0.00",
            "drawn_from_savings": "0.00",
            "transfers": "0.00",
        },
        "nodes": [],
        "links": [],
        "transfers": [],
        "disclosures": disclosures,
        "provenance": {
            "publications": list(CASHFLOW_MAP_PUBLICATIONS),
            "data_through": months_available[-1] if months_available else None,
            "transaction_count": 0,
        },
    }
    if not months_available:
        disclosures.append(
            {
                "code": "no_data",
                "severity": "info",
                "message": "No account transactions have been published yet.",
            }
        )
        return base

    selected = month if month in months_available else months_available[-1]
    if month and month not in months_available:
        disclosures.append(
            {
                "code": "month_not_available",
                "severity": "info",
                "message": f"No transactions for {month}; showing {selected} instead.",
            }
        )
    base["month"] = selected
    position = months_available.index(selected)
    base["previous_month"] = months_available[position - 1] if position > 0 else None
    base["next_month"] = (
        months_available[position + 1] if position + 1 < len(months_available) else None
    )

    reference = today or date.today()
    latest = months_available[-1]
    current_month = f"{reference.year:04d}-{reference.month:02d}"
    lag = _month_gap(latest, current_month)
    if lag > 1:
        disclosures.append(
            {
                "code": "stale_data",
                "severity": "warn",
                "message": (
                    f"The newest transactions are from {latest}, {lag} months ago. "
                    "Upload a newer statement to bring the map up to date."
                ),
            }
        )

    monthly = next(row for row in monthly_rows if str(row["booking_month"]) == selected)
    total_income = _dec(monthly.get("income"))
    total_expense = _dec(monthly.get("expense"))
    month_cp_rows = [
        row for row in counterparty_rows if str(row.get("booking_month")) == selected
    ]
    month_cat_rows = [
        row for row in category_rows if str(row.get("booking_month")) == selected
    ]
    base["provenance"]["transaction_count"] = int(monthly.get("transaction_count") or 0)

    pairs = match_internal_transfers(month_cp_rows)
    transfer_total = sum((pair["amount"] for pair in pairs), ZERO)
    excluded_income: dict[str, Decimal] = defaultdict(lambda: ZERO)
    excluded_expense: dict[str, Decimal] = defaultdict(lambda: ZERO)
    if pairs and not include_transfers:
        for pair in pairs:
            excluded_income[pair["income_counterparty"]] += pair["amount"]
            excluded_expense[pair["expense_counterparty"]] += pair["amount"]
        disclosures.append(
            {
                "code": "transfers_excluded",
                "severity": "info",
                "message": (
                    f"{len(pairs)} matching in/out pair(s) totalling {_money(transfer_total)} "
                    "look like moves between your own accounts and are left out of the map."
                ),
            }
        )
    base["transfers"] = [
        {**pair, "amount": _money(pair["amount"])} for pair in pairs
    ]

    # --- income sources -------------------------------------------------
    source_flows: list[_Flow] = []
    for row in month_cp_rows:
        name = str(row.get("counterparty_name") or "Unknown payer")
        amount = _dec(row.get("income")) - excluded_income.get(name, ZERO)
        if amount > ZERO:
            source_flows.append(
                _Flow(f"in:{_slug(name)}", name, amount, int(row.get("transaction_count") or 0))
            )
    mapped_income = sum((flow.amount for flow in source_flows), ZERO)
    source_flows, other_sources = _group_small(
        source_flows, MAX_SOURCES, "Other income ({count})", "in:other"
    )

    # --- destinations ---------------------------------------------------
    has_categories = any(row.get("category") for row in category_rows)
    grouping = "category" if has_categories else "counterparty"
    base["grouping"] = grouping

    def destination_name(row: Mapping[str, Any]) -> str:
        if grouping == "category":
            return str(row.get("category") or UNCATEGORISED_LABEL)
        return str(row.get("counterparty_name") or "Unknown payee")

    # Remove matched transfers from the category rows by counterparty.
    remaining_exclusion = dict(excluded_expense)
    dest_amounts: dict[str, Decimal] = defaultdict(lambda: ZERO)
    dest_counts: dict[str, int] = defaultdict(int)
    for row in month_cat_rows:
        amount = _dec(row.get("total_expense"))
        counterparty = str(row.get("counterparty_name") or "")
        excluded = min(amount, remaining_exclusion.get(counterparty, ZERO))
        if excluded > ZERO:
            remaining_exclusion[counterparty] -= excluded
            amount -= excluded
        if amount <= ZERO:
            continue
        name = destination_name(row)
        dest_amounts[name] += amount
        dest_counts[name] += int(row.get("transaction_count") or 0)
    mapped_expense = sum(dest_amounts.values(), ZERO)

    if grouping == "counterparty":
        disclosures.append(
            {
                "code": "uncategorised",
                "severity": "info",
                "message": (
                    "Spending isn't categorised yet, so the map shows payees. "
                    "Add category rules to group them."
                ),
            }
        )
    else:
        uncategorised = dest_amounts.get(UNCATEGORISED_LABEL, ZERO)
        if uncategorised > ZERO and mapped_expense > ZERO:
            uncategorised_pct = (uncategorised / mapped_expense * 100).quantize(Decimal("1"))
            disclosures.append(
                {
                    "code": "partly_uncategorised",
                    "severity": "info",
                    "message": f"{uncategorised_pct}% of spending this month has no category.",
                }
            )

    # Regularity: a destination is regular when it had spending in at least
    # REGULARITY_MIN_HITS of the last REGULARITY_WINDOW available months.
    window_months = months_available[max(0, position - REGULARITY_WINDOW + 1) : position + 1]
    history: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    trend_months = months_available[max(0, position - TREND_MONTHS + 1) : position + 1]
    for row in category_rows:
        row_month = str(row.get("booking_month"))
        if row_month in trend_months:
            history[destination_name(row)][row_month] += _dec(row.get("total_expense"))
    can_classify = len(window_months) >= REGULARITY_WINDOW
    if not can_classify:
        disclosures.append(
            {
                "code": "short_history",
                "severity": "info",
                "message": (
                    f"Telling regular from occasional spending needs {REGULARITY_WINDOW} "
                    "months of history; all spending is shown together."
                ),
            }
        )

    def bucket_for(name: str) -> str:
        if not can_classify:
            return "spending"
        hits = sum(1 for m in window_months if history[name].get(m, ZERO) > ZERO)
        return "regular" if hits >= REGULARITY_MIN_HITS else "occasional"

    buckets: dict[str, list[_Flow]] = defaultdict(list)
    for name, amount in dest_amounts.items():
        buckets[bucket_for(name)].append(
            _Flow(f"out:{_slug(name)}", name, amount, dest_counts[name])
        )

    reconciled_expense = (total_expense - (transfer_total if pairs and not include_transfers else ZERO))
    gap = (reconciled_expense - mapped_expense).copy_abs()
    if gap > Decimal("0.05"):
        disclosures.append(
            {
                "code": "unreconciled_spending",
                "severity": "warn",
                "message": (
                    f"{_money(gap)} of spending in the monthly total has no payee "
                    "breakdown and is missing from the map."
                ),
            }
        )

    net = mapped_income - mapped_expense
    kept = net if net > ZERO else ZERO
    drawn = -net if net < ZERO else ZERO

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    inflow_total = mapped_income + drawn

    def share(amount: Decimal) -> float:
        if inflow_total <= ZERO:
            return 0.0
        return float((amount / inflow_total).quantize(Decimal("0.0001")))

    def trend_for(names: list[str]) -> list[dict[str, str]]:
        return [
            {
                "month": m,
                "amount": _money(sum((history[n].get(m, ZERO) for n in names), ZERO)),
            }
            for m in trend_months
        ]

    used_ids: set[str] = set()

    def unique_id(candidate: str) -> str:
        node_id, suffix = candidate, 2
        while node_id in used_ids:
            node_id, suffix = f"{candidate}-{suffix}", suffix + 1
        used_ids.add(node_id)
        return node_id

    def add_node(node_id: str, label: str, column: int, kind: str, amount: Decimal,
                 count: int = 0, members: list[str] | None = None,
                 trend: list[dict[str, str]] | None = None) -> str:
        node_id = unique_id(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "column": column,
                "kind": kind,
                "amount": _money(amount),
                "share": share(amount),
                "transaction_count": count,
                "members": members or [],
                "trend": trend or [],
            }
        )
        return node_id

    if inflow_total > ZERO:
        for flow in source_flows:
            source_id = add_node(flow.key, flow.label, 0, "income", flow.amount,
                                 flow.transaction_count,
                                 other_sources if flow.key == "in:other" else None)
            links.append({"source": source_id, "target": "pool", "amount": _money(flow.amount)})
        if drawn > ZERO:
            add_node("in:savings", "Drawn from savings", 0, "savings_draw", drawn)
            links.append({"source": "in:savings", "target": "pool", "amount": _money(drawn)})
        add_node("pool", "Money in", 1, "pool", inflow_total,
                 sum(flow.transaction_count for flow in source_flows))

        bucket_labels = {
            "regular": "Regular spending",
            "occasional": "Occasional spending",
            "spending": "Spending",
        }
        for bucket_key in ("regular", "occasional", "spending"):
            flows = buckets.get(bucket_key)
            if not flows:
                continue
            bucket_total = sum((flow.amount for flow in flows), ZERO)
            bucket_id = f"bucket:{bucket_key}"
            add_node(bucket_id, bucket_labels[bucket_key], 2, bucket_key, bucket_total,
                     sum(flow.transaction_count for flow in flows))
            links.append({"source": "pool", "target": bucket_id, "amount": _money(bucket_total)})
            grouped, other_members = _group_small(
                flows,
                MAX_DESTINATIONS_PER_BUCKET,
                "Everything else ({count})",
                f"out:other-{bucket_key}",
            )
            for flow in grouped:
                members = other_members if flow.key.startswith("out:other-") else None
                trend_names = members if members else [flow.label]
                dest_id = add_node(flow.key, flow.label, 3, grouping, flow.amount,
                                   flow.transaction_count, members, trend_for(trend_names))
                links.append({"source": bucket_id, "target": dest_id, "amount": _money(flow.amount)})
        if kept > ZERO:
            add_node("bucket:kept", "Kept", 2, "kept", kept)
            links.append({"source": "pool", "target": "bucket:kept", "amount": _money(kept)})

    base["nodes"] = nodes
    base["links"] = links
    base["totals"] = {
        "income": _money(total_income),
        "expense": _money(total_expense),
        "net": _money(total_income - total_expense),
        "mapped_income": _money(mapped_income),
        "mapped_expense": _money(mapped_expense),
        "kept": _money(kept),
        "drawn_from_savings": _money(drawn),
        "transfers": _money(transfer_total),
    }
    return base
