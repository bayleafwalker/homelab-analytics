"""Qualify read-only Kotiakku evidence for a household battery-plan review.

This is a transformation helper over Home Assistant history. Callers must
provide explicit HA entity mappings; entity-name guessing is deliberately not
used. The source integration owns battery economics calculations, while HLA
owns evidence qualification and the review recommendation.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from packages.domains.homelab.pipelines.ha_models import FACT_HA_STATE_CHANGE_TABLE
from packages.storage.duckdb_store import DuckDBStore

KOTIAKKU_EVIDENCE_CONTRACT_VERSION = "1.0"
KOTIAKKU_CALCULATION_METHOD = "battery_vs_no_battery_site_cost_v1"
KOTIAKKU_SAMPLE_FIELDS = (
    "grid_power_kw",
    "solar_to_grid_kw",
    "solar_to_battery_kw",
    "grid_to_house_kw",
    "battery_to_house_kw",
    "spot_price_cents_per_kwh",
)
KOTIAKKU_REQUIRED_ENTITY_MAP_KEYS = frozenset(
    (*KOTIAKKU_SAMPLE_FIELDS, "battery_savings")
)
_EXPECTED_UNITS = {
    "grid_power_kw": "kW",
    "solar_to_grid_kw": "kW",
    "solar_to_battery_kw": "kW",
    "grid_to_house_kw": "kW",
    "battery_to_house_kw": "kW",
    "spot_price_cents_per_kwh": "c/kWh",
}
_UNAVAILABLE_STATES = frozenset({"", "unknown", "unavailable", "none", "nan"})
_SAMPLE_INTERVAL = timedelta(minutes=5)


def assess_kotiakku_battery_plan_evidence(
    *,
    source_rows: list[dict[str, Any]],
    measurement_rows: list[dict[str, Any]],
    entity_map: dict[str, str],
    decision_month: str,
    household_timezone: str,
    assessed_at: datetime,
    freshness_limit: timedelta = timedelta(minutes=15),
) -> dict[str, Any]:
    """Return a traceable review assessment or decline an unqualified claim.

    ``source_rows`` contains history for the mapped ``battery_savings`` HA
    entity. ``measurement_rows`` contains history for the six mapped source
    measurement entities. The caller supplies IDs from source-asset
    configuration, never inferred from display names.
    """
    reasons: list[str] = []
    profile_error = _validate_profile(entity_map, decision_month, assessed_at)
    if profile_error:
        return _empty_assessment(decision_month, entity_map, profile_error)

    assert assessed_at.tzinfo is not None
    try:
        timezone = ZoneInfo(household_timezone)
    except (ZoneInfoNotFoundError, TypeError):
        return _empty_assessment(
            decision_month, entity_map, "household_timezone_unknown"
        )

    source_entity_id = entity_map["battery_savings"]
    snapshots = [
        row for row in source_rows if row.get("entity_id") == source_entity_id
    ]
    if any(
        _parse_datetime(row.get("ingested_at")) is None
        and _parse_datetime(row.get("changed_at")) is None
        for row in snapshots
    ):
        reasons.append("source_history_timestamp_unknown")
    latest_snapshot = _latest_source_snapshot(snapshots, assessed_at=assessed_at)
    if latest_snapshot is None:
        return _empty_assessment(decision_month, entity_map, "source_snapshot_missing")

    source_attrs = _attributes(latest_snapshot)
    contract_version = source_attrs.get("evidence_contract_version")
    if contract_version != KOTIAKKU_EVIDENCE_CONTRACT_VERSION:
        reasons.append("unsupported_source_evidence_contract")
    if source_attrs.get("calculation_method") != KOTIAKKU_CALCULATION_METHOD:
        reasons.append("unsupported_source_calculation_method")
    if source_attrs.get("source_period_minutes") != 5:
        reasons.append("unsupported_source_period")

    period_end = _parse_datetime(source_attrs.get("last_period_end"))
    if period_end is None:
        reasons.append("source_period_end_missing")
    elif period_end > assessed_at or assessed_at - period_end > freshness_limit:
        reasons.append("source_measurements_stale")

    monthly_evidence = source_attrs.get("monthly_battery_evidence")
    month_evidence = (
        monthly_evidence.get(decision_month)
        if isinstance(monthly_evidence, dict)
        else None
    )
    if not isinstance(month_evidence, dict):
        reasons.append("monthly_window_counters_missing")
    month_tariff_snapshot = (
        month_evidence.get("tariff_snapshot")
        if isinstance(month_evidence, dict)
        else None
    )
    month_tariff_snapshot_id = (
        month_evidence.get("tariff_snapshot_id")
        if isinstance(month_evidence, dict)
        else None
    )
    if not isinstance(month_tariff_snapshot, dict) or not isinstance(
        month_tariff_snapshot_id, str
    ):
        reasons.append("monthly_tariff_snapshot_missing_or_mixed")
    elif _tariff_snapshot_id(month_tariff_snapshot) != month_tariff_snapshot_id:
        reasons.append("monthly_tariff_signature_mismatch")

    monthly_savings = source_attrs.get("monthly_battery_savings_eur")
    savings = _finite_decimal(monthly_savings.get(decision_month)) if isinstance(
        monthly_savings, dict
    ) else None
    if savings is None:
        reasons.append("monthly_savings_estimate_missing")
    elif isinstance(month_evidence, dict):
        evidence_savings = _finite_decimal(month_evidence.get("estimated_savings_eur"))
        if evidence_savings is None or evidence_savings != savings:
            reasons.append("monthly_savings_and_window_evidence_disagree")

    monthly_cost = _effective_monthly_cost(source_attrs)
    if monthly_cost is None:
        reasons.append("battery_cost_basis_missing")

    quality = _assess_measurement_coverage(
        measurement_rows=measurement_rows,
        entity_map=entity_map,
        decision_month=decision_month,
        timezone=timezone,
        assessed_at=assessed_at,
    )
    quality["source_window_counters"] = month_evidence
    reasons.extend(quality["reason_codes"])
    if isinstance(month_evidence, dict):
        counter_fields = (
            "processed_window_count",
            "savings_window_count",
            "skipped_savings_window_count",
        )
        counters = {field: month_evidence.get(field) for field in counter_fields}
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in counters.values()
        ):
            reasons.append("monthly_window_counters_invalid")
        elif (
            counters["processed_window_count"] != quality["expected_window_count"]
            or counters["savings_window_count"] != quality["expected_window_count"]
            or counters["skipped_savings_window_count"] != 0
        ):
            reasons.append("monthly_window_counters_incomplete")

    local_month_start = datetime.strptime(decision_month, "%Y-%m").replace(
        tzinfo=timezone
    )
    local_next_month = _next_month(local_month_start)
    if local_next_month.astimezone(UTC) > assessed_at.astimezone(UTC):
        reasons.append("decision_month_not_closed")

    source_last_period = quality.get("latest_source_period_end")
    if period_end and source_last_period and _as_utc(period_end) != _as_utc(
        _parse_datetime(source_last_period)
    ):
        reasons.append("source_summary_and_measurement_periods_disagree")

    # Preserve reason order while avoiding duplicate messages from repeated
    # history rows or multiple inputs failing the same check.
    reasons = list(dict.fromkeys(reasons))
    qualified = not reasons
    recommendation = "insufficient_evidence"
    if qualified and savings is not None and monthly_cost is not None:
        recommendation = (
            "review_battery_plan" if savings < monthly_cost else "no_review_indicated"
        )

    run_ids = sorted(
        {
            str(run_id)
            for run_id in [
                latest_snapshot.get("run_id"),
                *quality["measurement_source_run_ids"],
            ]
            if run_id not in (None, "")
        }
    )
    return {
        "evidence_contract_version": "1.0",
        "decision_month": decision_month,
        "evidence_status": "qualified" if qualified else "insufficient",
        "recommendation": recommendation,
        "recommendation_scope": "review_only",
        "actuation_authorized": False,
        "reason_codes": reasons,
        "estimated_monthly_battery_savings_eur": (
            float(savings) if savings is not None else None
        ),
        "effective_monthly_battery_cost_eur": (
            float(monthly_cost) if monthly_cost is not None else None
        ),
        "source_calculation_method": source_attrs.get("calculation_method"),
        "source_period_minutes": source_attrs.get("source_period_minutes"),
        "household_timezone": household_timezone,
        "source_tariff_snapshot_id": month_tariff_snapshot_id,
        "source_tariff_snapshot": month_tariff_snapshot,
        "source_tariff_snapshot_observed_at": latest_snapshot.get("ingested_at"),
        "source_last_period_end": (
            period_end.isoformat() if period_end is not None else None
        ),
        "source_quality": {
            key: value for key, value in quality.items() if key != "reason_codes"
        },
        "lineage": {
            "source_entity_ids": dict(sorted(entity_map.items())),
            "source_run_ids": run_ids,
            "source_report_ingested_at": latest_snapshot.get("ingested_at"),
        },
        "estimate_limitations": [
            "Battery savings are source-calculated estimates, not observed bill savings.",
            "Backfill status is not established by HA entity state history.",
            "A single month may not represent seasonal battery or tariff behavior.",
            "A review recommendation is not a tariff change, battery command, or authorization.",
            "Kotiakku reports an estimated battery-versus-no-battery site-cost comparison; it does not establish causal savings.",
        ],
    }


def assess_kotiakku_battery_plan_from_store(
    store: DuckDBStore,
    *,
    entity_map: dict[str, str],
    decision_month: str,
    household_timezone: str,
    assessed_at: datetime,
    freshness_limit: timedelta = timedelta(minutes=15),
) -> dict[str, Any]:
    """Read the configured HA histories and assess one closed month."""
    if _validate_profile(entity_map, decision_month, assessed_at):
        return assess_kotiakku_battery_plan_evidence(
            source_rows=[],
            measurement_rows=[],
            entity_map=entity_map,
            decision_month=decision_month,
            household_timezone=household_timezone,
            assessed_at=assessed_at,
            freshness_limit=freshness_limit,
        )

    table_exists = store.fetchall(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [FACT_HA_STATE_CHANGE_TABLE],
    )[0][0]
    if not table_exists:
        return _empty_assessment(
            decision_month, entity_map, "source_history_table_missing"
        )

    mapped_ids = sorted(set(entity_map.values()))
    placeholders = ", ".join("?" for _ in mapped_ids)
    rows = store.fetchall_dicts(
        f"""
        SELECT entity_id, state, attributes, changed_at, ingested_at, run_id
        FROM {FACT_HA_STATE_CHANGE_TABLE}
        WHERE entity_id IN ({placeholders})
        ORDER BY ingested_at, changed_at
        """,
        mapped_ids,
    )
    return assess_kotiakku_battery_plan_evidence(
        source_rows=rows,
        measurement_rows=rows,
        entity_map=entity_map,
        decision_month=decision_month,
        household_timezone=household_timezone,
        assessed_at=assessed_at,
        freshness_limit=freshness_limit,
    )


def _assess_measurement_coverage(
    *,
    measurement_rows: list[dict[str, Any]],
    entity_map: dict[str, str],
    decision_month: str,
    timezone: ZoneInfo,
    assessed_at: datetime,
) -> dict[str, Any]:
    month_start = datetime.strptime(decision_month, "%Y-%m").replace(tzinfo=timezone)
    month_end = _next_month(month_start)
    start_utc = month_start.astimezone(UTC)
    end_utc = month_end.astimezone(UTC)
    expected: set[datetime] = set()
    cursor = start_utc
    while cursor < end_utc:
        expected.add(cursor)
        cursor += _SAMPLE_INTERVAL

    entity_fields = {entity_id: field for field, entity_id in entity_map.items()}
    values: dict[datetime, dict[str, Decimal]] = defaultdict(dict)
    conflicts: set[datetime] = set()
    invalid_period_count = 0
    invalid_value_count = 0
    duplicate_count = 0
    unknown_scope_count = 0
    future_row_count = 0
    selected_runs: set[str] = set()
    latest_source_end: datetime | None = None

    for row in measurement_rows:
        field = entity_fields.get(str(row.get("entity_id", "")))
        if field not in KOTIAKKU_SAMPLE_FIELDS:
            continue
        row_time = _parse_datetime(row.get("ingested_at")) or _parse_datetime(
            row.get("changed_at")
        )
        if row_time is None:
            unknown_scope_count += 1
            continue
        if _as_utc(row_time) > _as_utc(assessed_at):
            future_row_count += 1
            continue
        attrs = _attributes(row)
        period_start = _parse_datetime(attrs.get("period_start"))
        period_end = _parse_datetime(attrs.get("period_end"))
        if period_start is None:
            row_changed_at = _parse_datetime(row.get("changed_at"))
            if row_changed_at is None:
                unknown_scope_count += 1
                continue
            row_month = row_changed_at.astimezone(timezone).strftime("%Y-%m")
            if row_month != decision_month:
                continue
            invalid_period_count += 1
            continue
        start_key = _as_utc(period_start)
        if period_end is None:
            if start_key in expected:
                invalid_period_count += 1
            continue
        end_key = _as_utc(period_end)
        if end_key - start_key != _SAMPLE_INTERVAL:
            if start_key in expected:
                invalid_period_count += 1
            continue
        if latest_source_end is None or end_key > latest_source_end:
            latest_source_end = end_key
        if start_key not in expected:
            continue
        expected_end = start_key + _SAMPLE_INTERVAL
        if expected_end != end_key:
            invalid_period_count += 1
            continue
        if attrs.get("unit_of_measurement") != _EXPECTED_UNITS[field]:
            invalid_value_count += 1
            continue
        state = str(row.get("state", "")).strip()
        if state.lower() in _UNAVAILABLE_STATES:
            invalid_value_count += 1
            continue
        value = _finite_decimal(state)
        if value is None:
            invalid_value_count += 1
            continue
        current = values[start_key].get(field)
        if current is not None:
            duplicate_count += 1
            if current != value:
                conflicts.add(start_key)
            continue
        values[start_key][field] = value
        if row.get("run_id") not in (None, ""):
            selected_runs.add(str(row["run_id"]))

    complete_windows = {
        period
        for period in expected
        if all(field in values.get(period, {}) for field in KOTIAKKU_SAMPLE_FIELDS)
        and period not in conflicts
    }
    complete_count = len(complete_windows)
    expected_count = len(expected)
    coverage = complete_count / expected_count if expected_count else 0.0
    reason_codes: list[str] = []
    if complete_count != expected_count:
        reason_codes.append("measurement_window_coverage_incomplete")
    if conflicts:
        reason_codes.append("conflicting_duplicate_measurements")
    if invalid_period_count:
        reason_codes.append("measurement_period_invalid")
    if invalid_value_count:
        reason_codes.append("measurement_value_or_unit_invalid")
    if unknown_scope_count:
        reason_codes.append("measurement_scope_timestamp_unknown")

    observed_periods = sorted(
        period for period in values if period in expected
    )
    latest_period_end = (
        (observed_periods[-1] + _SAMPLE_INTERVAL).isoformat()
        if observed_periods
        else None
    )
    return {
        "expected_window_count": expected_count,
        "complete_window_count": complete_count,
        "coverage_pct": round(coverage * 100, 4),
        "missing_window_count": expected_count - complete_count,
        "duplicate_snapshot_count": duplicate_count,
        "conflicting_window_count": len(conflicts),
        "invalid_period_record_count": invalid_period_count,
        "invalid_value_record_count": invalid_value_count,
        "unknown_scope_timestamp_count": unknown_scope_count,
        "future_record_count_ignored": future_row_count,
        "latest_period_end": latest_period_end,
        "latest_source_period_end": (
            latest_source_end.isoformat() if latest_source_end is not None else None
        ),
        "measurement_source_run_ids": sorted(selected_runs),
        "backfill_status": "not_established_from_ha_state_history",
        "source_window_counters": None,
        "reason_codes": reason_codes,
    }


def _effective_monthly_cost(attrs: dict[str, Any]) -> Decimal | None:
    direct_cost = _finite_decimal(attrs.get("battery_monthly_cost_eur"))
    if direct_cost is not None and direct_cost > 0:
        return direct_cost
    total_cost = _finite_decimal(attrs.get("battery_total_cost_eur"))
    if total_cost is None or total_cost <= 0:
        return None
    compensation = _finite_decimal(attrs.get("akkureservihyvitys_monthly_eur"))
    if compensation is None:
        return None
    return total_cost / Decimal("120") - compensation


def _latest_source_snapshot(
    rows: list[dict[str, Any]], *, assessed_at: datetime
) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in rows:
        ingested_at = _parse_datetime(row.get("ingested_at")) or _parse_datetime(
            row.get("changed_at")
        )
        if ingested_at is None:
            continue
        if _as_utc(ingested_at) > _as_utc(assessed_at):
            continue
        candidates.append((ingested_at, row))
    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def _attributes(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("attributes", row.get("attributes_json"))
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _as_utc(value: datetime | None) -> datetime:
    if value is None or value.tzinfo is None:
        raise ValueError("An aware timestamp is required")
    return value.astimezone(UTC)


def _finite_decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and math.isfinite(float(result)) else None


def _tariff_snapshot_id(snapshot: dict[str, Any]) -> str:
    """Match Kotiakku's stable ID over its sorted JSON tariff configuration."""
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _validate_profile(
    entity_map: dict[str, str], decision_month: str, assessed_at: datetime
) -> str | None:
    if set(entity_map) != KOTIAKKU_REQUIRED_ENTITY_MAP_KEYS:
        return "source_entity_mapping_incomplete"
    entity_ids = list(entity_map.values())
    if any(not entity_id.strip() for entity_id in entity_ids):
        return "source_entity_mapping_invalid"
    if len(set(entity_ids)) != len(entity_ids):
        return "source_entity_mapping_ambiguous"
    try:
        datetime.strptime(decision_month, "%Y-%m")
    except (TypeError, ValueError):
        return "decision_month_invalid"
    if assessed_at.tzinfo is None:
        return "assessment_timestamp_timezone_missing"
    return None


def _empty_assessment(
    decision_month: str, entity_map: dict[str, str], reason: str
) -> dict[str, Any]:
    return {
        "evidence_contract_version": "1.0",
        "decision_month": decision_month,
        "evidence_status": "insufficient",
        "recommendation": "insufficient_evidence",
        "recommendation_scope": "review_only",
        "actuation_authorized": False,
        "reason_codes": [reason],
        "estimated_monthly_battery_savings_eur": None,
        "effective_monthly_battery_cost_eur": None,
        "source_calculation_method": None,
        "source_period_minutes": None,
        "household_timezone": None,
        "source_tariff_snapshot_id": None,
        "source_tariff_snapshot": None,
        "source_tariff_snapshot_observed_at": None,
        "source_last_period_end": None,
        "source_quality": {
            "expected_window_count": 0,
            "complete_window_count": 0,
            "coverage_pct": 0.0,
            "missing_window_count": 0,
            "duplicate_snapshot_count": 0,
            "conflicting_window_count": 0,
            "invalid_period_record_count": 0,
            "invalid_value_record_count": 0,
            "unknown_scope_timestamp_count": 0,
            "future_record_count_ignored": 0,
            "latest_period_end": None,
            "backfill_status": "not_established_from_ha_state_history",
            "source_window_counters": None,
        },
        "lineage": {
            "source_entity_ids": dict(sorted(entity_map.items())),
            "source_run_ids": [],
            "source_report_ingested_at": None,
        },
        "estimate_limitations": [
            "The evidence is insufficient for a battery-plan review recommendation.",
            "No recommendation authorizes a tariff change, battery command, or other household action.",
        ],
    }


def _next_month(value: datetime) -> datetime:
    year = value.year + (value.month == 12)
    month = 1 if value.month == 12 else value.month + 1
    return value.replace(year=year, month=month, day=1)
