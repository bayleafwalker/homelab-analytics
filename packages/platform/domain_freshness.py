"""Domain grouping and aggregation for publication confidence and source freshness.

The dashboard groups publications and source assets by household domain
(finance, utilities, homelab, overview, ...). This module owns that mapping and
the worst-case aggregation over a set of rows so routes stay presentation-only.

Severity order for verdicts (worst last):
``trustworthy < degraded < unreliable < unavailable``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from packages.platform.publication_confidence import FreshnessState

_VERDICT_SEVERITY = {
    "trustworthy": 1,
    "degraded": 2,
    "unreliable": 3,
    "unavailable": 4,
}

_UTILITIES_TOKENS = ("utility", "contract_price")
_HOMELAB_TOKENS = ("homelab", "infrastructure", "home_automation")
_FINANCE_TOKENS = (
    "account",
    "asset",
    "balance",
    "budget",
    "cashflow",
    "contract",
    "finance",
    "loan",
    "subscription",
    "transaction",
)


def domain_for_package(transformation_package_id: str | None) -> str:
    """Return a dashboard domain label from a transformation package id.

    ``None`` or an empty id means the row is not tied to a household domain and
    reports as ``platform``. Unknown package ids fall back to the id without
    the ``builtin_`` prefix and with underscores rendered as spaces.
    """
    if not transformation_package_id:
        return "platform"
    package_id = transformation_package_id.lower()
    if any(token in package_id for token in _UTILITIES_TOKENS):
        return "utilities"
    if any(token in package_id for token in _HOMELAB_TOKENS):
        return "homelab"
    if "overview" in package_id:
        return "overview"
    if any(token in package_id for token in _FINANCE_TOKENS):
        return "finance"
    return transformation_package_id.removeprefix("builtin_").replace("_", " ")


def worst_case_verdict(verdict1: str, verdict2: str) -> str:
    """Return the worse of two verdicts, preserving the winning spelling."""
    normalized_1 = verdict1.lower()
    normalized_2 = verdict2.lower()
    return (
        verdict1
        if _VERDICT_SEVERITY.get(normalized_1, 0)
        >= _VERDICT_SEVERITY.get(normalized_2, 0)
        else verdict2
    )


def is_stale_publication(freshness_state: str) -> bool:
    """Whether a publication freshness state means the data is held back."""
    return freshness_state.lower() in {
        str(FreshnessState.STALE),
        str(FreshnessState.UNAVAILABLE),
    }


def summarize_domains(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate publication confidence rows into one summary per domain.

    Each row must carry ``domain``, ``confidence_verdict`` and
    ``freshness_state``. Summaries are ordered by domain and report the worst
    verdict in the domain, the row count, the count that is not trustworthy,
    and the count that is stale or unavailable.
    """
    summaries: dict[str, dict[str, Any]] = {}
    for row in rows:
        domain = str(row["domain"])
        confidence_verdict = str(row["confidence_verdict"])
        freshness_state = str(row["freshness_state"])

        summary = summaries.get(domain)
        if summary is None:
            summary = {
                "domain": domain,
                "verdict": confidence_verdict,
                "count": 0,
                "degraded_count": 0,
                "stale_count": 0,
            }
            summaries[domain] = summary
        else:
            summary["verdict"] = worst_case_verdict(
                summary["verdict"], confidence_verdict
            )

        summary["count"] += 1
        if confidence_verdict.lower() != "trustworthy":
            summary["degraded_count"] += 1
        if is_stale_publication(freshness_state):
            summary["stale_count"] += 1

    return [summaries[domain] for domain in sorted(summaries)]
