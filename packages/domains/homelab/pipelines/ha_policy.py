"""HA Phase 4 — Policy evaluation engine.

A policy is a named rule that evaluates current platform state and produces a
verdict.  Verdicts:

    ok          — condition within bounds
    warning     — approaching a threshold
    breach      — threshold exceeded
    unavailable — insufficient data to evaluate

Built-in demo policies (hardcoded, seeded defaults):
    budget_status        — current month max utilization across all categories
    monthly_spend_rate   — spending pace vs days elapsed in the current month
    bridge_health        — WebSocket bridge last_sync_at freshness (5 min threshold)
    kitchen_light_request — approval-gated device action via HA helper state

Operator-authored policies are loaded from the policy registry at evaluation
time alongside these built-in seeds.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

logger = logging.getLogger("homelab_analytics.ha_policy")

PolicyVerdict = Literal["ok", "warning", "breach", "unavailable"]

AuthorityMode = Literal["registry", "snapshot", "unavailable"]

_SNAPSHOT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PolicyAuthorityStatus:
    """Effective authority for registry-policy evaluation.

    ``registry``    — enabled policies were loaded live from the registry.
    ``snapshot``    — the registry is unreachable; evaluation runs against the
                      last-known-good snapshot of enabled policies (degraded).
    ``unavailable`` — no registry store is configured, or the registry is
                      unreachable and no snapshot exists; registry policies are
                      not evaluated and nothing is silently revived.
    """

    mode: AuthorityMode
    registry_configured: bool
    snapshot_version: int
    snapshot_saved_at: str | None
    last_registry_success_at: str | None
    last_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "registry_configured": self.registry_configured,
            "snapshot_version": self.snapshot_version,
            "snapshot_saved_at": self.snapshot_saved_at,
            "last_registry_success_at": self.last_registry_success_at,
            "last_error": self.last_error,
        }

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

# Type alias for the context-fetch callable.
FetchFn = Callable[[], dict[str, Any]]

# Batched publication fetch: given the deduplicated set of publication keys
# referenced by effective policies, return ``publication_<key>`` → rows.
PublicationFetchFn = Callable[[frozenset[str]], dict[str, Any]]

_STALE_FRESHNESS_STATES = {"OVERDUE", "MISSING_PERIOD", "PARSE_FAILED"}


def _referenced_publication_keys(
    policies: list[dict[str, Any]],
) -> frozenset[str]:
    """Publication keys read as row data by the given policies (deduplicated).

    Only ``publication_value_comparison`` rules consume publication rows;
    freshness rules read confidence snapshots from the control plane instead.
    """
    keys: set[str] = set()
    for policy in policies:
        try:
            rule_doc = json.loads(policy["rule_document"])
        except (ValueError, TypeError, KeyError):
            continue
        if rule_doc.get("rule_kind") == "publication_value_comparison":
            key = rule_doc.get("publication_key")
            if isinstance(key, str) and key:
                keys.add(key)
    return frozenset(keys)


# ---------------------------------------------------------------------------
# Builtin seed lifecycle
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicySeedDefinition:
    """A declarative policy seeded into the registry as source_kind='builtin'."""

    policy_id: str
    display_name: str
    description: str
    rule_document: dict[str, Any]
    enabled: bool = True


def _seed_content_hash(
    display_name: str, description: str, rule_document: dict[str, Any] | str
) -> str:
    """Hash of the seed-owned content. ``enabled`` is deliberately excluded:
    it is operator-owned state after the initial create."""
    if isinstance(rule_document, str):
        rule_document = json.loads(rule_document)
    canonical = json.dumps(
        {
            "display_name": display_name,
            "description": description,
            "rule_document": rule_document,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# None of the four code built-ins (budget_status, monthly_spend_rate,
# bridge_health, kitchen_light_request) is expressible behavior-identically in
# the three shipped declarative rule kinds: the budget pair aggregate across
# all budget_rows context entries with dual warning/breach thresholds, bridge
# health reads bridge sync state no rule kind covers, and the kitchen-light
# request needs a warning verdict plus approval-action metadata that
# declarative rules cannot carry. Per the template-honesty rule (omit what the
# rule language cannot express, never approximate), the production seed list
# is empty until richer rule kinds exist; the lifecycle machinery below is the
# installation path for future seeds and A2 templates.
BUILTIN_POLICY_SEEDS: list[PolicySeedDefinition] = []

_SEED_STATE_SCHEMA_VERSION = 1


def _load_seed_state(seed_state_path: Path | None) -> dict[str, str]:
    if seed_state_path is None or not seed_state_path.exists():
        return {}
    try:
        document = json.loads(seed_state_path.read_text(encoding="utf-8"))
        seeded = document.get("seeded", {})
        if not isinstance(seeded, dict):
            raise ValueError("seed state 'seeded' must be a mapping")
        return {str(k): str(v) for k, v in seeded.items()}
    except Exception as exc:
        logger.warning(
            "Failed to load policy seed state; treating as unseeded",
            extra={"path": str(seed_state_path), "error": str(exc)},
        )
        return {}


def _persist_seed_state(
    seed_state_path: Path | None, seeded: dict[str, str]
) -> None:
    if seed_state_path is None:
        return
    try:
        seed_state_path.parent.mkdir(parents=True, exist_ok=True)
        document = {
            "schema_version": _SEED_STATE_SCHEMA_VERSION,
            "seeded": seeded,
        }
        tmp_path = seed_state_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        os.replace(tmp_path, seed_state_path)
    except Exception as exc:
        logger.warning(
            "Failed to persist policy seed state",
            extra={"path": str(seed_state_path), "error": str(exc)},
        )


def ensure_builtin_policies(
    store: Any,
    *,
    seeds: list[PolicySeedDefinition] | None = None,
    seed_state_path: Path | None = None,
) -> dict[str, list[str]]:
    """Idempotently install builtin policy seeds into the registry.

    Guarantees (see the policy-and-automation architecture doc):
      * one row per stable policy id, safe under concurrent starts (the
        registry primary key arbitrates; a lost create race re-reads the row);
      * a seed-definition upgrade rewrites a row only while its seed-owned
        content (display name, description, rule document) still matches what
        was previously seeded — operator edits and the operator-owned
        ``enabled`` flag are never overwritten;
      * a row the operator deleted is never re-created (the local seed-state
        sidecar is the tombstone record);
      * a previously seeded id absent from the current seed list is reported
        as orphaned, never deleted.

    Returns a summary mapping of outcome → policy ids.
    """
    from packages.storage.control_plane import (
        PolicyDefinitionCreate,
        PolicyDefinitionUpdate,
    )

    resolved_seeds = BUILTIN_POLICY_SEEDS if seeds is None else seeds
    seeded_state = _load_seed_state(seed_state_path)
    summary: dict[str, list[str]] = {
        "created": [],
        "upgraded": [],
        "unchanged": [],
        "skipped_deleted": [],
        "skipped_operator_edited": [],
        "conflict": [],
        "orphaned": [],
    }

    for seed in resolved_seeds:
        seed_hash = _seed_content_hash(
            seed.display_name, seed.description, seed.rule_document
        )
        recorded_hash = seeded_state.get(seed.policy_id)

        try:
            existing = store.get_policy_definition(seed.policy_id)
        except KeyError:
            existing = None
        except Exception as exc:
            logger.warning(
                "Policy seed lookup failed",
                extra={"policy_id": seed.policy_id, "error": str(exc)},
            )
            continue

        if recorded_hash is not None and existing is None:
            # We seeded it before and the operator deleted it: tombstoned.
            summary["skipped_deleted"].append(seed.policy_id)
            continue

        if existing is None:
            try:
                store.create_policy_definition(
                    PolicyDefinitionCreate(
                        policy_id=seed.policy_id,
                        display_name=seed.display_name,
                        policy_kind="declarative_rule",
                        rule_schema_version="1.0",
                        rule_document=json.dumps(seed.rule_document),
                        enabled=seed.enabled,
                        source_kind="builtin",
                        description=seed.description,
                        creator="builtin-seed",
                    )
                )
                seeded_state[seed.policy_id] = seed_hash
                summary["created"].append(seed.policy_id)
            except Exception:
                # Lost a concurrent-start race (or the id pre-exists): the
                # primary key arbitrates. Re-read and reconcile below.
                try:
                    existing = store.get_policy_definition(seed.policy_id)
                except Exception as exc:
                    logger.warning(
                        "Policy seed create failed",
                        extra={"policy_id": seed.policy_id, "error": str(exc)},
                    )
                    continue

        if existing is None:
            continue

        row_hash = _seed_content_hash(
            existing.display_name,
            existing.description or "",
            existing.rule_document,
        )
        if row_hash == seed_hash:
            seeded_state[seed.policy_id] = seed_hash
            if seed.policy_id not in summary["created"]:
                summary["unchanged"].append(seed.policy_id)
        elif recorded_hash is not None and row_hash == recorded_hash:
            # Seed definition upgraded and the row is still exactly what we
            # seeded: apply the upgrade without touching `enabled`.
            try:
                store.update_policy_definition(
                    seed.policy_id,
                    PolicyDefinitionUpdate(
                        display_name=seed.display_name,
                        description=seed.description,
                        rule_document=json.dumps(seed.rule_document),
                    ),
                )
                seeded_state[seed.policy_id] = seed_hash
                summary["upgraded"].append(seed.policy_id)
            except Exception as exc:
                logger.warning(
                    "Policy seed upgrade failed",
                    extra={"policy_id": seed.policy_id, "error": str(exc)},
                )
        elif recorded_hash is not None:
            # Operator edited the row after seeding: theirs now.
            summary["skipped_operator_edited"].append(seed.policy_id)
        else:
            # Id collision with a row we never seeded: leave it alone.
            summary["conflict"].append(seed.policy_id)

    current_seed_ids = {seed.policy_id for seed in resolved_seeds}
    for policy_id in sorted(set(seeded_state) - current_seed_ids):
        summary["orphaned"].append(policy_id)

    _persist_seed_state(seed_state_path, seeded_state)
    return summary


def _compare_values(left: float, operator: str, right: float) -> bool:
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    if operator == "eq":
        return left == right
    if operator == "neq":
        return left != right
    return False


def _evaluate_declarative_rule(
    rule_doc: dict[str, Any],
    context: dict[str, Any],
    now: datetime,
    control_plane_store: Any | None,
) -> tuple[PolicyVerdict, str | None]:
    """Evaluate a declarative rule document against the current context.

    Context keys consumed:
      ``publication_<key>`` — list[dict] for publication_value_comparison
      ``ha_entities``       — list[dict] with ``entity_id`` + ``state`` for
                              ha_helper_state_comparison
    Freshness comparisons fall back to the control_plane_store confidence
    snapshots when available.
    """
    from pydantic import ValidationError

    from packages.platform.policy_schema import (
        HaHelperStateComparisonRule,
        PublicationFreshnessComparisonRule,
        PublicationValueComparisonRule,
        parse_rule_document,
    )

    try:
        rule = parse_rule_document(rule_doc)
    except (ValueError, ValidationError) as exc:
        logger.warning("Invalid registry rule document", extra={"error": str(exc)})
        return "unavailable", None

    if isinstance(rule, PublicationValueComparisonRule):
        rows: list[dict] = context.get(f"publication_{rule.publication_key}", [])
        if not rows:
            return "unavailable", None
        row = rows[0] if isinstance(rows, list) else rows
        raw = row.get(rule.field_name)
        if raw is None:
            return "unavailable", None
        try:
            value = float(raw)
            threshold = float(rule.threshold)
        except (ValueError, TypeError):
            return "unavailable", None
        verdict: PolicyVerdict = "breach" if _compare_values(value, rule.operator, threshold) else "ok"
        return verdict, str(value)

    if isinstance(rule, PublicationFreshnessComparisonRule):
        if control_plane_store is None:
            return "unavailable", None
        try:
            snapshots = control_plane_store.list_publication_confidence_snapshots(
                publication_key=rule.publication_key, limit=1
            )
        except Exception:
            return "unavailable", None
        if not snapshots:
            return "unavailable", None
        snap = snapshots[0]
        try:
            assessed_at = snap.assessed_at if isinstance(snap.assessed_at, datetime) else datetime.fromisoformat(str(snap.assessed_at))
            age_hours = (now - assessed_at.replace(tzinfo=UTC) if assessed_at.tzinfo is None else now - assessed_at).total_seconds() / 3600
        except Exception:
            return "unavailable", None
        verdict = "breach" if _compare_values(age_hours, rule.operator, rule.threshold_hours) else "ok"
        return verdict, f"{age_hours:.1f}h"

    if isinstance(rule, HaHelperStateComparisonRule):
        entities: list[dict] = context.get("ha_entities", [])
        entity_state: str | None = None
        for entity in entities:
            if entity.get("entity_id") == rule.entity_id:
                entity_state = str(entity.get("state", ""))
                break
        if entity_state is None:
            return "unavailable", None
        expected = str(rule.expected_value)
        if rule.operator == "eq":
            verdict = "ok" if entity_state == expected else "breach"
        elif rule.operator == "neq":
            verdict = "ok" if entity_state != expected else "breach"
        else:
            try:
                verdict = "ok" if _compare_values(float(entity_state), rule.operator, float(expected)) else "breach"
            except (ValueError, TypeError):
                verdict = "unavailable"
        return verdict, entity_state

    return "unavailable", None


class HaPolicyEvaluator:
    """Evaluates built-in seed policies and operator-authored registry policies.

    Parameters
    ----------
    fetch_fn:
        Callable returning a context dict. Expected keys:
            ``bridge_connected``             (bool)
            ``bridge_last_sync_at``          (str | None)
            ``budget_rows``                  (list[dict])
            ``ha_entities``                  (list[dict])
            ``publication_<key>``            (list[dict]) — optional, for
                                             publication_value_comparison rules
    policy_registry_store:
        Optional store implementing ``list_policy_definitions``. When provided,
        enabled operator-authored policies are loaded and evaluated alongside
        the built-in seeds.
    """

    def __init__(
        self,
        fetch_fn: FetchFn,
        *,
        control_plane_store: Any | None = None,
        policy_registry_store: Any | None = None,
        snapshot_path: Path | None = None,
        publication_fetch_fn: PublicationFetchFn | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._publication_fetch_fn = publication_fetch_fn
        self._control_plane_store = control_plane_store
        self._policy_registry_store = policy_registry_store
        self._snapshot_path = snapshot_path
        self._last_results: list[PolicyResult] = []
        self._lkg_policies: list[dict[str, Any]] | None = None
        self._snapshot_version = 0
        self._snapshot_saved_at: str | None = None
        self._last_registry_success_at: str | None = None
        self._last_error: str | None = None
        self._authority_mode: AuthorityMode = "unavailable"
        self._load_snapshot_file()

    def _load_snapshot_file(self) -> None:
        # The snapshot deliberately lives outside the registry's failure
        # domain (a local file, not a registry table) so it stays readable
        # during a registry outage and across process restarts.
        if self._snapshot_path is None or not self._snapshot_path.exists():
            return
        try:
            document = json.loads(self._snapshot_path.read_text(encoding="utf-8"))
            policies = document["policies"]
            if not isinstance(policies, list):
                raise ValueError("snapshot policies must be a list")
            self._lkg_policies = policies
            self._snapshot_version = int(document.get("snapshot_version", 0))
            self._snapshot_saved_at = document.get("saved_at")
        except Exception as exc:
            logger.warning(
                "Failed to load policy authority snapshot",
                extra={"path": str(self._snapshot_path), "error": str(exc)},
            )

    def _persist_snapshot_file(self) -> None:
        if self._snapshot_path is None:
            return
        try:
            self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            document = {
                "schema_version": _SNAPSHOT_SCHEMA_VERSION,
                "snapshot_version": self._snapshot_version,
                "saved_at": self._snapshot_saved_at,
                "policies": self._lkg_policies,
            }
            tmp_path = self._snapshot_path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._snapshot_path)
        except Exception as exc:
            logger.warning(
                "Failed to persist policy authority snapshot",
                extra={"path": str(self._snapshot_path), "error": str(exc)},
            )

    def _refresh_registry_policies(
        self, now: datetime
    ) -> list[dict[str, Any]] | None:
        """Load enabled registry policies, applying snapshot authority.

        Returns the effective policy list to evaluate, or ``None`` when
        registry policies must not be evaluated (mode ``unavailable``).
        Only *enabled* policies are ever snapshotted, so an operator-disabled
        policy cannot be revived by an outage.
        """
        if self._policy_registry_store is None:
            self._authority_mode = "unavailable"
            return None
        try:
            records = self._policy_registry_store.list_policy_definitions(
                enabled_only=True
            )
        except Exception as exc:
            self._last_error = str(exc)
            if self._lkg_policies is not None:
                self._authority_mode = "snapshot"
                logger.warning(
                    "Policy registry unreachable; evaluating last-known-good snapshot",
                    extra={
                        "snapshot_version": self._snapshot_version,
                        "error": str(exc),
                    },
                )
                return self._lkg_policies
            self._authority_mode = "unavailable"
            logger.warning(
                "Policy registry unreachable and no snapshot exists",
                extra={"error": str(exc)},
            )
            return None

        policies = [
            {
                "policy_id": record.policy_id,
                "display_name": record.display_name,
                "description": record.description or "",
                "rule_document": record.rule_document,
                "source_kind": record.source_kind,
            }
            for record in records
        ]
        self._last_registry_success_at = now.isoformat()
        self._last_error = None
        if policies != self._lkg_policies:
            self._snapshot_version += 1
            self._lkg_policies = policies
            self._snapshot_saved_at = now.isoformat()
            self._persist_snapshot_file()
        self._authority_mode = "registry"
        return policies

    def _publication_confidence(
        self, publication_key: str, now: datetime
    ) -> ConfidenceSummary | None:
        """Latest confidence snapshot for one publication, or None."""
        if self._control_plane_store is None:
            return None
        try:
            snapshots = self._control_plane_store.list_publication_confidence_snapshots(
                publication_key=publication_key, limit=1
            )
        except Exception:
            return None
        if not snapshots:
            return None
        snap = snapshots[0]
        try:
            assessed_at = (
                snap.assessed_at
                if isinstance(snap.assessed_at, datetime)
                else datetime.fromisoformat(str(snap.assessed_at))
            )
        except Exception:
            assessed_at = now
        return ConfidenceSummary(
            verdict=snap.confidence_verdict,
            freshness_state=snap.freshness_state,
            completeness_pct=snap.completeness_pct,
            assessed_at=assessed_at,
        )

    def get_authority_status(self) -> PolicyAuthorityStatus:
        """Return the effective authority mode for registry-policy evaluation."""
        return PolicyAuthorityStatus(
            mode=self._authority_mode,
            registry_configured=self._policy_registry_store is not None,
            snapshot_version=self._snapshot_version,
            snapshot_saved_at=self._snapshot_saved_at,
            last_registry_success_at=self._last_registry_success_at,
            last_error=self._last_error,
        )

    def evaluate(self) -> list[PolicyResult]:
        """Fetch current platform state and evaluate all policies.

        One evaluation cycle observes one context: the effective policy set is
        resolved first, the publications those policies reference are fetched
        once as a deduplicated batch, and every policy in the cycle evaluates
        against that same snapshot of facts.
        """
        now = datetime.now(UTC)
        effective_policies = self._refresh_registry_policies(now)

        try:
            context = self._fetch_fn()
        except Exception as exc:
            logger.warning("Policy context fetch failed", extra={"error": str(exc)})
            context = {}

        if effective_policies and self._publication_fetch_fn is not None:
            referenced_keys = _referenced_publication_keys(effective_policies)
            if referenced_keys:
                try:
                    context.update(self._publication_fetch_fn(referenced_keys))
                except Exception as exc:
                    logger.warning(
                        "Policy publication fetch failed",
                        extra={"error": str(exc)},
                    )

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

        if effective_policies is not None:
            publication_confidence_cache: dict[str, ConfidenceSummary | None] = {}
            for reg_policy in effective_policies:
                rule_doc: dict[str, Any] = {}
                try:
                    rule_doc = json.loads(reg_policy["rule_document"])
                    verdict, value = _evaluate_declarative_rule(
                        rule_doc, context, now, self._control_plane_store
                    )
                except Exception as exc:
                    logger.warning(
                        "Registry policy evaluation error",
                        extra={
                            "policy_id": reg_policy["policy_id"],
                            "error": str(exc),
                        },
                    )
                    verdict, value = "unavailable", None

                metadata: dict[str, Any] = {
                    "source_kind": reg_policy["source_kind"],
                    "authority_mode": self._authority_mode,
                }
                policy_freshness = input_freshness
                publication_key = rule_doc.get("publication_key")
                if (
                    rule_doc.get("rule_kind") == "publication_value_comparison"
                    and isinstance(publication_key, str)
                ):
                    metadata["publication_key"] = publication_key
                    if publication_key not in publication_confidence_cache:
                        publication_confidence_cache[publication_key] = (
                            self._publication_confidence(publication_key, now)
                        )
                    publication_summary = publication_confidence_cache[
                        publication_key
                    ]
                    if publication_summary is not None:
                        policy_freshness = publication_summary
                        if (
                            publication_summary.freshness_state
                            in _STALE_FRESHNESS_STATES
                        ):
                            # Stale input must not yield a confident verdict.
                            verdict = "unavailable"
                            value = (
                                "stale input: "
                                f"{publication_summary.freshness_state}"
                            )

                results.append(PolicyResult(
                    id=reg_policy["policy_id"],
                    name=reg_policy["display_name"],
                    description=reg_policy["description"],
                    verdict=verdict,
                    value=value,
                    evaluated_at=now.isoformat(),
                    approval_required=False,
                    metadata=metadata,
                    input_freshness=policy_freshness,
                ))

        self._last_results = results
        return results

    def get_results(self) -> list[PolicyResult]:
        """Return cached last results (empty list if evaluate() not yet called)."""
        return self._last_results
