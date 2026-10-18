"""Wallboard panels: service health, room readings, event feed, power series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.use_cases.wallboard import (
    build_device_readings,
    build_event_feed,
    build_power_series,
    build_service_health,
    normalize_service_status,
    select_energy_meter,
)
from packages.domains.finance.pipelines.account_transaction_service import (
    AccountTransactionService,
)
from packages.domains.homelab.pipelines.transformation_homelab import (
    refresh_service_health_current,
)
from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.platform.action_proposals import ActionProposalRegistry
from packages.storage.duckdb_store import DuckDBStore
from packages.storage.run_metadata import (
    IngestionRunCreate,
    IngestionRunStatus,
    RunMetadataRepository,
)

NOW = datetime(2026, 10, 18, 12, 30, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def test_normalize_service_status() -> None:
    assert normalize_service_status("running") == "up"
    assert normalize_service_status("Degraded") == "degraded"
    assert normalize_service_status("stopped") == "down"
    assert normalize_service_status("mystery") == "unknown"
    assert normalize_service_status(None) == "unknown"


def test_service_health_joins_workload_metrics_and_flags_stale() -> None:
    services = [
        {
            "service_id": "ha",
            "service_name": "Home Assistant",
            "host": "nuc",
            "state": "running",
            "uptime_seconds": 3600,
            "recorded_at": datetime(2026, 10, 18, 12, 20),  # naive -> UTC
        },
        {
            "service_id": "nas",
            "service_name": "NAS",
            "host": "",
            "state": "stopped",
            "uptime_seconds": None,
            "recorded_at": "2026-10-17T08:00:00+00:00",
        },
    ]
    workloads = [
        {"workload_id": "ha", "avg_cpu_pct_7d": "12.345", "avg_mem_gb_7d": "1.5"},
        {"workload_id": "other", "display_name": "NAS", "host": "x", "avg_cpu_pct_7d": 1},
    ]
    rows = build_service_health(services, workloads, now=NOW)

    # Down sorts first.
    assert [row["service_id"] for row in rows] == ["nas", "ha"]
    nas, ha = rows
    assert ha["status"] == "up"
    assert ha["host"] == "nuc"
    assert ha["cpu_pct"] == 12.35
    assert ha["mem_gb"] == 1.5
    assert ha["metrics_window"] == "7d_avg"
    assert ha["stale"] is False
    # The service reports no host, so a same-name workload on any host matches.
    assert nas["cpu_pct"] == 1.0
    assert nas["status"] == "down"
    assert nas["host"] is None
    assert nas["uptime_seconds"] is None
    assert nas["stale"] is True


def test_service_health_without_matching_workload_keeps_metrics_unknown() -> None:
    rows = build_service_health(
        [{"service_id": "a", "service_name": "A", "host": "h1", "state": "ok",
          "recorded_at": NOW}],
        [{"workload_id": "b", "display_name": "A", "host": "h2", "avg_cpu_pct_7d": 5}],
        now=NOW,
    )
    assert rows[0]["cpu_pct"] is None
    assert rows[0]["mem_gb"] is None
    assert rows[0]["metrics_window"] is None


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


def _entity(entity_id: str, state: str, unit: str | None, area: str | None, **extra: Any) -> dict:
    return {
        "entity_id": entity_id,
        "entity_class": entity_id.split(".")[0],
        "friendly_name": extra.get("friendly_name"),
        "area": area,
        "unit": unit,
        "last_state": state,
        "last_seen": extra.get("last_seen", "2026-10-18T12:00:00+00:00"),
    }


def test_device_readings_group_by_room() -> None:
    rooms = build_device_readings(
        [
            _entity("sensor.lr_temperature", "21.0", "°C", "living_room"),
            _entity("sensor.lr_temp_2", "71.6", "°F", "living_room"),
            _entity("sensor.lr_humidity", "45", "%", "living_room"),
            _entity("sensor.lr_tv_power", "120", "W", "living_room"),
            _entity("sensor.lr_lamp_power", "0.03", "kW", "living_room"),
            _entity("sensor.kitchen_temperature", "unavailable", "°C", "kitchen"),
            _entity("sensor.hall_temperature", "19.5", "°C", None),
            _entity("sensor.phone_battery", "80", "%", "living_room"),
            _entity("light.kitchen", "on", None, "kitchen"),
        ]
    )
    by_room = {row["room"]: row for row in rooms}
    assert [row["room"] for row in rooms] == ["kitchen", "living_room", None]

    living = by_room["living_room"]
    assert living["temperature_c"] == 21.5  # mean of 21.0 and 22.0
    assert living["humidity_pct"] == 45
    assert living["power_w"] == 150
    assert living["sensor_count"] == 5

    # A room whose only sensor is unavailable still shows, with unknowns.
    kitchen = by_room["kitchen"]
    assert kitchen["temperature_c"] is None
    assert kitchen["humidity_pct"] is None
    assert kitchen["power_w"] is None
    assert kitchen["sensor_count"] == 1

    assert by_room[None]["temperature_c"] == 19.5


def test_device_readings_empty() -> None:
    assert build_device_readings([]) == []


# ---------------------------------------------------------------------------
# Event feed
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    run_id: str
    dataset_name: str
    source_name: str
    row_count: int
    status: IngestionRunStatus
    created_at: datetime


def test_event_feed_merges_sources_newest_first_and_honours_since() -> None:
    since = NOW - timedelta(hours=12)
    runs = [
        _Run("r1", "transactions", "bank", 40, IngestionRunStatus.LANDED, NOW - timedelta(hours=1)),
        _Run("r2", "bills", "upload", 0, IngestionRunStatus.REJECTED,
             (NOW - timedelta(hours=2)).replace(tzinfo=None)),
        _Run("old", "x", "y", 1, IngestionRunStatus.LANDED, NOW - timedelta(days=2)),
    ]
    proposals = [
        {
            "action_id": "p1",
            "policy_name": "Battery charge",
            "status": "approved",
            "created_at": (NOW - timedelta(hours=3)).isoformat(),
            "approved_at": (NOW - timedelta(minutes=30)).isoformat(),
            "resolved_by": "alice",
        },
        {
            "action_id": "p2",
            "policy_name": "Old",
            "status": "pending",
            "created_at": (NOW - timedelta(days=1)).isoformat(),
        },
    ]
    alerts = [
        {"action_class": "alert", "action_type": "persistent_notification_create",
         "policy_id": "budget", "policy_name": "Budget", "verdict": "breach",
         "timestamp": (NOW - timedelta(minutes=10)).isoformat(), "result": "success"},
        {"action_class": "recommendation", "action_type": "persistent_notification_create",
         "policy_id": "budget", "policy_name": "Budget",
         "timestamp": (NOW - timedelta(minutes=10)).isoformat()},
    ]
    events = build_event_feed(runs=runs, proposals=proposals, alerts=alerts, since=since)
    assert [event["title"] for event in events] == [
        "Alert: Budget (breach)",
        "Approved: Battery charge",
        "Ingested transactions",
        "Ingestion rejected: bills",
        "Proposed: Battery charge",
    ]
    assert events[0]["tone"] == "warn"
    assert events[2]["detail"] == "40 rows from bank"
    assert events[2]["kind"] == "ingestion"
    # No history on these fixtures: the snapshot timestamps are the fallback.
    assert events[4]["tone"] == "accent"


def test_event_feed_reads_proposal_history_including_release_failed() -> None:
    def at(minutes: int) -> str:
        return (NOW - timedelta(minutes=minutes)).isoformat()

    proposal = {
        "action_id": "p9",
        "policy_name": "Charge battery",
        "status": "pending",
        "created_at": at(50),
        "approved_at": None,  # cleared by the failed release
        "history": [
            {"kind": "drafted", "at": at(50), "actor": "policy", "reason": None},
            {"kind": "refreshed", "at": at(40), "actor": None, "reason": None},
            {"kind": "approved", "at": at(30), "actor": "alice", "reason": None},
            {"kind": "release_failed", "at": at(29), "actor": None,
             "reason": "HA notification release failed"},
            {"kind": "reopened", "at": at(10), "actor": None, "reason": None},
        ],
    }
    events = build_event_feed(
        runs=[], proposals=[proposal], alerts=[], since=NOW - timedelta(hours=1)
    )
    assert [(event["title"], event["tone"]) for event in events] == [
        ("Reopened: Charge battery", "accent"),
        ("Release failed: Charge battery", "warn"),
        ("Approved: Charge battery", "ok"),
        ("Proposed: Charge battery", "accent"),
    ]
    assert events[1]["detail"] == "HA notification release failed"
    assert events[2]["detail"] == "alice"
    assert len({event["event_id"] for event in events}) == 4


def test_event_feed_alert_dismiss_is_ok_tone() -> None:
    events = build_event_feed(
        runs=[],
        proposals=[],
        alerts=[{"action_class": "alert", "action_type": "persistent_notification_dismiss",
                 "policy_id": "p", "policy_name": "Budget", "timestamp": NOW.isoformat(),
                 "result": "success"}],
        since=NOW - timedelta(hours=1),
    )
    assert events[0]["title"] == "Cleared: Budget"
    assert events[0]["tone"] == "ok"


# ---------------------------------------------------------------------------
# Power series
# ---------------------------------------------------------------------------


def _reading(at: datetime, value: str) -> dict[str, str]:
    return {"changed_at": at.isoformat(), "state": value}


def test_power_series_has_24_utc_hour_buckets() -> None:
    buckets = build_power_series([], unit="kWh", now=NOW)
    assert len(buckets) == 24
    assert buckets[-1]["hour_start"] == "2026-10-18T12:00:00+00:00"
    assert buckets[-1]["partial"] is True
    assert buckets[0]["hour_start"] == "2026-10-17T13:00:00+00:00"
    assert buckets[0]["partial"] is False
    assert all(bucket["kwh"] is None for bucket in buckets)


def test_power_series_spreads_deltas_and_marks_unknown() -> None:
    h10 = NOW.replace(hour=10, minute=0)
    readings = [
        _reading(h10, "100.0"),
        _reading(h10 + timedelta(minutes=30), "100.5"),
        # Crosses 11:00: 1.0 kWh over 60 min split 30/30.
        _reading(h10 + timedelta(minutes=90), "101.5"),
        # Meter reset: new value is the delta.
        _reading(h10 + timedelta(minutes=110), "0.2"),
        {"changed_at": "not-a-time", "state": "5"},
        _reading(h10 + timedelta(minutes=115), "unavailable"),
    ]
    buckets = {bucket["hour_start"][11:16]: bucket for bucket in
               build_power_series(readings, unit="kWh", now=NOW)}
    assert buckets["10:00"]["kwh"] == 1.0
    assert buckets["11:00"]["kwh"] == 0.7
    assert buckets["12:00"]["kwh"] is None
    assert buckets["09:00"]["kwh"] is None


def test_power_series_long_gap() -> None:
    h3 = NOW.replace(hour=3, minute=0)
    moving = build_power_series(
        [_reading(h3, "10"), _reading(h3 + timedelta(hours=5), "15")], unit="kWh", now=NOW
    )
    flat = build_power_series(
        [_reading(h3, "10"), _reading(h3 + timedelta(hours=5), "10")], unit="kWh", now=NOW
    )
    moving_by = {b["hour_start"][11:13]: b["kwh"] for b in moving}
    flat_by = {b["hour_start"][11:13]: b["kwh"] for b in flat}
    assert moving_by["04"] is None  # cannot place 5 kWh inside a 5h gap
    assert flat_by["04"] == 0.0  # unchanged counter: nothing used


def test_power_series_converts_wh() -> None:
    h11 = NOW.replace(hour=11, minute=0)
    buckets = build_power_series(
        [_reading(h11, "1000"), _reading(h11 + timedelta(minutes=30), "1500")],
        unit="Wh",
        now=NOW,
    )
    assert buckets[-2]["kwh"] == 0.5


def test_select_energy_meter() -> None:
    house = {"entity_id": "sensor.house_energy", "unit": "kWh"}
    plug = {"entity_id": "sensor.plug_energy", "unit": "kWh"}
    other = {"entity_id": "sensor.ev_energy", "unit": "kWh"}
    assert select_energy_meter([]) == (None, "no_meter")
    assert select_energy_meter([plug]) == (plug, "ok")
    assert select_energy_meter([house, plug]) == (house, "ok")
    assert select_energy_meter([plug, other]) == (None, "ambiguous")
    assert select_energy_meter([plug, other], entity_id="sensor.ev_energy") == (other, "ok")
    assert select_energy_meter([plug], entity_id="sensor.nope") == (None, "no_meter")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _client(tmp_path: Path, *, with_reporting: bool = True) -> tuple[TestClient, dict[str, Any]]:
    repo = RunMetadataRepository(tmp_path / "runs.db")
    service = AccountTransactionService(
        landing_root=tmp_path / "landing", metadata_repository=repo
    )
    ts = TransformationService(DuckDBStore.memory())
    registry = ActionProposalRegistry()
    app = create_app(
        service,
        transformation_service=ts if with_reporting else None,
        reporting_service=ReportingService(ts) if with_reporting else None,
        ha_action_proposal_registry=registry,
    )
    return TestClient(app), {"ts": ts, "repo": repo, "registry": registry}


def test_api_empty_states_are_honest(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    services = client.get("/api/wallboard/services").json()
    assert services["available"] is True
    assert services["services"] == []

    devices = client.get("/api/wallboard/devices").json()
    assert devices == {"available": True, "generated_at": devices["generated_at"], "rooms": []}

    power = client.get("/api/wallboard/power").json()
    assert power["status"] == "no_meter"
    assert power["window_hours"] == 24
    assert len(power["buckets"]) == 24
    assert power["total_kwh"] is None
    assert all(bucket["kwh"] is None for bucket in power["buckets"])

    events = client.get("/api/wallboard/events").json()
    assert events["events"] == []
    assert events["sources"] == {"runs": True, "proposals": True, "alerts": False}
    since = datetime.fromisoformat(events["since"])
    generated = datetime.fromisoformat(events["generated_at"])
    assert generated - since == timedelta(hours=12)


def test_api_without_reporting_reports_unavailable(tmp_path: Path) -> None:
    client, _ = _client(tmp_path, with_reporting=False)
    assert client.get("/api/wallboard/services").json()["available"] is False
    assert client.get("/api/wallboard/devices").json()["available"] is False
    power = client.get("/api/wallboard/power").json()
    assert power["available"] is False
    assert power["status"] == "unavailable"


def test_api_panels_with_data(tmp_path: Path) -> None:
    client, deps = _client(tmp_path)
    ts: TransformationService = deps["ts"]
    now = datetime.now(UTC)

    ts.load_service_health(
        [{"service_id": "ha", "service_name": "Home Assistant", "host": "nuc",
          "state": "running", "uptime_seconds": 7200,
          "recorded_at": now.replace(tzinfo=None).isoformat()}],
        run_id="hl-1",
    )
    refresh_service_health_current(ts.store)

    hour = now.replace(minute=0, second=0, microsecond=0)
    ts.ingest_ha_states(
        [
            {"entity_id": "sensor.house_energy", "state": "500.0",
             "attributes": {"unit_of_measurement": "kWh"},
             "last_changed": (hour - timedelta(hours=1)).isoformat()},
            {"entity_id": "sensor.lr_temperature", "state": "21.4",
             "attributes": {"unit_of_measurement": "°C", "area_id": "living_room"},
             "last_changed": now.isoformat()},
        ]
    )
    ts.ingest_ha_states(
        [{"entity_id": "sensor.house_energy", "state": "501.2",
          "attributes": {"unit_of_measurement": "kWh"},
          "last_changed": (hour - timedelta(minutes=30)).isoformat()}]
    )

    deps["repo"].create_run(
        IngestionRunCreate(
            run_id="run-1", source_name="bank", dataset_name="transactions",
            file_name="a.csv", raw_path="r", manifest_path="m", sha256="x",
            row_count=3, header=("a",), status=IngestionRunStatus.LANDED, passed=True,
        )
    )
    deps["registry"].register(
        policy_id="pol", policy_name="Charge battery", verdict="warning",
        value=None, notification_id=None,
    )

    services = client.get("/api/wallboard/services").json()["services"]
    assert services[0]["name"] == "Home Assistant"
    assert services[0]["status"] == "up"
    assert services[0]["host"] == "nuc"
    assert services[0]["uptime_seconds"] == 7200
    assert services[0]["cpu_pct"] is None

    rooms = client.get("/api/wallboard/devices").json()["rooms"]
    assert rooms == [
        {"room": "living_room", "temperature_c": 21.4, "humidity_pct": None,
         "power_w": None, "sensor_count": 1, "last_seen": rooms[0]["last_seen"]}
    ]

    power = client.get("/api/wallboard/power").json()
    assert power["status"] == "ok"
    assert power["meter"]["entity_id"] == "sensor.house_energy"
    assert power["buckets"][-2]["kwh"] == pytest.approx(1.2)
    assert power["total_kwh"] == pytest.approx(1.2)

    titles = [event["title"] for event in client.get("/api/wallboard/events").json()["events"]]
    assert "Ingested transactions" in titles
    assert "Proposed: Charge battery" in titles

    narrow = client.get("/api/wallboard/power", params={"window_hours": 6}).json()
    assert len(narrow["buckets"]) == 6


def test_api_rejects_bad_since(tmp_path: Path) -> None:
    client, _ = _client(tmp_path)
    assert client.get("/api/wallboard/events", params={"since": "yesterday"}).status_code == 400
    assert client.get("/api/wallboard/power", params={"window_hours": 0}).status_code == 422
