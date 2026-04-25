"""HA Phase 4 — Policy evaluation engine.

A policy is a named rule that evaluates current platform state and produces a
verdict.  Verdicts:

    ok          — condition within bounds
    warning     — approaching a threshold
    breach      — threshold exceeded
    unavailable — insufficient data to evaluate

Built-in demo policies (hardcoded, not operator-authored):
    budget_status        — current month max utilization across all categories
    monthly_spend_rate   — spending pace vs days elapsed in the current month
    bridge_health        — WebSocket bridge last_sync_at freshness (5 min threshold)
    kitchen_light_request — approval-gated device action via HA helper state

These built-ins exercise the evaluation loop. The operator-facing policy model
(persisted registry, rule schema, CRUD API) is not yet implemented.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Literal

logger = logging.getLogger("homelab_analytics.ha_policy")

PolicyVerdict = Literal["ok", "warning", "breach", "unavailable"]

def _verdict_severity(verdict: str) -> int:
    """Return severity of a confidence verdict (higher = worse)."""
    severity_map = {
        "TRUSTWORTHY": 1,
        "DEGRADED": 2,
        "UNRELIABLE": 3,
        "UNAVAILABLE": 4,
    }
    return severity_map.get(verdict, 0)


def _freshness_severity(state: str) -> int:
    """Return severity of a freshness state (higher = worse)."""
    severity_map = {
        "CURRENT": 1,
        "DUE_SOON": 2,
        "OVERDUE": 3,
        "MISSING_PERIOD": 4,
        "PARSE_FAILED": 5,
        "UNCONFIGURED": 0,
    }
    return severity_map.get(state, 0)


_WARNING_UTILIZATION_PCT: float = 80.0
_STALE_BRIDGE_SECONDS: int = 300      # 5 minutes
_PACE_OVERSPEND_MARGIN: float = 15.0  # pct-points above daily pace → warning


@dataclass(frozen=True)
class ConfidenceSummary:
    """Summary of publication confidence at time of policy evaluation."""

    verdict: str
    freshness_state: str
    completeness_pct: int
    assessed_at: datetime


@dataclass
class PolicyResult:
    """Result of evaluating one policy."""

    id: str
    name: str
    description: str
    verdict: PolicyVerdict
    value: str | None
    evaluated_at: str
    approval_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    input_freshness: ConfidenceSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        input_freshness_dict = None
        if self.input_freshness is not None:
            input_freshness_dict = {
                "verdict": self.input_freshness.verdict,
                "freshness_state": self.input_freshness.freshness_state,
                "completeness_pct": self.input_freshness.completeness_pct,
                "assessed_at": self.input_freshness.assessed_at.isoformat(),
            }
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "verdict": self.verdict,
            "value": self.value,
            "evaluated_at": self.evaluated_at,
            "approval_required": self.approval_required,
            "metadata": dict(self.metadata),
            "input_freshness": input_freshness_dict,
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


def _evaluate_kitchen_light_request(
    context: dict[str, Any], now: datetime
) -> tuple[PolicyVerdict, str | None]:
    """Operator-requested kitchen light control via HA helper state."""
    entities = context.get("ha_entities") or []
    helper = next(
        (
            entity
            for entity in entities
            if entity.get("entity_id") == "input_boolean.hla_kitchen_light_request"
        ),
        None,
    )
    if helper is None:
        return "unavailable", None
    if str(helper.get("last_state") or "").lower() != "on":
        return "ok", "Kitchen light request helper is off."
    return "warning", "Kitchen light request helper is on."


# ---------------------------------------------------------------------------
# Built-in policy definitions
# ---------------------------------------------------------------------------

@dataclass
class _PolicyDef:
    id: str
    name: str
    description: str
    evaluate_fn: Callable[[dict[str, Any], datetime], tuple[PolicyVerdict, str | None]]
    approval_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


_BUILTIN_POLICIES: list[_PolicyDef] = [
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
    _PolicyDef(
        id="kitchen_light_request",
        name="Kitchen Light Request",
        description="Approval-gated kitchen light request surfaced from a HA helper.",
        evaluate_fn=_evaluate_kitchen_light_request,
        approval_required=True,
        metadata={
            "approval_action": {
                "domain": "light",
                "service": "turn_on",
                "data": {"entity_id": "light.kitchen"},
            }
        },
    ),
]

# ---------------------------------------------------------------------------
# Design note: operator-authored policy registry (not yet implemented)
#
# _BUILTIN_POLICIES is the only source of policies today. A future policy
# engine would replace or augment it with:
#   - a DB-backed PolicyRegistry persisting operator-authored PolicyDef rows
#   - a rule schema or expression DSL so thresholds and conditions are
#     configurable without editing Python source
#   - CRUD API endpoints for policy definitions
#   - HaPolicyEvaluator loading from the registry at runtime
#
# Until those exist, the evaluator is working infrastructure against demo
# policies, not an operator-facing feature.
# ---------------------------------------------------------------------------

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

    def __init__(
        self,
        fetch_fn: FetchFn,
        *,
        control_plane_store: Any | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._control_plane_store = control_plane_store
        self._last_results: list[PolicyResult] = []

    def evaluate(self) -> list[PolicyResult]:
        """Fetch current platform state and evaluate all policies."""
        try:
            context = self._fetch_fn()
        except Exception as exc:
            logger.warning("Policy context fetch failed", extra={"error": str(exc)})
            context = {}

        now = datetime.now(UTC)

        # Capture confidence snapshot at evaluation time if available
        input_freshness = None
        if self._control_plane_store is not None:
            try:
                snapshots = self._control_plane_store.list_publication_confidence_snapshots()
                if snapshots:
                    # Aggregate to worst-case verdict for all publications
                    verdicts = [snap.confidence_verdict for snap in snapshots]
                    worst_verdict = verdicts[0]
                    for v in verdicts[1:]:
                        if _verdict_severity(v) > _verdict_severity(worst_verdict):
                            worst_verdict = v

                    avg_completeness = sum(
                        snap.completeness_pct for snap in snapshots
                    ) // len(snapshots)
                    worst_freshness = snapshots[0].freshness_state
                    for snap in snapshots[1:]:
                        if _freshness_severity(snap.freshness_state) > _freshness_severity(
                            worst_freshness
                        ):
                            worst_freshness = snap.freshness_state

                    input_freshness = ConfidenceSummary(
                        verdict=worst_verdict,
                        freshness_state=worst_freshness,
                        completeness_pct=avg_completeness,
                        assessed_at=now,
                    )
            except Exception:
                pass

        results: list[PolicyResult] = []
        for policy in _BUILTIN_POLICIES:
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
                approval_required=policy.approval_required,
                metadata=dict(policy.metadata),
                input_freshness=input_freshness,
            ))

        self._last_results = results
        return results

    def get_results(self) -> list[PolicyResult]:
        """Return cached last results (empty list if evaluate() not yet called)."""
        return self._last_results
