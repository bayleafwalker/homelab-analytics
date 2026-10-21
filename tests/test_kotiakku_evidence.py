"""Synthetic contract tests for read-only Kotiakku evidence qualification."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from packages.domains.homelab.pipelines.ha_service import ensure_ha_storage, ingest_ha_states
from packages.domains.utilities.pipelines.kotiakku_evidence import (
    KOTIAKKU_CALCULATION_METHOD,
    KOTIAKKU_EVIDENCE_CONTRACT_VERSION,
    KOTIAKKU_SAMPLE_FIELDS,
    assess_kotiakku_battery_plan_evidence,
    assess_kotiakku_battery_plan_from_store,
)
from packages.storage.duckdb_store import DuckDBStore

_DECISION_MONTH = "2026-01"
_TIMEZONE = "Europe/Helsinki"
_ENTITY_MAP = {
    "grid_power_kw": "sensor.synthetic_grid_power",
    "solar_to_grid_kw": "sensor.synthetic_solar_to_grid",
    "solar_to_battery_kw": "sensor.synthetic_solar_to_battery",
    "grid_to_house_kw": "sensor.synthetic_grid_to_house",
    "battery_to_house_kw": "sensor.synthetic_battery_to_house",
    "spot_price_cents_per_kwh": "sensor.synthetic_spot_price",
    "battery_savings": "sensor.synthetic_total_battery_savings",
}
_FIELD_VALUES = {
    "grid_power_kw": "0.4",
    "solar_to_grid_kw": "0.1",
    "solar_to_battery_kw": "0.2",
    "grid_to_house_kw": "0.3",
    "battery_to_house_kw": "0.2",
    "spot_price_cents_per_kwh": "8.0",
}
_TARIFF_SNAPSHOT = {
    "tariff_mode": "spot_only",
    "grid_import_transfer_fee_cents_per_kwh": 5.0,
}


def _tariff_snapshot_id(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _synthetic_histories(
    *,
    savings: str = "30.0",
    monthly_cost: str = "49.0",
    decision_month: str = _DECISION_MONTH,
    timezone_name: str = _TIMEZONE,
    extra_attrs: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build explicitly synthetic, complete January source histories."""
    timezone = ZoneInfo(timezone_name)
    year, month = (int(part) for part in decision_month.split("-"))
    local_start = datetime(year, month, 1, tzinfo=timezone)
    end_month = 1 if month == 12 else month + 1
    end_year = year + (month == 12)
    local_end = datetime(end_year, end_month, 1, tzinfo=timezone)
    expected_window_count = int(
        (local_end.astimezone(UTC) - local_start.astimezone(UTC)).total_seconds()
        // 300
    )
    cursor = local_start.astimezone(UTC)
    end_utc = local_end.astimezone(UTC)
    measurement_rows: list[dict[str, Any]] = []
    last_period_end: datetime | None = None
    while cursor < end_utc:
        period_start = cursor.astimezone(timezone)
        period_end = (cursor + timedelta(minutes=5)).astimezone(timezone)
        for field in KOTIAKKU_SAMPLE_FIELDS:
            unit = "c/kWh" if field == "spot_price_cents_per_kwh" else "kW"
            measurement_rows.append(
                {
                    "entity_id": _ENTITY_MAP[field],
                    "state": _FIELD_VALUES[field],
                    "attributes": json.dumps(
                        {
                            "period_start": period_start.isoformat(),
                            "period_end": period_end.isoformat(),
                            "unit_of_measurement": unit,
                        }
                    ),
                    "changed_at": period_end.isoformat(),
                    "ingested_at": period_end.isoformat(),
                    "run_id": "synthetic-measurement-run",
                }
            )
        last_period_end = period_end
        cursor += timedelta(minutes=5)

    assert last_period_end is not None
    assessed_at = (last_period_end + timedelta(minutes=5)).isoformat()
    source_rows: list[dict[str, Any]] = [
        {
            "entity_id": _ENTITY_MAP["battery_savings"],
            "state": savings,
            "attributes": json.dumps(
                {
                    "evidence_contract_version": KOTIAKKU_EVIDENCE_CONTRACT_VERSION,
                    "calculation_method": KOTIAKKU_CALCULATION_METHOD,
                    "source_period_minutes": 5,
                    "last_period_end": last_period_end.isoformat(),
                    "tariff_snapshot_id": _tariff_snapshot_id(_TARIFF_SNAPSHOT),
                    "tariff_snapshot": _TARIFF_SNAPSHOT,
                    "monthly_battery_savings_eur": {decision_month: savings},
                    "monthly_battery_evidence": {
                        decision_month: {
                            "processed_window_count": expected_window_count,
                            "savings_window_count": expected_window_count,
                            "skipped_savings_window_count": 0,
                            "estimated_savings_eur": savings,
                            "tariff_snapshot_id": _tariff_snapshot_id(
                                _TARIFF_SNAPSHOT
                            ),
                            "tariff_snapshot": _TARIFF_SNAPSHOT,
                        }
                    },
                    "battery_monthly_cost_eur": monthly_cost,
                    "battery_total_cost_eur": "6000.0",
                    "akkureservihyvitys_monthly_eur": "10.0",
                    "skipped_windows": 0,
                    **(extra_attrs or {}),
                }
            ),
            "changed_at": last_period_end.isoformat(),
            "ingested_at": assessed_at,
            "run_id": "synthetic-economics-run",
        }
    ]
    return source_rows, measurement_rows


def _assess(
    source_rows: list[dict[str, object]],
    measurement_rows: list[dict[str, object]],
    *,
    assessed_at: datetime | None = None,
    decision_month: str = _DECISION_MONTH,
    household_timezone: str = _TIMEZONE,
) -> dict[str, Any]:
    latest = datetime.fromisoformat(
        str(json.loads(str(source_rows[-1]["attributes"]))["last_period_end"])
    )
    now = assessed_at or latest + timedelta(minutes=5)
    return assess_kotiakku_battery_plan_evidence(
        source_rows=source_rows,
        measurement_rows=measurement_rows,
        entity_map=_ENTITY_MAP,
        decision_month=decision_month,
        household_timezone=household_timezone,
        assessed_at=now,
    )


def test_complete_synthetic_month_recommends_review_below_monthly_cost() -> None:
    source_rows, measurement_rows = _synthetic_histories()

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "qualified"
    assert result["recommendation"] == "review_battery_plan"
    assert result["recommendation_scope"] == "review_only"
    assert result["actuation_authorized"] is False
    assert result["estimated_monthly_battery_savings_eur"] == 30.0
    assert result["effective_monthly_battery_cost_eur"] == 49.0
    assert result["source_tariff_snapshot_id"] == _tariff_snapshot_id(
        _TARIFF_SNAPSHOT
    )
    source_quality = result["source_quality"]
    assert isinstance(source_quality, dict)
    assert source_quality["coverage_pct"] == 100.0
    assert source_quality["expected_window_count"] == 8_928
    assert source_quality["source_window_counters"] == {
        "processed_window_count": 8_928,
        "savings_window_count": 8_928,
        "skipped_savings_window_count": 0,
        "estimated_savings_eur": "30.0",
        "tariff_snapshot_id": _tariff_snapshot_id(_TARIFF_SNAPSHOT),
        "tariff_snapshot": _TARIFF_SNAPSHOT,
    }
    assert result["reason_codes"] == []


def test_complete_synthetic_month_declines_review_when_estimate_covers_cost() -> None:
    source_rows, measurement_rows = _synthetic_histories(savings="75.0")

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "qualified"
    assert result["recommendation"] == "no_review_indicated"
    assert result["actuation_authorized"] is False


def test_spring_dst_month_uses_local_calendar_window_count() -> None:
    month = "2026-03"
    source_rows, measurement_rows = _synthetic_histories(decision_month=month)
    result = _assess(source_rows, measurement_rows, decision_month=month)
    quality = result["source_quality"]
    assert result["evidence_status"] == "qualified"
    assert quality["expected_window_count"] == 8_916
    assert quality["complete_window_count"] == 8_916


def test_missing_ha_sample_window_is_corroboration_not_a_gate() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    measurement_rows.pop(0)

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "qualified"
    assert "measurement_window_coverage_incomplete" not in result["reason_codes"]
    assert result["actuation_authorized"] is False
    source_quality = result["source_quality"]
    assert isinstance(source_quality, dict)
    assert source_quality["missing_window_count"] == 1
    assert source_quality["coverage_basis"] == "source_window_counters"
    assert "measurement_window_coverage_incomplete" in source_quality[
        "corroboration_reason_codes"
    ]


def test_stale_source_freshness_refuses_recommendation() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    result = _assess(
        source_rows,
        measurement_rows,
        assessed_at=datetime(2026, 2, 1, 1, 0, tzinfo=UTC),
    )
    assert result["recommendation"] == "insufficient_evidence"
    assert "source_measurements_stale" in result["reason_codes"]


def test_legacy_source_without_published_cost_uses_fallback_derivation() -> None:
    """Integrations before 1.6.0 publish no effective cost; HLA derives it."""
    source_rows, measurement_rows = _synthetic_histories()
    result = _assess(source_rows, measurement_rows)
    assert result["effective_monthly_battery_cost_eur"] == 49.0
    assert result["battery_cost_basis"]["method"] == "direct_monthly_cost"
    assert result["battery_cost_basis"]["battery_cost_basis"] is None


def test_published_effective_cost_is_preferred_over_derivation() -> None:
    """Kotiakku >= 1.6.0: the gross instalment is not used as the cost."""
    source_rows, measurement_rows = _synthetic_histories(
        savings="21.78",
        monthly_cost="65.82",
        extra_attrs={
            "effective_monthly_cost_eur": 15.82,
            "battery_cost_basis": "instalment",
        },
    )
    result = _assess(source_rows, measurement_rows)
    assert result["evidence_status"] == "qualified"
    assert result["effective_monthly_battery_cost_eur"] == 15.82
    assert result["recommendation"] == "no_review_indicated"
    basis = result["battery_cost_basis"]
    assert basis["method"] == "source_effective_monthly_cost"
    assert basis["battery_cost_basis"] == "instalment"
    assert basis["battery_monthly_cost_eur"] == 65.82


def test_published_negative_effective_cost_is_kept() -> None:
    """A paid-off instalment nets to -compensation; zero savings still covers it."""
    source_rows, measurement_rows = _synthetic_histories(
        savings="0.0",
        monthly_cost="0.0",
        extra_attrs={
            "effective_monthly_cost_eur": -50.0,
            "battery_cost_basis": "instalment",
        },
    )
    result = _assess(source_rows, measurement_rows)
    assert result["effective_monthly_battery_cost_eur"] == -50.0
    assert result["recommendation"] == "no_review_indicated"
    assert result["battery_cost_basis"]["method"] == "source_effective_monthly_cost"


def test_published_null_effective_cost_does_not_fall_back() -> None:
    """A source that publishes an unknown cost is not re-derived by HLA."""
    source_rows, measurement_rows = _synthetic_histories(
        extra_attrs={
            "effective_monthly_cost_eur": None,
            "battery_cost_basis": "total_cost",
        },
    )
    result = _assess(source_rows, measurement_rows)
    assert result["effective_monthly_battery_cost_eur"] is None
    assert result["recommendation"] == "insufficient_evidence"
    assert "battery_cost_basis_missing" in result["reason_codes"]
    assert result["battery_cost_basis"]["method"] is None


def test_missing_battery_cost_basis_refuses_recommendation() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    attrs = json.loads(str(source_rows[0]["attributes"]))
    attrs["battery_monthly_cost_eur"] = 0
    attrs["battery_total_cost_eur"] = 0
    source_rows[0]["attributes"] = json.dumps(attrs)
    result = _assess(source_rows, measurement_rows)
    assert result["recommendation"] == "insufficient_evidence"
    assert "battery_cost_basis_missing" in result["reason_codes"]


def test_tariff_snapshot_signature_mismatch_refuses_recommendation() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    attrs = json.loads(str(source_rows[0]["attributes"]))
    attrs["monthly_battery_evidence"][_DECISION_MONTH]["tariff_snapshot"] = {
        **_TARIFF_SNAPSHOT,
        "grid_import_transfer_fee_cents_per_kwh": 7.0,
    }
    source_rows[0]["attributes"] = json.dumps(attrs)
    result = _assess(source_rows, measurement_rows)
    assert result["recommendation"] == "insufficient_evidence"
    assert "monthly_tariff_signature_mismatch" in result["reason_codes"]


def test_december_history_does_not_poison_january_contract_qualification() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    legacy_source = dict(source_rows[0])
    legacy_source.update(
        changed_at="2025-12-31T23:55:00+02:00",
        ingested_at="2025-12-31T23:56:00+02:00",
    )
    legacy_source["attributes"] = json.dumps(
        {"last_period_end": "2025-12-31T23:55:00+02:00", "tariff_snapshot_id": "old"}
    )
    legacy_measurement = dict(measurement_rows[0])
    legacy_measurement.update(
        changed_at="2025-12-31T23:55:00+02:00",
        ingested_at="2025-12-31T23:56:00+02:00",
        attributes=json.dumps({"period_start": "not-a-date"}),
        state="unknown",
    )
    source_rows.insert(0, legacy_source)
    measurement_rows.append(legacy_measurement)

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "qualified"
    assert result["recommendation"] == "review_battery_plan"


def test_later_month_tariff_does_not_rewrite_selected_month_snapshot() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    later_tariff = {
        "tariff_mode": "flat",
        "grid_import_transfer_fee_cents_per_kwh": 8.0,
    }
    current_period_start = datetime(2026, 3, 1, 0, 0, tzinfo=ZoneInfo(_TIMEZONE))
    current_period_end = current_period_start + timedelta(minutes=5)
    attrs = json.loads(str(source_rows[0]["attributes"]))
    attrs["last_period_end"] = current_period_end.isoformat()
    attrs["tariff_snapshot"] = later_tariff
    attrs["tariff_snapshot_id"] = _tariff_snapshot_id(later_tariff)
    later_snapshot = dict(source_rows[0])
    later_snapshot.update(
        attributes=json.dumps(attrs),
        changed_at=current_period_end.isoformat(),
        ingested_at=current_period_end.isoformat(),
        run_id="synthetic-later-tariff-run",
    )
    source_rows.append(later_snapshot)
    for field in KOTIAKKU_SAMPLE_FIELDS:
        measurement_rows.append(
            {
                "entity_id": _ENTITY_MAP[field],
                "state": _FIELD_VALUES[field],
                "attributes": json.dumps(
                    {
                        "period_start": current_period_start.isoformat(),
                        "period_end": current_period_end.isoformat(),
                        "unit_of_measurement": (
                            "c/kWh" if field == "spot_price_cents_per_kwh" else "kW"
                        ),
                    }
                ),
                "changed_at": current_period_end.isoformat(),
                "ingested_at": current_period_end.isoformat(),
                "run_id": "synthetic-later-measurement-run",
            }
        )

    result = _assess(
        source_rows,
        measurement_rows,
        assessed_at=current_period_end + timedelta(minutes=5),
    )

    assert result["evidence_status"] == "qualified"
    assert result["source_tariff_snapshot"] == _TARIFF_SNAPSHOT
    assert result["source_tariff_snapshot_id"] == _tariff_snapshot_id(
        _TARIFF_SNAPSHOT
    )


def test_future_ingested_source_and_measurement_rows_are_not_used() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    future_source = dict(source_rows[0])
    future_source.update(
        changed_at="2026-02-01T01:00:00+02:00",
        ingested_at="2026-02-01T01:00:00+02:00",
        state="999.0",
        run_id="synthetic-future-source-run",
    )
    source_rows.append(future_source)
    future_measurement = dict(measurement_rows[-1])
    future_measurement.update(
        changed_at="2026-02-01T01:00:00+02:00",
        ingested_at="2026-02-01T01:00:00+02:00",
        state="999.0",
        run_id="synthetic-future-measurement-run",
    )
    measurement_rows.append(future_measurement)

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "qualified"
    assert result["estimated_monthly_battery_savings_eur"] == 30.0
    assert result["source_quality"]["future_record_count_ignored"] == 1
    assert result["lineage"]["source_run_ids"] == [
        "synthetic-economics-run",
        "synthetic-measurement-run",
    ]


def test_conflicting_monthly_savings_fields_refuse_qualification() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    attrs = json.loads(source_rows[0]["attributes"])
    attrs["monthly_battery_savings_eur"][_DECISION_MONTH] = "31.0"
    source_rows[0]["attributes"] = json.dumps(attrs)

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "insufficient"
    assert result["recommendation"] == "insufficient_evidence"
    assert "monthly_savings_and_window_evidence_disagree" in result["reason_codes"]


def test_measurement_with_unknown_scope_timestamp_preserves_uncertainty() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    measurement_rows.append(
        {
            "entity_id": _ENTITY_MAP["grid_power_kw"],
            "state": "0.1",
            "attributes": json.dumps({"unit_of_measurement": "kW"}),
        }
    )
    result = _assess(source_rows, measurement_rows)
    assert "measurement_scope_timestamp_unknown" not in result["reason_codes"]
    assert "measurement_scope_timestamp_unknown" in result["source_quality"][
        "corroboration_reason_codes"
    ]


def test_source_snapshot_with_unknown_ingestion_scope_preserves_uncertainty() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    unscoped_source = dict(source_rows[0])
    unscoped_source.pop("changed_at")
    unscoped_source.pop("ingested_at")
    source_rows.append(unscoped_source)

    result = _assess(source_rows, measurement_rows)

    assert result["evidence_status"] == "insufficient"
    assert "source_history_timestamp_unknown" in result["reason_codes"]


def test_incomplete_monthly_window_counters_refuse_recommendation() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    attrs = json.loads(str(source_rows[0]["attributes"]))
    attrs["monthly_battery_evidence"][_DECISION_MONTH][
        "skipped_savings_window_count"
    ] = 1
    source_rows[0]["attributes"] = json.dumps(attrs)
    result = _assess(source_rows, measurement_rows)
    assert result["recommendation"] == "insufficient_evidence"
    assert "monthly_window_counters_incomplete" in result["reason_codes"]


def test_conflicting_ha_samples_are_reported_as_corroboration() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    conflicting = dict(measurement_rows[0])
    conflicting["state"] = "9.9"
    measurement_rows.append(conflicting)

    result = _assess(source_rows, measurement_rows)

    assert "conflicting_duplicate_measurements" not in result["reason_codes"]
    assert "conflicting_duplicate_measurements" in result["source_quality"][
        "corroboration_reason_codes"
    ]
    assert result["actuation_authorized"] is False


def test_summary_entity_alone_qualifies_on_source_counters() -> None:
    source_rows, _ = _synthetic_histories()

    result = assess_kotiakku_battery_plan_evidence(
        source_rows=source_rows,
        measurement_rows=[],
        entity_map={"battery_savings": _ENTITY_MAP["battery_savings"]},
        decision_month=_DECISION_MONTH,
        household_timezone=_TIMEZONE,
        assessed_at=datetime(2026, 2, 1, 0, 5, tzinfo=ZoneInfo(_TIMEZONE)),
    )

    assert result["evidence_status"] == "qualified", result["reason_codes"]
    quality = result["source_quality"]
    assert quality["sample_corroboration"] == "not_mapped"
    assert quality["corroboration_reason_codes"] == []
    assert quality["source_coverage_pct"] == 100.0


def _with_skipped(source_rows: list[dict[str, object]], skipped: int) -> None:
    attrs = json.loads(str(source_rows[0]["attributes"]))
    counters = attrs["monthly_battery_evidence"][_DECISION_MONTH]
    counters["skipped_savings_window_count"] = skipped
    counters["savings_window_count"] = counters["processed_window_count"] - skipped
    source_rows[0]["attributes"] = json.dumps(attrs)


@pytest.mark.parametrize(("skipped", "status"), [(8, "qualified"), (9, "insufficient")])
def test_declared_skip_tolerance_bounds_qualification(skipped: int, status: str) -> None:
    source_rows, measurement_rows = _synthetic_histories()
    _with_skipped(source_rows, skipped)

    result = assess_kotiakku_battery_plan_evidence(
        source_rows=source_rows,
        measurement_rows=measurement_rows,
        entity_map=_ENTITY_MAP,
        decision_month=_DECISION_MONTH,
        household_timezone=_TIMEZONE,
        assessed_at=datetime(2026, 2, 1, 0, 5, tzinfo=ZoneInfo(_TIMEZONE)),
        max_skipped_window_ratio=Decimal("0.001"),
    )

    assert result["evidence_status"] == status
    assert result["source_quality"]["allowed_skipped_window_count"] == 8
    if status == "qualified":
        assert any("excludes 8 source window" in line for line in result["estimate_limitations"])
    else:
        assert "monthly_window_counters_incomplete" in result["reason_codes"]


def test_savings_count_must_equal_processed_minus_skipped() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    _with_skipped(source_rows, 2)
    attrs = json.loads(str(source_rows[0]["attributes"]))
    attrs["monthly_battery_evidence"][_DECISION_MONTH]["savings_window_count"] += 1
    source_rows[0]["attributes"] = json.dumps(attrs)

    result = assess_kotiakku_battery_plan_evidence(
        source_rows=source_rows,
        measurement_rows=measurement_rows,
        entity_map=_ENTITY_MAP,
        decision_month=_DECISION_MONTH,
        household_timezone=_TIMEZONE,
        assessed_at=datetime(2026, 2, 1, 0, 5, tzinfo=ZoneInfo(_TIMEZONE)),
        max_skipped_window_ratio=Decimal("0.001"),
    )

    assert "monthly_window_counters_incomplete" in result["reason_codes"]


def test_unmapped_source_is_unknown_and_has_no_recommendation() -> None:
    source_rows, measurement_rows = _synthetic_histories()
    incomplete_map = {
        key: value for key, value in _ENTITY_MAP.items() if key != "battery_savings"
    }

    result = assess_kotiakku_battery_plan_evidence(
        source_rows=source_rows,
        measurement_rows=measurement_rows,
        entity_map=incomplete_map,
        decision_month=_DECISION_MONTH,
        household_timezone=_TIMEZONE,
        assessed_at=datetime(2026, 2, 1, 0, 5, tzinfo=ZoneInfo(_TIMEZONE)),
    )

    assert result["evidence_status"] == "insufficient"
    assert result["recommendation"] == "insufficient_evidence"
    assert result["reason_codes"] == ["source_entity_mapping_incomplete"]


def test_from_store_reads_ha_history_and_refuses_partial_month() -> None:
    store = DuckDBStore.memory()
    ensure_ha_storage(store)
    period_start = "2026-01-31T23:50:00+02:00"
    period_end = "2026-01-31T23:55:00+02:00"
    states = [
        {
            "entity_id": entity_id,
            "state": _FIELD_VALUES[field],
            "last_changed": period_end,
            "last_updated": period_end,
            "attributes": {
                "period_start": period_start,
                "period_end": period_end,
                "unit_of_measurement": (
                    "c/kWh" if field == "spot_price_cents_per_kwh" else "kW"
                ),
            },
        }
        for field, entity_id in _ENTITY_MAP.items()
        if field != "battery_savings"
    ]
    states.append(
        {
            "entity_id": _ENTITY_MAP["battery_savings"],
            "state": "30.0",
            "last_changed": period_end,
            "last_updated": period_end,
            "attributes": {
                "evidence_contract_version": KOTIAKKU_EVIDENCE_CONTRACT_VERSION,
                "calculation_method": KOTIAKKU_CALCULATION_METHOD,
                "source_period_minutes": 5,
                "last_period_end": period_end,
                "tariff_snapshot_id": _tariff_snapshot_id(_TARIFF_SNAPSHOT),
                "tariff_snapshot": _TARIFF_SNAPSHOT,
                "monthly_battery_savings_eur": {_DECISION_MONTH: "30.0"},
                "battery_monthly_cost_eur": "49.0",
                "battery_total_cost_eur": "6000.0",
                "akkureservihyvitys_monthly_eur": "10.0",
            },
        }
    )
    ingest_ha_states(store, states, run_id="synthetic-ha-run")

    result = assess_kotiakku_battery_plan_from_store(
        store,
        entity_map=_ENTITY_MAP,
        decision_month=_DECISION_MONTH,
        household_timezone=_TIMEZONE,
        assessed_at=datetime.now(UTC) + timedelta(minutes=1),
    )

    assert result["recommendation"] == "insufficient_evidence"
    assert "monthly_window_counters_missing" in result["reason_codes"]
    assert "measurement_window_coverage_incomplete" in result["source_quality"][
        "corroboration_reason_codes"
    ]
    lineage = result["lineage"]
    assert isinstance(lineage, dict)
    assert lineage["source_run_ids"] == ["synthetic-ha-run"]
