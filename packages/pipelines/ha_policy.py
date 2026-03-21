"""HA Phase 4 — Policy evaluation engine.

A policy is a named rule that evaluates current platform state and produces a
verdict.  Verdicts:

    ok          — condition within bounds
    warning     — approaching a threshold
    breach      — threshold exceeded
    unavailable — insufficient data to evaluate

Built-in policies:
    budget_status        — current month max utilization across all categories
    monthly_spend_rate   — spending pace vs days elapsed in the current month
    bridge_health        — WebSocket bridge last_sync_at freshness (5 min threshold)
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal

logger = logging.getLogger("homelab_analytics.ha_policy")

PolicyVerdict = Literal["ok", "warning", "breach", "unavailable"]

_WARNING_UTILIZATION_PCT: float = 80.0
_STALE_BRIDGE_SECONDS: int = 300      # 5 minutes
_PACE_OVERSPEND_MARGIN: float = 15.0  # pct-points above daily pace → warning


@dataclass
class PolicyResult:
    """Result of evaluating one policy."""

    id: str
    name: str
    description: str
    verdict: PolicyVerdict
    value: str | None
    evaluated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "verdict": self.verdict,
            "value": self.value,
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# Built-in policy evaluation functions
# Signature: (context: dict, now: datetime) → (verdict, value_str | None)
# ---------------------------------------------------------------------------

def _evaluate_budget_status(
    context: dict[str, Any], now: datetime
) -> tuple[PolicyVerdict, str | None]:
    """Max utilisation across all budget categories → ok / warning / breach."""
    rows = context.get("budget_rows") or []
    if not rows:
        return "unavailable", None
    try:
        max_pct = max(float(r.get("utilization_pct") or 0) for r in rows)
    except (TypeError, ValueError):
        return "unavailable", None
    value = f"{max_pct:.1f}%"
    if max_pct > 100.0:
        return "breach", value
    if max_pct >= _WARNING_UTILIZATION_PCT:
        return "warning", value
    return "ok", value


def _evaluate_monthly_spend_rate(
    context: dict[str, Any], now: datetime
) -> tuple[PolicyVerdict, str | None]:
    """Spending pace vs days elapsed in the current month → ok / warning / breach."""
    rows = context.get("budget_rows") or []
    if not rows:
        return "unavailable", None
    try:
        max_pct = max(float(r.get("utilization_pct") or 0) for r in rows)
    except (TypeError, ValueError):
        return "unavailable", None
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    pace_pct = (now.day / days_in_month) * 100.0
    value = f"{max_pct:.1f}% spent, {pace_pct:.1f}% of month elapsed"
    if max_pct > 100.0:
        return "breach", value
    if max_pct > pace_pct + _PACE_OVERSPEND_MARGIN:
        return "warning", value
    return "ok", value


def _evaluate_bridge_health(
    context: dict[str, Any], now: datetime
) -> tuple[PolicyVerdict, str | None]:
    """Bridge last_sync_at freshness → ok / warning / unavailable."""
    last_sync_at = context.get("bridge_last_sync_at")
    if not last_sync_at:
        return "unavailable", None
    try:
        synced = datetime.fromisoformat(last_sync_at)
        if synced.tzinfo is None:
            synced = synced.replace(tzinfo=UTC)
        age_seconds = (now - synced).total_seconds()
    except (ValueError, TypeError):
        return "unavailable", None
    value = f"{int(age_seconds)}s since last sync"
    if age_seconds > _STALE_BRIDGE_SECONDS:
        return "warning", value
    return "ok", value


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------

@dataclass
class _PolicyDef:
    id: str
    name: str
    description: str
    evaluate_fn: Callable[[dict[str, Any], datetime], tuple[PolicyVerdict, str | None]]


_POLICIES: list[_PolicyDef] = [
    _PolicyDef(
        id="budget_status",
        name="Budget Status",
        description="Current month max budget utilization across all categories.",
        evaluate_fn=_evaluate_budget_status,
    ),
    _PolicyDef(
        id="monthly_spend_rate",
        name="Monthly Spend Rate",
        description="Spending pace relative to days elapsed in the current month.",
        evaluate_fn=_evaluate_monthly_spend_rate,
    ),
    _PolicyDef(
        id="bridge_health",
        name="Bridge Health",
        description="WebSocket bridge freshness — last sync within 5 minutes.",
        evaluate_fn=_evaluate_bridge_health,
    ),
]

# Type alias for the context-fetch callable.
FetchFn = Callable[[], dict[str, Any]]


class HaPolicyEvaluator:
    """Evaluates built-in policies against current platform state.

    Parameters
    ----------
    fetch_fn:
        Callable with no arguments that returns a context dict.
        Expected keys:
            ``bridge_connected``    (bool)
            ``bridge_last_sync_at`` (str | None) — ISO timestamp
            ``budget_rows``         (list[dict]) — mart_budget_progress_current rows
    """

    def __init__(self, fetch_fn: FetchFn) -> None:
        self._fetch_fn = fetch_fn
        self._last_results: list[PolicyResult] = []

    def evaluate(self) -> list[PolicyResult]:
        """Fetch current platform state and evaluate all policies."""
        try:
            context = self._fetch_fn()
        except Exception as exc:
            logger.warning("Policy context fetch failed", extra={"error": str(exc)})
            context = {}

        now = datetime.now(UTC)
        results: list[PolicyResult] = []
        for policy in _POLICIES:
            try:
                verdict, value = policy.evaluate_fn(context, now)
            except Exception as exc:
                logger.warning(
                    "Policy evaluation error",
                    extra={"policy_id": policy.id, "error": str(exc)},
                )
                verdict, value = "unavailable", None
            results.append(PolicyResult(
                id=policy.id,
                name=policy.name,
                description=policy.description,
                verdict=verdict,
                value=value,
                evaluated_at=now.isoformat(),
            ))

        self._last_results = results
        return results

    def get_results(self) -> list[PolicyResult]:
        """Return cached last results (empty list if evaluate() not yet called)."""
        return self._last_results
