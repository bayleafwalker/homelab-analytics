"""Compose the Operating Picture cards from published reporting facts."""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

import duckdb
import psycopg

from packages.pipelines.reporting_currency import StaleReportingSchemaError
from packages.pipelines.reporting_service import ReportingService
from packages.platform.capability_types import CapabilityPack

Domain = Literal["finance", "utilities", "homelab"]
MetricState = Literal["available", "empty", "unavailable"]
TrendState = Literal["available", "insufficient_history", "unavailable"]
_DOMAINS: tuple[Domain, ...] = ("finance", "utilities", "homelab")
_UNHEALTHY = {"degraded", "stopped"}
_KNOWN = {"running", *_UNHEALTHY}
_CRITICALITY = {"critical": 3, "standard": 2, "background": 1}
_KNOWN_PRIORITIES = {1, 2, 3}
_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DomainPoint:
    period: str
    value: str | int
    unit: str
    run_id: str | None = None
    known_count: int | None = None


@dataclass(frozen=True)
class DomainAttention:
    key: str
    label: str
    priority: int | None
    href: str


@dataclass
class DomainCard:
    domain_key: Domain
    metric_state: MetricState = "unavailable"
    trend_state: TrendState = "unavailable"
    attention_state: MetricState = "unavailable"
    headline: list[DomainPoint] = field(default_factory=list)
    trend: list[DomainPoint] = field(default_factory=list)
    attention: DomainAttention | None = None


def compose_domain_cards(
    packs: Sequence[CapabilityPack], reporting: ReportingService | None
) -> list[DomainCard]:
    """Read each publication independently so failure does not look like emptiness."""
    source_owners = {pack.name for pack in packs if pack.sources}
    cards = [DomainCard(domain) for domain in _DOMAINS if domain in source_owners]
    if reporting is None:
        return cards
    money_attention = (
        _read(reporting.get_open_attention_items)
        if source_owners.intersection({"finance", "utilities"})
        else None
    )
    for card in cards:
        if card.domain_key == "homelab":
            _homelab_card(
                card,
                _read(reporting.get_service_health_current),
                _read(reporting.get_service_health_history),
            )
            continue
        if card.domain_key == "finance":
            _monetary_card(card, _read(reporting.get_monthly_cashflow), "booking_month", "net")
        else:
            _monetary_card(
                card, _read(reporting.get_utility_cost_trend_monthly), "billing_month", "total_cost"
            )
        if money_attention is not None:
            _assign_attention(
                card,
                [
                    DomainAttention(
                        str(row["item_id"]),
                        str(row["title"]),
                        row["severity"] if row["severity"] in _KNOWN_PRIORITIES else None,
                        "/review",
                    )
                    for row in money_attention
                    if row["source_domain"] == card.domain_key
                ],
            )
    return cards


def _read(reader: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]] | None:
    try:
        return reader()
    except (KeyError, OSError, duckdb.Error, psycopg.Error, StaleReportingSchemaError):
        _log.warning("Domain card publication unavailable for %s", reader.__name__, exc_info=True)
        return None


def _monetary_card(
    card: DomainCard, rows: list[dict[str, Any]] | None, period_key: str, value_key: str
) -> None:
    if rows is None:
        return
    groups: dict[str, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        unit = row["currency"]
        # In Utilities, NULL represents observed usage without a bill. It is
        # not money. A zero-valued actual bill retains its recorded currency.
        if not unit:
            continue
        period = str(row[period_key])
        amounts = groups[str(unit)]
        amounts[period] = amounts.get(period, Decimal(0)) + Decimal(str(row[value_key]))
    for unit, periods in sorted(groups.items()):
        points = [DomainPoint(period, str(value), unit) for period, value in sorted(periods.items())]
        card.headline.append(points[-1])
        if len(points) > 1:
            card.trend.extend(points)
    card.trend.sort(key=lambda point: (point.period, point.unit))
    card.metric_state = "available" if card.headline else "empty"
    card.trend_state = "available" if card.trend else "insufficient_history"


def _homelab_card(
    card: DomainCard,
    current: list[dict[str, Any]] | None,
    history: list[dict[str, Any]] | None,
) -> None:
    if current is not None:
        known = [row for row in current if row["state"] in _KNOWN]
        if not current:
            card.metric_state = "empty"
            card.attention_state = "empty"
        elif known:
            unhealthy = [row for row in known if row["state"] in _UNHEALTHY]
            card.metric_state = "available"
            card.headline = [
                DomainPoint(
                    max(_utc_period(row["recorded_at"]) for row in known),
                    len(unhealthy), "services", known_count=len(known),
                )
            ]
            _assign_attention(
                card,
                [
                    DomainAttention(
                        str(row["service_id"]),
                        f"{row['service_name'] or row['service_id']}: {row['state']}",
                        _CRITICALITY.get(row["criticality"]),
                        "/homelab",
                    )
                    for row in unhealthy
                ],
            )
    if history is None:
        return
    batches: dict[tuple[str, str], dict[str, str]] = defaultdict(dict)
    for row in history:
        batch = (_utc_period(row["recorded_at"]), str(row["run_id"]))
        batches[batch][str(row["service_id"])] = str(row["state"])
    if not batches:
        card.trend_state = "insufficient_history"
        return

    latest = batches[max(batches)]
    if not any(state in _KNOWN for state in latest.values()):
        return
    card.trend_state = "insufficient_history"
    if not all(state in _KNOWN for state in latest.values()):
        return

    points: list[DomainPoint] = []
    for (period, run_id), observations in sorted(batches.items()):
        if observations.keys() == latest.keys() and all(state in _KNOWN for state in observations.values()):
            unhealthy_count = sum(state in _UNHEALTHY for state in observations.values())
            point = DomainPoint(period, unhealthy_count, "services", run_id, len(observations))
            # Multiple runs may carry the same recorded observation time.
            # Keep one deterministic batch at that instant, not a time delta of zero.
            if points and points[-1].period == period:
                points[-1] = point
            else:
                points.append(point)
    if len(points) > 1:
        card.trend_state = "available"
        card.trend = points


def _assign_attention(card: DomainCard, candidates: list[DomainAttention]) -> None:
    card.attention_state = "available" if candidates else "empty"
    if candidates:
        card.attention = min(
            candidates, key=lambda item: (
                item.priority is None,
                -(item.priority or 0),
                item.key,
                item.label,
            ),
        )


def _utc_period(value: datetime) -> str:
    utc = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
