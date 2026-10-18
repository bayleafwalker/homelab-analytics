"""Battery-plan outcome publication: verdict guard, disclosures and lineage."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from packages.domains.homelab.pipelines.ha_models import FACT_HA_STATE_CHANGE_TABLE
from packages.domains.homelab.pipelines.ha_service import ensure_ha_storage
from packages.domains.utilities.battery_plan_decision import (
    BATTERY_PLAN_DECISION,
    BATTERY_PLAN_OUTCOME_PUBLICATION_KEY,
)
from packages.domains.utilities.pipelines.battery_plan_models import (
    VALUE_ROLES,
    VALUE_STATUSES,
    VERDICTS,
)
from packages.domains.utilities.pipelines.battery_plan_outcome import (
    BATTERY_PLAN_PROFILE_ENV,
    BatteryPlanProfileResolution,
    build_battery_plan_outcome_rows,
    load_battery_plan_profile,
    parse_battery_plan_profile,
)
from packages.pipelines.battery_plan_outcome_publication import (
    BATTERY_PLAN_PUBLICATION_KEYS,
    publish_battery_plan_outcome,
)
from packages.pipelines.household_decisions import get_decision_definition
from packages.pipelines.household_reporting import PUBLICATION_RELATIONS
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.ingestion_config import IngestionConfigRepository
from tests.test_kotiakku_evidence import _ENTITY_MAP, _TIMEZONE, _synthetic_histories

ROOT = Path(__file__).resolve().parents[1]


def _profile(**overrides: Any) -> BatteryPlanProfileResolution:
    document: dict[str, Any] = {
        "entity_map": _ENTITY_MAP,
        "household_timezone": _TIMEZONE,
        "decision_months": ["2026-01"],
    }
    document.update(overrides)
    return parse_battery_plan_profile(document)


def _store_with_history(
    *,
    savings: str = "30.0",
    monthly_cost: str = "49.0",
    drop_measurements: int = 0,
) -> tuple[DuckDBStore, datetime]:
    source_rows, measurement_rows = _synthetic_histories(
        savings=savings, monthly_cost=monthly_cost
    )
    if drop_measurements:
        measurement_rows = measurement_rows[drop_measurements:]
    store = DuckDBStore.memory()
    ensure_ha_storage(store)
    # Bulk-load a month of five-minute history via read_json; row-by-row
    # inserts of ~54k rows would dominate the test runtime.
    columns = ("entity_id", "canonical_id", "state", "attributes", "changed_at", "ingested_at", "run_id")
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "history.jsonl"
        with path.open("w") as handle:
            for row in [*measurement_rows, *source_rows]:
                record = {**row, "canonical_id": row["entity_id"]}
                handle.write(json.dumps({column: record[column] for column in columns}) + "\n")
        spec = ", ".join(f"'{column}': 'VARCHAR'" for column in columns)
        store.execute(
            f"INSERT INTO {FACT_HA_STATE_CHANGE_TABLE} ({', '.join(columns)}) "
            f"SELECT {', '.join(columns)} FROM read_json(?, format='newline_delimited', columns={{{spec}}})",
            [str(path)],
        )
    assessed_at = datetime.fromisoformat(source_rows[0]["ingested_at"]).astimezone(UTC)
    return store, assessed_at


def _service(
    store: DuckDBStore,
    *,
    assessed_at: datetime,
    resolution: BatteryPlanProfileResolution | None = None,
    control_plane: Any = None,
) -> TransformationService:
    resolved = resolution or _profile()
    return TransformationService(
        store,
        control_plane_store=control_plane,
        battery_plan_profile_loader=lambda: resolved,
        clock=lambda: assessed_at,
    )


def _values(service: TransformationService) -> dict[str, dict[str, Any]]:
    return {row["value_key"]: row for row in service.get_battery_plan_outcome_values()}


def test_qualified_month_below_cost_publishes_no_benefit_estimate_with_disclosures() -> None:
    store, assessed_at = _store_with_history()
    service = _service(store, assessed_at=assessed_at)

    assert service.refresh_publications([BATTERY_PLAN_OUTCOME_PUBLICATION_KEY]) == [
        BATTERY_PLAN_OUTCOME_PUBLICATION_KEY
    ]
    [row] = service.get_battery_plan_outcome()

    assert row["verdict"] == "no_benefit_estimated"
    assert row["evidence_status"] == "qualified"
    assert row["claim_basis"] == "source_estimate"
    assert row["source_recommendation"] == "review_battery_plan"
    assert row["actuation_authorized"] is False
    assert row["recommendation_scope"] == "review_only"
    assert float(row["coverage_pct"]) == 100.0
    assert row["freshness_status"] == "fresh"
    assert row["decision_key"] == BATTERY_PLAN_DECISION.decision_key
    assert row["decision_version"] == BATTERY_PLAN_DECISION.version
    assert float(row["estimated_net_benefit_eur"]) == pytest.approx(-19.0)
    assert json.loads(row["reason_codes_json"]) == []
    assert row["remediation"] is None
    assert json.loads(row["source_run_ids_json"]) == [
        "synthetic-economics-run",
        "synthetic-measurement-run",
    ]
    assert json.loads(row["tariff_snapshot_json"])["tariff_mode"] == "spot_only"
    assert row["assessment_id"].startswith("bpo_")

    values = _values(service)
    for value in values.values():
        assert value["value_status"] in VALUE_STATUSES
        assert value["value_role"] in VALUE_ROLES
        assert value["assessment_id"] == row["assessment_id"]
    # Actuals, estimates and assumptions stay distinct.
    assert values["grid_to_house_kwh"]["value_role"] == "actual"
    assert values["grid_to_house_kwh"]["value_status"] == "derived"
    assert values["estimated_savings_eur"]["value_status"] == "estimated"
    assert values["estimated_savings_eur"]["value_role"] == "estimate"
    assert values["effective_monthly_cost_eur"]["value_status"] == "user_entered"
    assert values["tariff.tariff_mode"]["value_text"] == "spot_only"
    assert values["tariff.tariff_mode"]["value_role"] == "assumption"
    # 0.3 kW over every window of a 31-day month.
    windows = row["expected_window_count"]
    assert float(values["grid_to_house_kwh"]["value_numeric"]) == pytest.approx(
        0.3 * windows * 5 / 60, rel=1e-6
    )
    # Not supplied by the source contract: disclosed as missing, never zero.
    assert values["net_site_cost_eur"]["is_missing"] is True
    assert values["net_site_cost_eur"]["value_numeric"] is None
    assert "net_site_cost_eur" in json.loads(row["missing_fields_json"])


def test_qualified_month_covering_cost_is_benefit_estimate_not_realized_savings() -> None:
    store, assessed_at = _store_with_history(savings="60.0")
    service = _service(store, assessed_at=assessed_at)
    service.refresh_battery_plan_outcome()

    [row] = service.get_battery_plan_outcome()
    assert row["verdict"] == "benefit_estimated"
    assert row["claim_basis"] == "source_estimate"
    limitations = json.loads(row["limitations_json"])
    assert any("not observed bill savings" in item for item in limitations)


def test_stale_source_cannot_produce_positive_claim_and_gives_remediation() -> None:
    store, assessed_at = _store_with_history(savings="60.0")
    service = _service(store, assessed_at=assessed_at + timedelta(hours=2))
    service.refresh_battery_plan_outcome()

    [row] = service.get_battery_plan_outcome()
    assert row["verdict"] == "insufficient_evidence"
    assert row["claim_basis"] == "none"
    assert row["source_recommendation"] == "insufficient_evidence"
    assert row["freshness_status"] == "stale"
    assert "source_measurements_stale" in json.loads(row["reason_codes_json"])
    assert "freshness limit" in row["remediation"]


def test_incomplete_coverage_cannot_produce_positive_claim() -> None:
    store, assessed_at = _store_with_history(savings="60.0", drop_measurements=6)
    service = _service(store, assessed_at=assessed_at)
    service.refresh_battery_plan_outcome()

    [row] = service.get_battery_plan_outcome()
    assert row["verdict"] == "insufficient_evidence"
    assert row["missing_window_count"] == 1
    assert "Backfill the missing five-minute" in row["remediation"]
    flow = _values(service)["grid_to_house_kwh"]
    assert f"{row['complete_window_count']} of {row['expected_window_count']}" in flow["note"]


def test_missing_cost_basis_stays_missing_not_zero() -> None:
    store, assessed_at = _store_with_history(monthly_cost="")
    # Also remove the total-cost fallback so no cost basis exists.
    store.execute(
        f"UPDATE {FACT_HA_STATE_CHANGE_TABLE} SET attributes = "
        "replace(attributes, '\"battery_total_cost_eur\": \"6000.0\"', "
        "'\"battery_total_cost_eur\": null') WHERE entity_id = ?",
        [_ENTITY_MAP["battery_savings"]],
    )
    service = _service(store, assessed_at=assessed_at)
    service.refresh_battery_plan_outcome()

    [row] = service.get_battery_plan_outcome()
    assert row["verdict"] == "insufficient_evidence"
    assert row["effective_monthly_cost_eur"] is None
    assert row["estimated_net_benefit_eur"] is None
    values = _values(service)
    assert values["effective_monthly_cost_eur"]["is_missing"] is True
    assert values["effective_monthly_cost_eur"]["value_numeric"] is None
    assert values["battery_total_cost_eur"]["is_missing"] is True
    assert "battery_cost_basis_missing" in json.loads(row["reason_codes_json"])


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason_codes": ["measurement_window_coverage_incomplete"]},
        {"source_quality": {"coverage_pct": 99.9}},
        {"source_last_period_end": "2026-01-01T00:00:00+00:00"},
        {"source_last_period_end": None},
        {"evidence_status": "insufficient"},
    ],
)
def test_verdict_guard_refuses_positive_claim_on_any_weak_input(
    overrides: dict[str, Any],
) -> None:
    assessed_at = datetime(2026, 2, 1, 0, 5, tzinfo=UTC)
    assessment: dict[str, Any] = {
        "evidence_status": "qualified",
        "recommendation": "no_review_indicated",
        "reason_codes": [],
        "estimated_monthly_battery_savings_eur": 90.0,
        "effective_monthly_battery_cost_eur": 10.0,
        "source_last_period_end": "2026-02-01T00:00:00+00:00",
        "source_quality": {"coverage_pct": 100.0},
    }
    assessment.update(overrides)

    summary, _ = build_battery_plan_outcome_rows(
        assessment,
        decision_month="2026-01",
        assessed_at=assessed_at,
        profile_status="configured",
        freshness_limit_minutes=15,
    )
    assert summary["verdict"] == "insufficient_evidence"
    assert summary["claim_basis"] == "none"
    assert summary["remediation"]
    assert summary["verdict"] in VERDICTS


def test_unconfigured_profile_publishes_insufficient_row_with_remediation() -> None:
    store = DuckDBStore.memory()
    assessed_at = datetime(2026, 3, 10, 12, tzinfo=UTC)
    service = _service(
        store,
        assessed_at=assessed_at,
        resolution=load_battery_plan_profile({}),
    )
    service.refresh_battery_plan_outcome()

    [row] = service.get_battery_plan_outcome()
    assert row["profile_status"] == "unconfigured"
    assert row["decision_month"] == "2026-02"
    assert row["verdict"] == "insufficient_evidence"
    assert BATTERY_PLAN_PROFILE_ENV in row["remediation"]


def test_profile_loader_reads_json_file_and_rejects_invalid_documents() -> None:
    with TemporaryDirectory() as temp_dir:
        good = Path(temp_dir) / "profile.json"
        good.write_text(
            json.dumps({"entity_map": _ENTITY_MAP, "household_timezone": _TIMEZONE})
        )
        bad = Path(temp_dir) / "bad.json"
        bad.write_text("{not json")
        resolved = load_battery_plan_profile({BATTERY_PLAN_PROFILE_ENV: str(good)})
        assert resolved.status == "configured"
        assert resolved.profile is not None
        assert resolved.profile.household_timezone == _TIMEZONE
        assert load_battery_plan_profile({BATTERY_PLAN_PROFILE_ENV: str(bad)}).status == "invalid"
    assert parse_battery_plan_profile({"entity_map": "x"}).status == "invalid"
    assert parse_battery_plan_profile(
        {"entity_map": {}, "household_timezone": "UTC", "freshness_limit_minutes": 0}
    ).status == "invalid"


def test_publish_records_reporting_lineage_from_source_runs() -> None:
    store, assessed_at = _store_with_history()
    with TemporaryDirectory() as temp_dir:
        control_plane = IngestionConfigRepository(Path(temp_dir) / "config.db")
        service = _service(store, assessed_at=assessed_at, control_plane=control_plane)
        reporting = ReportingService(service, control_plane_store=control_plane)

        result = publish_battery_plan_outcome(service, reporting, control_plane=control_plane)

        assert result.refreshed == [BATTERY_PLAN_OUTCOME_PUBLICATION_KEY]
        assert result.lineage_run_ids == [
            "synthetic-economics-run",
            "synthetic-measurement-run",
        ]
        assert result.outcomes[0]["verdict"] == "no_benefit_estimated"
        for key in BATTERY_PLAN_PUBLICATION_KEYS:
            lineage = control_plane.list_source_lineage(target_name=key)
            assert {record.input_run_id for record in lineage} == set(result.lineage_run_ids)
            assert {record.target_layer for record in lineage} == {"reporting"}
            assert {record.source_system for record in lineage} == {"home_assistant"}
            snapshots = control_plane.list_publication_confidence_snapshots(
                publication_key=key
            )
            # Confidence sees the recorded inputs; without run metadata the
            # signals are unknown, so the verdict must not be trustworthy.
            latest = max(snapshots, key=lambda snapshot: snapshot.assessed_at)
            # Confidence keeps the latest run per source system.
            contributing = set(latest.contributing_run_ids or ())
            assert contributing and contributing <= set(result.lineage_run_ids)
            assert latest.confidence_verdict != "trustworthy"


def test_decision_definition_is_registered_and_bound_to_publication() -> None:
    definition = get_decision_definition("kotiakku_battery_plan_review")
    assert definition is BATTERY_PLAN_DECISION
    assert definition.subject_publication_key in PUBLICATION_RELATIONS
    for key in definition.supporting_publication_keys:
        assert key in PUBLICATION_RELATIONS
    assert definition.decision_maker_role == "operator"
    assert any(option.is_non_decision for option in definition.outcome_options)
    assert definition.insufficient_evidence_criteria
    assert definition.evidence_that_could_change_decision


def test_battery_plan_modules_have_no_actuation_or_credential_path() -> None:
    sources = [
        ROOT / "packages/domains/utilities/pipelines/kotiakku_evidence.py",
        ROOT / "packages/domains/utilities/pipelines/battery_plan_outcome.py",
        ROOT / "packages/domains/utilities/battery_plan_decision.py",
        ROOT / "packages/pipelines/battery_plan_outcome_publication.py",
    ]
    forbidden = ("call_service", "/api/services", "HA_TOKEN", "requests.", "httpx", "mqtt")
    for path in sources:
        text = path.read_text()
        for token in forbidden:
            assert token not in text, f"{path.name} contains {token!r}"


def test_worker_exposes_refresh_battery_plan_outcome_command() -> None:
    from apps.worker.command_handlers import build_worker_command_handlers
    from apps.worker.command_parser import build_parser

    assert "refresh-battery-plan-outcome" in build_worker_command_handlers()
    assert build_parser().parse_args(["refresh-battery-plan-outcome"]).command == (
        "refresh-battery-plan-outcome"
    )
