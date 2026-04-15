"""Cross-domain scenario result types owned by the overview composition layer."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from packages.platform.source_freshness import SourceFreshnessSummary

__all__ = [
    "HomelabCostBenefitComparison",
    "HomelabCostBenefitResult",
    "TariffShockResult",
]


@dataclass
class TariffShockResult:
    scenario_id: str
    label: str
    tariff_pct_delta: Decimal
    baseline_monthly_utility_cost: Decimal
    new_monthly_utility_cost: Decimal
    annual_additional_cost: Decimal
    months_until_deficit: int | None
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class HomelabCostBenefitComparison:
    scenario_id: str
    label: str
    assumptions: list[dict[str, Any]]
    summary_rows: list[dict[str, Any]]
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None


@dataclass
class HomelabCostBenefitResult:
    scenario_id: str
    label: str
    monthly_cost_delta: Decimal
    baseline_monthly_cost: Decimal
    new_monthly_cost: Decimal
    annual_cost_delta: Decimal
    is_stale: bool
    assumptions_summary: list[SourceFreshnessSummary] | None = None
