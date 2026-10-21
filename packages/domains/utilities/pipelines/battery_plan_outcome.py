"""Publish the Kotiakku battery-plan outcome as reporting marts.

Reads the transformation-layer HA history (``fact_ha_state_change``) through
the evidence qualifier in ``kotiakku_evidence`` and rebuilds two reporting
marts:

- ``mart_battery_plan_outcome``: one row per assessed decision month with the
  verdict, coverage, freshness, tariff assumptions, lineage and remediation.
- ``mart_battery_plan_outcome_values``: one row per material value with its
  status (observed / derived / estimated / heuristic / user_entered) and role
  (actual / estimate / assumption / quality). Missing values stay missing
  (``is_missing``), never zero.

Verdict guard: only a fully qualified assessment (no reason codes, fresh
source, complete coverage) can yield ``benefit_estimated``; everything else is
``insufficient_evidence``. Even a qualified verdict is a source estimate, not
realized savings, and never authorizes an action.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from packages.domains.utilities.battery_plan_decision import (
    BATTERY_PLAN_DECISION,
    BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES,
    BATTERY_PLAN_MIN_COVERAGE_PCT,
)
from packages.domains.utilities.pipelines.battery_plan_models import (
    MART_BATTERY_PLAN_OUTCOME_COLUMNS,
    MART_BATTERY_PLAN_OUTCOME_TABLE,
    MART_BATTERY_PLAN_OUTCOME_VALUES_COLUMNS,
    MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE,
)
from packages.domains.utilities.pipelines.kotiakku_evidence import (
    assess_kotiakku_battery_plan_from_store,
)
from packages.storage.duckdb_store import DuckDBStore

BATTERY_PLAN_PROFILE_ENV = "HOMELAB_ANALYTICS_BATTERY_PLAN_PROFILE"

_FLOW_VALUES: tuple[tuple[str, str, str, str], ...] = (
    ("grid_power_kwh", "Net grid energy", "kWh", "grid_power_kw"),
    ("grid_to_house_kwh", "Grid to house energy", "kWh", "grid_to_house_kw"),
    ("solar_to_grid_kwh", "Solar to grid energy", "kWh", "solar_to_grid_kw"),
    ("solar_to_battery_kwh", "Solar to battery energy", "kWh", "solar_to_battery_kw"),
    ("battery_to_house_kwh", "Battery to house energy", "kWh", "battery_to_house_kw"),
    (
        "spot_price_avg_cents_per_kwh",
        "Average spot price",
        "c/kWh",
        "spot_price_cents_per_kwh",
    ),
)

_REMEDIATION: dict[str, str] = {
    "source_profile_unconfigured": (
        f"Set {BATTERY_PLAN_PROFILE_ENV} to a JSON profile file with the explicit "
        "Kotiakku HA entity_map and household_timezone, then refresh the publication."
    ),
    "source_profile_invalid": (
        f"Fix the JSON profile referenced by {BATTERY_PLAN_PROFILE_ENV}: it must be "
        "readable and contain entity_map and household_timezone."
    ),
    "source_entity_mapping_incomplete": (
        "Map all seven Kotiakku entities (six measurements plus battery_savings) "
        "explicitly in the profile entity_map."
    ),
    "source_entity_mapping_invalid": "Replace empty entity IDs in the profile entity_map.",
    "source_entity_mapping_ambiguous": (
        "Map each Kotiakku field to a distinct HA entity in the profile entity_map."
    ),
    "household_timezone_unknown": "Set a valid IANA household_timezone in the profile.",
    "decision_month_invalid": "Use YYYY-MM decision months in the profile.",
    "assessment_timestamp_timezone_missing": "Assess with a timezone-aware timestamp.",
    "source_history_table_missing": (
        "Ingest Home Assistant history for the mapped entities so fact_ha_state_change exists."
    ),
    "source_snapshot_missing": (
        "Ingest HA history for the mapped battery_savings entity up to the assessment time."
    ),
    "source_history_timestamp_unknown": (
        "Re-ingest HA history with changed_at and ingested_at timestamps for the economics sensor."
    ),
    "measurement_scope_timestamp_unknown": (
        "Re-ingest HA measurement history with timestamps so each record's month can be established."
    ),
    "unsupported_source_evidence_contract": (
        "Upgrade ha-elisa-kotiakku to evidence contract 1.0."
    ),
    "unsupported_source_calculation_method": (
        "Use the Kotiakku battery_vs_no_battery_site_cost_v1 calculation method."
    ),
    "unsupported_source_period": "Configure Kotiakku for five-minute source periods.",
    "source_period_end_missing": (
        "Check that the Kotiakku integration reports last_period_end; re-run HA ingest."
    ),
    "source_measurements_stale": (
        "Check the Kotiakku integration and its cloud connection, then re-run HA ingest: "
        "the latest source period must be within the freshness limit."
    ),
    "monthly_window_counters_missing": (
        "The source has no window counters for the month; backfill the month in the "
        "integration or choose a month it processed."
    ),
    "monthly_window_counters_invalid": "Source window counters are malformed; upgrade the integration.",
    "monthly_window_counters_incomplete": (
        "The source skipped or missed five-minute windows for the month; backfill them "
        "in the integration or choose a fully covered month."
    ),
    "monthly_tariff_snapshot_missing_or_mixed": (
        "Verify the integration's tariff configuration: one consistent tariff snapshot "
        "is required for the month."
    ),
    "monthly_tariff_signature_mismatch": (
        "The month's tariff snapshot does not match its signature; re-verify tariff inputs."
    ),
    "monthly_savings_estimate_missing": (
        "The source published no savings estimate for the month; check the integration."
    ),
    "monthly_savings_and_window_evidence_disagree": (
        "Source savings and window evidence disagree; re-run the integration's monthly calculation."
    ),
    "battery_cost_basis_missing": (
        "Enter the battery monthly cost, or total cost plus akkureservihyvitys "
        "compensation, in the Kotiakku integration."
    ),
    "measurement_window_coverage_incomplete": (
        "Backfill the missing five-minute measurement windows into HA history for the month."
    ),
    "conflicting_duplicate_measurements": (
        "Resolve conflicting duplicate measurement samples in HA history for the month."
    ),
    "measurement_period_invalid": (
        "Check sensor period_start/period_end attributes: each must span five minutes."
    ),
    "measurement_value_or_unit_invalid": (
        "Check measurement units (kW, c/kWh) and unavailable states for the month."
    ),
    "decision_month_not_closed": (
        "Wait until the decision month has closed in the household timezone."
    ),
    "source_summary_and_measurement_periods_disagree": (
        "Re-ingest HA history so the economics and measurement sensors cover the same latest period."
    ),
}


@dataclass(frozen=True)
class BatteryPlanEvidenceProfile:
    """Operator-supplied source mapping; entity names are never guessed."""

    entity_map: Mapping[str, str]
    household_timezone: str
    decision_months: tuple[str, ...] = ()
    freshness_limit_minutes: int = BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES
    # Share of a month's source windows that may be skipped (missing flows or
    # prices) while the month still qualifies; declared, never inferred.
    max_skipped_window_ratio: Decimal = Decimal(0)


@dataclass(frozen=True)
class BatteryPlanProfileResolution:
    profile: BatteryPlanEvidenceProfile | None
    status: str  # configured | unconfigured | invalid


def load_battery_plan_profile(
    environ: Mapping[str, str] | None = None,
) -> BatteryPlanProfileResolution:
    """Resolve the profile from the JSON file named by the profile env var."""
    env = os.environ if environ is None else environ
    raw_path = (env.get(BATTERY_PLAN_PROFILE_ENV) or "").strip()
    if not raw_path:
        return BatteryPlanProfileResolution(None, "unconfigured")
    try:
        document = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return BatteryPlanProfileResolution(None, "invalid")
    return parse_battery_plan_profile(document)


def parse_battery_plan_profile(document: object) -> BatteryPlanProfileResolution:
    if not isinstance(document, dict):
        return BatteryPlanProfileResolution(None, "invalid")
    entity_map = document.get("entity_map")
    timezone_name = document.get("household_timezone")
    months = document.get("decision_months", [])
    freshness = document.get("freshness_limit_minutes", BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES)
    skip_ratio = _skip_ratio(document.get("max_skipped_window_ratio", 0))
    if (
        not isinstance(entity_map, dict)
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in entity_map.items())
        or not isinstance(timezone_name, str)
        or not isinstance(months, list)
        or not all(isinstance(month, str) for month in months)
        or not isinstance(freshness, int)
        or isinstance(freshness, bool)
        or freshness <= 0
        or skip_ratio is None
    ):
        return BatteryPlanProfileResolution(None, "invalid")
    return BatteryPlanProfileResolution(
        BatteryPlanEvidenceProfile(
            entity_map=dict(entity_map),
            household_timezone=timezone_name,
            decision_months=tuple(months),
            freshness_limit_minutes=freshness,
            max_skipped_window_ratio=skip_ratio,
        ),
        "configured",
    )


def _skip_ratio(value: object) -> Decimal | None:
    """Accept a declared ratio in [0, 0.01]; anything looser is refused."""
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    ratio = _decimal(value)
    if ratio is None or ratio < 0 or ratio > Decimal("0.01"):
        return None
    return ratio


def ensure_battery_plan_storage(store: DuckDBStore) -> None:
    store.ensure_table(MART_BATTERY_PLAN_OUTCOME_TABLE, MART_BATTERY_PLAN_OUTCOME_COLUMNS)
    store.ensure_table(
        MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE, MART_BATTERY_PLAN_OUTCOME_VALUES_COLUMNS
    )


def refresh_battery_plan_outcome(
    store: DuckDBStore,
    *,
    resolution: BatteryPlanProfileResolution,
    assessed_at: datetime,
) -> int:
    """Rebuild both outcome marts (DELETE + INSERT). Returns outcome row count."""
    if assessed_at.tzinfo is None:
        raise ValueError("assessed_at must be timezone-aware")
    ensure_battery_plan_storage(store)
    summaries: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    for month, assessment, freshness_limit in _assessments(
        store, resolution=resolution, assessed_at=assessed_at
    ):
        summary, value_rows = build_battery_plan_outcome_rows(
            assessment,
            decision_month=month,
            assessed_at=assessed_at,
            profile_status=resolution.status,
            freshness_limit_minutes=freshness_limit,
        )
        summaries.append(summary)
        values.extend(value_rows)
    store.execute(f"DELETE FROM {MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE}")
    store.execute(f"DELETE FROM {MART_BATTERY_PLAN_OUTCOME_TABLE}")
    if summaries:
        store.insert_rows(MART_BATTERY_PLAN_OUTCOME_TABLE, summaries)
    if values:
        store.insert_rows(MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE, values)
    return len(summaries)


def get_battery_plan_outcome(
    store: DuckDBStore, *, decision_month: str | None = None
) -> list[dict[str, Any]]:
    where, params = ("WHERE decision_month = ?", [decision_month]) if decision_month else ("", [])
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BATTERY_PLAN_OUTCOME_TABLE} {where} ORDER BY decision_month DESC",
        params,
    )


def get_battery_plan_outcome_values(
    store: DuckDBStore, *, decision_month: str | None = None
) -> list[dict[str, Any]]:
    where, params = ("WHERE decision_month = ?", [decision_month]) if decision_month else ("", [])
    return store.fetchall_dicts(
        f"SELECT * FROM {MART_BATTERY_PLAN_OUTCOME_VALUES_TABLE} {where}"
        " ORDER BY decision_month DESC, display_order",
        params,
    )


def _assessments(
    store: DuckDBStore,
    *,
    resolution: BatteryPlanProfileResolution,
    assessed_at: datetime,
) -> list[tuple[str, dict[str, Any], int]]:
    profile = resolution.profile
    if profile is None:
        month = _previous_closed_month(assessed_at, UTC)
        reason = (
            "source_profile_invalid"
            if resolution.status == "invalid"
            else "source_profile_unconfigured"
        )
        return [
            (
                month,
                _unassessed(month, reason),
                BATTERY_PLAN_FRESHNESS_LIMIT_MINUTES,
            )
        ]
    try:
        timezone = ZoneInfo(profile.household_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = None
    months = profile.decision_months or (
        _previous_closed_month(assessed_at, timezone or UTC),
    )
    results = []
    for month in dict.fromkeys(months):
        assessment = assess_kotiakku_battery_plan_from_store(
            store,
            entity_map=dict(profile.entity_map),
            decision_month=month,
            household_timezone=profile.household_timezone,
            assessed_at=assessed_at,
            freshness_limit=timedelta(minutes=profile.freshness_limit_minutes),
            max_skipped_window_ratio=profile.max_skipped_window_ratio,
        )
        results.append((month, assessment, profile.freshness_limit_minutes))
    return results


def _unassessed(month: str, reason: str) -> dict[str, Any]:
    return {
        "evidence_contract_version": None,
        "decision_month": month,
        "evidence_status": "insufficient",
        "recommendation": "insufficient_evidence",
        "recommendation_scope": "review_only",
        "actuation_authorized": False,
        "reason_codes": [reason],
        "estimated_monthly_battery_savings_eur": None,
        "effective_monthly_battery_cost_eur": None,
        "battery_cost_basis": None,
        "source_calculation_method": None,
        "household_timezone": None,
        "source_tariff_snapshot_id": None,
        "source_tariff_snapshot": None,
        "source_last_period_end": None,
        "source_quality": {},
        "lineage": {"source_entity_ids": {}, "source_run_ids": [], "source_report_ingested_at": None},
        "estimate_limitations": [
            "No source profile is available, so no evidence was read.",
            "No recommendation authorizes a tariff change, battery command, or other household action.",
        ],
    }


def build_battery_plan_outcome_rows(
    assessment: Mapping[str, Any],
    *,
    decision_month: str,
    assessed_at: datetime,
    profile_status: str,
    freshness_limit_minutes: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Turn one evidence assessment into a summary row and value-disclosure rows."""
    quality: Mapping[str, Any] = assessment.get("source_quality") or {}
    reasons = [str(code) for code in assessment.get("reason_codes") or []]
    savings = _decimal(assessment.get("estimated_monthly_battery_savings_eur"))
    cost = _decimal(assessment.get("effective_monthly_battery_cost_eur"))
    # Coverage is the source's counter-attested share of savings-qualified
    # windows; HA sample coverage is corroboration only.
    coverage_pct = float(quality.get("source_coverage_pct") or 0.0)
    coverage_floor_pct = float(
        quality.get("source_coverage_floor_pct") or BATTERY_PLAN_MIN_COVERAGE_PCT
    )
    period_end = _parse_aware(assessment.get("source_last_period_end"))
    assessed_utc = assessed_at.astimezone(UTC)
    freshness_age = (
        Decimal(str(round((assessed_utc - period_end).total_seconds() / 60, 2)))
        if period_end is not None
        else None
    )
    if freshness_age is None:
        freshness_status = "unknown"
    elif Decimal(0) <= freshness_age <= Decimal(freshness_limit_minutes):
        freshness_status = "fresh"
    else:
        freshness_status = "stale"

    verdict = _guarded_verdict(
        evidence_status=str(assessment.get("evidence_status")),
        reasons=reasons,
        freshness_status=freshness_status,
        coverage_pct=coverage_pct,
        coverage_floor_pct=coverage_floor_pct,
        savings=savings,
        cost=cost,
    )
    net_benefit = savings - cost if savings is not None and cost is not None else None
    cost_basis: Mapping[str, Any] = assessment.get("battery_cost_basis") or {}
    lineage: Mapping[str, Any] = assessment.get("lineage") or {}
    tariff = assessment.get("source_tariff_snapshot")
    assessment_id = _assessment_id(assessment, decision_month, assessed_utc)

    value_rows = _value_rows(
        assessment_id=assessment_id,
        decision_month=decision_month,
        quality=quality,
        savings=savings,
        cost=cost,
        net_benefit=net_benefit,
        cost_basis=cost_basis,
        tariff=tariff if isinstance(tariff, dict) else None,
        coverage_pct=coverage_pct,
        freshness_age=freshness_age,
        entity_ids=lineage.get("source_entity_ids") or {},
    )
    missing_fields = [row["value_key"] for row in value_rows if row["is_missing"]]
    remediation_lines = list(
        dict.fromkeys(
            _REMEDIATION.get(code, f"Investigate source reason code '{code}'.")
            for code in reasons
        )
    )
    if verdict == "insufficient_evidence" and not remediation_lines:
        remediation_lines.append(
            "Evidence did not meet the decision's sufficiency criteria; re-run the refresh "
            "after the source is fresh and fully covered."
        )
    limitations = list(assessment.get("estimate_limitations") or [])
    limitations.extend(
        [
            "Battery-health limits reported by the integration are heuristic and are not evaluated here.",
            "Net site cost is not supplied by evidence contract 1.0 and is not derived by HLA.",
        ]
    )
    invalid_records = int(quality.get("invalid_period_record_count") or 0) + int(
        quality.get("invalid_value_record_count") or 0
    )
    summary = {
        "assessment_id": assessment_id,
        "decision_key": BATTERY_PLAN_DECISION.decision_key,
        "decision_version": BATTERY_PLAN_DECISION.version,
        "decision_month": decision_month,
        "household_timezone": assessment.get("household_timezone"),
        "assessed_at": assessed_utc.isoformat(),
        "profile_status": profile_status,
        "evidence_status": "qualified" if verdict != "insufficient_evidence" else "insufficient",
        "verdict": verdict,
        "claim_basis": "none" if verdict == "insufficient_evidence" else "source_estimate",
        "source_recommendation": (
            str(assessment.get("recommendation"))
            if verdict != "insufficient_evidence"
            else "insufficient_evidence"
        ),
        "recommendation_scope": "review_only",
        "actuation_authorized": False,
        "estimated_savings_eur": savings,
        "effective_monthly_cost_eur": cost,
        "estimated_net_benefit_eur": net_benefit,
        "cost_basis_method": cost_basis.get("method"),
        "expected_window_count": int(quality.get("expected_window_count") or 0),
        "complete_window_count": int(quality.get("complete_window_count") or 0),
        "missing_window_count": int(quality.get("missing_window_count") or 0),
        "coverage_pct": Decimal(str(coverage_pct)),
        "duplicate_snapshot_count": int(quality.get("duplicate_snapshot_count") or 0),
        "conflicting_window_count": int(quality.get("conflicting_window_count") or 0),
        "invalid_record_count": invalid_records,
        "unknown_scope_timestamp_count": int(quality.get("unknown_scope_timestamp_count") or 0),
        "backfill_status": str(
            quality.get("backfill_status") or "not_established_from_ha_state_history"
        ),
        "source_last_period_end": period_end.isoformat() if period_end else None,
        "freshness_status": freshness_status,
        "freshness_age_minutes": freshness_age,
        "freshness_limit_minutes": freshness_limit_minutes,
        "tariff_snapshot_id": assessment.get("source_tariff_snapshot_id"),
        "tariff_snapshot_json": _json(tariff) if isinstance(tariff, dict) else None,
        "source_calculation_method": assessment.get("source_calculation_method"),
        "source_evidence_contract_version": assessment.get("evidence_contract_version"),
        "reason_codes_json": _json(reasons),
        "missing_fields_json": _json(missing_fields),
        "remediation": " ".join(remediation_lines) or None,
        "limitations_json": _json(limitations),
        "source_entity_ids_json": _json(lineage.get("source_entity_ids") or {}),
        "source_run_ids_json": _json(list(lineage.get("source_run_ids") or [])),
        "source_report_ingested_at": lineage.get("source_report_ingested_at"),
    }
    return summary, value_rows


def _guarded_verdict(
    *,
    evidence_status: str,
    reasons: list[str],
    freshness_status: str,
    coverage_pct: float,
    coverage_floor_pct: float,
    savings: Decimal | None,
    cost: Decimal | None,
) -> str:
    """Stale or incomplete evidence can never produce a positive claim."""
    if (
        evidence_status != "qualified"
        or reasons
        or freshness_status != "fresh"
        or coverage_pct < coverage_floor_pct
        or savings is None
        or cost is None
    ):
        return "insufficient_evidence"
    return "benefit_estimated" if savings >= cost else "no_benefit_estimated"


def _cost_note(method: object, source_basis: object) -> str | None:
    """Explain how the effective monthly cost the verdict uses was obtained."""
    if method == "source_effective_monthly_cost":
        basis = source_basis if isinstance(source_basis, str) and source_basis else "unknown"
        return (
            "Published by the source as its effective monthly cost "
            f"(basis {basis}: gross basis cost minus akkureservihyvitys; may be negative)."
        )
    if method == "total_cost_over_120_months_minus_compensation":
        return "Derived as total cost / 120 months minus akkureservihyvitys compensation."
    return None


def _value_rows(
    *,
    assessment_id: str,
    decision_month: str,
    quality: Mapping[str, Any],
    savings: Decimal | None,
    cost: Decimal | None,
    net_benefit: Decimal | None,
    cost_basis: Mapping[str, Any],
    tariff: dict[str, Any] | None,
    coverage_pct: float,
    freshness_age: Decimal | None,
    entity_ids: Mapping[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(
        key: str,
        label: str,
        value: object,
        *,
        unit: str | None,
        status: str,
        role: str,
        source: str | None,
        note: str | None = None,
    ) -> None:
        numeric = _decimal(value) if not isinstance(value, str) else None
        text = value if isinstance(value, str) else None
        rows.append(
            {
                "assessment_id": assessment_id,
                "decision_month": decision_month,
                "display_order": len(rows) + 1,
                "value_key": key,
                "value_label": label,
                "value_numeric": numeric,
                "value_text": text,
                "unit": unit,
                "value_status": status,
                "value_role": role,
                "is_missing": numeric is None and text is None,
                "source_reference": source,
                "note": note,
            }
        )

    flows: Mapping[str, Any] = quality.get("observed_flow_totals") or {}
    complete = int(quality.get("complete_window_count") or 0)
    expected = int(quality.get("expected_window_count") or 0)
    flow_note = (
        f"Derived from observed five-minute samples over {complete} of {expected} "
        "complete windows; incomplete windows are excluded, not zero-filled."
    )
    for key, label, unit, field in _FLOW_VALUES:
        add(
            key,
            label,
            _decimal(flows.get(key)),
            unit=unit,
            status="derived",
            role="actual",
            source=entity_ids.get(field),
            note=flow_note if complete < expected or not flows else
            "Derived from observed five-minute samples over all expected windows.",
        )
    add(
        "net_site_cost_eur",
        "Net site cost",
        None,
        unit="EUR",
        status="derived",
        role="actual",
        source=None,
        note="Not supplied by Kotiakku evidence contract 1.0; HLA does not derive it.",
    )
    savings_source = entity_ids.get("battery_savings")
    add(
        "estimated_savings_eur",
        "Estimated battery-versus-no-battery savings",
        savings,
        unit="EUR",
        status="estimated",
        role="estimate",
        source=f"{savings_source}#monthly_battery_savings_eur" if savings_source else None,
        note="Source-calculated estimate; not observed bill savings and not causal.",
    )
    method = cost_basis.get("method")
    add(
        "effective_monthly_cost_eur",
        "Effective monthly battery cost",
        cost,
        unit="EUR",
        status="user_entered" if method == "direct_monthly_cost" else "derived",
        role="assumption",
        source=f"{savings_source}#battery_cost_basis" if savings_source else None,
        note=_cost_note(method, cost_basis.get("battery_cost_basis")),
    )
    add(
        "estimated_net_benefit_eur",
        "Estimated net benefit (savings minus cost)",
        net_benefit,
        unit="EUR",
        status="derived",
        role="estimate",
        source=None,
        note="Derived from a source estimate and user-entered cost inputs.",
    )
    for key, label in (
        ("battery_monthly_cost_eur", "Battery monthly cost input"),
        ("battery_total_cost_eur", "Battery total cost input"),
        ("akkureservihyvitys_monthly_eur", "Akkureservihyvitys monthly compensation input"),
    ):
        add(
            key,
            label,
            cost_basis.get(key),
            unit="EUR",
            status="user_entered",
            role="assumption",
            source=f"{savings_source}#{key}" if savings_source else None,
        )
    if tariff is None:
        add(
            "tariff_snapshot",
            "Tariff snapshot for the month",
            None,
            unit=None,
            status="user_entered",
            role="assumption",
            source=None,
            note="No consistent month-specific tariff snapshot was available.",
        )
    else:
        for tariff_key in sorted(tariff):
            raw = tariff[tariff_key]
            add(
                f"tariff.{tariff_key}",
                f"Tariff: {tariff_key}",
                raw if isinstance(raw, str) else _decimal(raw),
                unit=None,
                status="user_entered",
                role="assumption",
                source=f"{savings_source}#monthly_battery_evidence.tariff_snapshot"
                if savings_source
                else None,
            )
    add(
        "coverage_pct",
        "Complete five-minute window coverage",
        Decimal(str(coverage_pct)),
        unit="percent",
        status="derived",
        role="quality",
        source=None,
    )
    add(
        "freshness_age_minutes",
        "Source age at assessment",
        freshness_age,
        unit="minutes",
        status="derived",
        role="quality",
        source=None,
    )
    return rows


def _assessment_id(
    assessment: Mapping[str, Any], decision_month: str, assessed_utc: datetime
) -> str:
    payload = _json(
        {
            "decision_key": BATTERY_PLAN_DECISION.decision_key,
            "decision_version": BATTERY_PLAN_DECISION.version,
            "decision_month": decision_month,
            "assessed_at": assessed_utc.isoformat(),
            "assessment": assessment,
        }
    )
    return "bpo_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _previous_closed_month(assessed_at: datetime, timezone: Any) -> str:
    local = assessed_at.astimezone(timezone)
    first = local.replace(day=1)
    previous = first - timedelta(days=1)
    return previous.strftime("%Y-%m")


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except ArithmeticError:
        return None
    return result if result.is_finite() else None


def _parse_aware(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
