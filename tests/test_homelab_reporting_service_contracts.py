"""Contract tests: ReportingService correctly surfaces the 4 homelab mart methods
and the HA entity read/write methods added in sprint #387.

These tests verify that the RS delegation layer returns the expected column
shapes and does not accidentally raise or swallow domain errors.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from packages.pipelines.reporting_service import ReportingService
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _make_rs() -> ReportingService:
    ts = TransformationService(DuckDBStore.memory())
    return ReportingService(ts)


def _seed_homelab(rs: ReportingService) -> None:
    ts = rs._transformation_service
    ts.load_service_health(
        [
            {
                "service_id": "svc_a", "service_name": "Alpha", "service_type": "container",
                "host": "node-1", "criticality": "critical", "managed_by": "k8s",
                "recorded_at": "2026-05-08T10:00:00", "state": "running",
                "uptime_seconds": "3600", "last_state_change": "2026-05-08T09:00:00",
            },
            {
                "service_id": "svc_b", "service_name": "Beta", "service_type": "addon",
                "host": "node-1", "criticality": "low", "managed_by": "docker",
                "recorded_at": "2026-05-08T10:00:00", "state": "stopped",
                "uptime_seconds": "0", "last_state_change": "2026-05-08T09:30:00",
            },
        ],
        run_id="r-1",
    )
    ts.refresh_service_health_current()

    ts.load_backup_runs(
        [
            {
                "backup_id": "bkp-1", "target": "nas",
                "started_at": "2026-05-08T02:00:00", "completed_at": "2026-05-08T02:15:00",
                "size_bytes": "1073741824", "status": "success",
            },
        ],
        run_id="r-2",
    )
    ts.refresh_backup_freshness()

    ts.load_storage_sensors(
        [
            {
                "entity_id": "sensor.nas_disk", "device_name": "NAS Array",
                "recorded_at": "2026-05-08T10:00:00", "capacity_bytes": "1000000000",
                "used_bytes": "850000000", "sensor_type": "disk",
            },
        ],
        run_id="r-3",
    )
    ts.refresh_storage_risk()

    # workload_cost_7d windows on CURRENT_TIMESTAMP - 7 days; keep samples inside it
    base = datetime.now() - timedelta(hours=2)
    ts.load_workload_sensors(
        [
            {
                "workload_id": "wl_plex", "entity_id": "sensor.plex_cpu",
                "display_name": "Plex", "host": "node-1", "workload_type": "container",
                "recorded_at": (base - timedelta(hours=1)).isoformat(),
                "cpu_pct": "15.0", "mem_bytes": "536870912",
            },
        ],
        run_id="r-4",
    )
    ts.refresh_workload_cost_7d()


class TestServiceHealthCurrentContract(unittest.TestCase):
    def test_returns_list_of_dicts(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        rows = rs.get_service_health_current()
        self.assertIsInstance(rows, list)
        self.assertEqual(2, len(rows))

    def test_row_has_required_columns(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        row = rs.get_service_health_current()[0]
        for col in ("service_id", "service_name", "criticality", "managed_by", "state"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_empty_when_no_data(self) -> None:
        rs = _make_rs()
        self.assertEqual([], rs.get_service_health_current())


class TestBackupFreshnessContract(unittest.TestCase):
    def test_returns_list_of_dicts(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        rows = rs.get_backup_freshness()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_row_has_required_columns(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        row = rs.get_backup_freshness()[0]
        for col in ("target", "hours_since_backup", "is_stale"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_is_stale_is_boolean(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        for row in rs.get_backup_freshness():
            self.assertIn(row["is_stale"], (True, False))


class TestStorageRiskContract(unittest.TestCase):
    def test_returns_list_of_dicts(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        rows = rs.get_storage_risk()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_row_has_required_columns(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        row = rs.get_storage_risk()[0]
        for col in ("entity_id", "device_name", "pct_used", "risk_tier"):
            self.assertIn(col, row, f"missing column: {col}")

    def test_pct_used_is_numeric(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        row = rs.get_storage_risk()[0]
        self.assertIsInstance(float(row["pct_used"]), float)


class TestWorkloadCost7dContract(unittest.TestCase):
    def test_returns_list_of_dicts(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        rows = rs.get_workload_cost_7d()
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_row_has_required_columns(self) -> None:
        rs = _make_rs()
        _seed_homelab(rs)
        row = rs.get_workload_cost_7d()[0]
        for col in ("workload_id", "avg_cpu_pct_7d", "est_monthly_cost"):
            self.assertIn(col, row, f"missing column: {col}")


class TestHaEntityMethodsContract(unittest.TestCase):
    """Verify the HA entity read/write delegation added in sprint #387."""

    def _seed_entities(self, rs: ReportingService) -> None:
        states = [
            {"entity_id": "sensor.temp", "state": "21.5",
             "attributes": {"unit_of_measurement": "°C"}, "last_changed": "2026-05-08T10:00:00Z"},
            {"entity_id": "light.kitchen", "state": "on",
             "attributes": {"brightness": 255}, "last_changed": "2026-05-08T10:01:00Z"},
        ]
        rs.ingest_ha_states(states, run_id="ha-r-1", source_system="home_assistant")

    def test_ingest_ha_states_returns_count(self) -> None:
        rs = _make_rs()
        states = [
            {"entity_id": "sensor.temp", "state": "21.5",
             "attributes": {}, "last_changed": "2026-05-08T10:00:00Z"},
        ]
        count = rs.ingest_ha_states(states, run_id="ha-r-1")
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(count, 0)

    def test_get_ha_entities_returns_list(self) -> None:
        rs = _make_rs()
        self._seed_entities(rs)
        rows = rs.get_ha_entities()
        self.assertIsInstance(rows, list)
        self.assertEqual(2, len(rows))

    def test_get_ha_entities_row_has_entity_id(self) -> None:
        rs = _make_rs()
        self._seed_entities(rs)
        ids = {r["entity_id"] for r in rs.get_ha_entities()}
        self.assertIn("sensor.temp", ids)
        self.assertIn("light.kitchen", ids)

    def test_get_ha_entity_history_returns_list(self) -> None:
        rs = _make_rs()
        self._seed_entities(rs)
        rows = rs.get_ha_entity_history("sensor.temp", limit=10)
        self.assertIsInstance(rows, list)

    def test_get_ha_entity_history_empty_for_unknown_entity(self) -> None:
        rs = _make_rs()
        rows = rs.get_ha_entity_history("sensor.nonexistent", limit=10)
        self.assertEqual([], rows)
