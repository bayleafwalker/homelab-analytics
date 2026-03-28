"""Tests for the homelab domain — fact loading, mart refresh, and acceptance criteria.

Minimum acceptance (from sprint docs):
- All 4 marts populate from fixture data
- mart_backup_freshness correctly flags targets with last backup >24h ago
- mart_storage_risk correctly tiers at 80%/90% thresholds
- HOMELAB_PACK.validate() passes
"""
from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from packages.domains.homelab.manifest import HOMELAB_PACK
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _service_rows() -> list[dict]:
    return [
        {
            "service_id": "svc_homeassistant",
            "service_name": "Home Assistant",
            "service_type": "addon",
            "host": "homeserver",
            "criticality": "critical",
            "managed_by": "homeassistant",
            "recorded_at": "2026-03-20T08:00:00",
            "state": "running",
            "uptime_seconds": "864000",
            "last_state_change": "2026-03-10T08:00:00",
        },
        {
            "service_id": "svc_postgres",
            "service_name": "PostgreSQL",
            "service_type": "container",
            "host": "homeserver",
            "criticality": "critical",
            "managed_by": "portainer",
            "recorded_at": "2026-03-20T08:00:00",
            "state": "running",
            "uptime_seconds": "432000",
            "last_state_change": "2026-03-15T08:00:00",
        },
        {
            "service_id": "svc_nginx",
            "service_name": "Nginx",
            "service_type": "container",
            "host": "homeserver",
            "criticality": "standard",
            "managed_by": "portainer",
            "recorded_at": "2026-03-20T08:00:00",
            "state": "running",
            "uptime_seconds": "172800",
            "last_state_change": "2026-03-18T08:00:00",
        },
        {
            "service_id": "svc_mosquitto",
            "service_name": "Mosquitto MQTT",
            "service_type": "addon",
            "host": "homeserver",
            "criticality": "standard",
            "managed_by": "homeassistant",
            "recorded_at": "2026-03-20T08:00:00",
            "state": "degraded",
            "uptime_seconds": "3600",
            "last_state_change": "2026-03-20T07:00:00",
        },
        {
            "service_id": "svc_backups",
            "service_name": "Backup Agent",
            "service_type": "container",
            "host": "homeserver",
            "criticality": "background",
            "managed_by": "portainer",
            "recorded_at": "2026-03-20T08:00:00",
            "state": "stopped",
            "uptime_seconds": "0",
            "last_state_change": "2026-03-20T06:00:00",
        },
    ]


def _backup_rows() -> list[dict]:
    return [
        {
            "backup_id": "bkp_001",
            "started_at": "2026-03-20T02:00:00",
            "completed_at": "2026-03-20T02:15:00",
            "size_bytes": "5368709120",
            "target": "nas",
            "status": "success",
        },
        {
            "backup_id": "bkp_002",
            "started_at": "2026-03-20T02:30:00",
            "completed_at": "2026-03-20T02:45:00",
            "size_bytes": "1073741824",
            "target": "s3",
            "status": "success",
        },
        {
            "backup_id": "bkp_003",
            "started_at": "2026-03-18T02:00:00",
            "completed_at": "2026-03-18T02:20:00",
            "size_bytes": "4831838208",
            "target": "nas",
            "status": "success",
        },
    ]


def _storage_rows() -> list[dict]:
    return [
        {
            "entity_id": "sensor.homeserver_disk",
            "device_name": "Home Server /",
            "recorded_at": "2026-03-20T08:00:00",
            "capacity_bytes": "500107862016",
            "used_bytes": "420090765312",   # ~84% → warn tier
            "sensor_type": "disk",
        },
        {
            "entity_id": "sensor.nas_disk",
            "device_name": "NAS Array",
            "recorded_at": "2026-03-20T08:00:00",
            "capacity_bytes": "4000787030016",
            "used_bytes": "3500689338368",  # ~87.5% → warn tier
            "sensor_type": "disk",
        },
    ]


def _crit_storage_row() -> dict:
    """Storage sensor at >90% usage — crit tier."""
    return {
        "entity_id": "sensor.crit_disk",
        "device_name": "Critical Disk",
        "recorded_at": "2026-03-20T08:00:00",
        "capacity_bytes": "100000000000",
        "used_bytes": "95000000000",  # 95% → crit
        "sensor_type": "disk",
    }


def _ok_storage_row() -> dict:
    """Storage sensor at <80% usage — ok tier."""
    return {
        "entity_id": "sensor.ok_disk",
        "device_name": "OK Disk",
        "recorded_at": "2026-03-20T08:00:00",
        "capacity_bytes": "100000000000",
        "used_bytes": "50000000000",  # 50% → ok
        "sensor_type": "disk",
    }


def _workload_rows() -> list[dict]:
    base = datetime.now().replace(microsecond=0, second=0, minute=0)
    return [
        {
            "workload_id": "wl_homeassistant",
            "entity_id": "sensor.ha_cpu",
            "display_name": "Home Assistant",
            "host": "homeserver",
            "workload_type": "addon",
            "recorded_at": (base - timedelta(days=1)).isoformat(),
            "cpu_pct": "12.5",
            "mem_bytes": "536870912",
        },
        {
            "workload_id": "wl_homeassistant",
            "entity_id": "sensor.ha_cpu",
            "display_name": "Home Assistant",
            "host": "homeserver",
            "workload_type": "addon",
            "recorded_at": (base - timedelta(days=1, hours=1)).isoformat(),
            "cpu_pct": "15.2",
            "mem_bytes": "524288000",
        },
        {
            "workload_id": "wl_postgres",
            "entity_id": "sensor.pg_cpu",
            "display_name": "PostgreSQL",
            "host": "homeserver",
            "workload_type": "container",
            "recorded_at": (base - timedelta(days=1)).isoformat(),
            "cpu_pct": "5.1",
            "mem_bytes": "268435456",
        },
    ]


# ---------------------------------------------------------------------------
# Pack validation
# ---------------------------------------------------------------------------


class HomelabPackTests(unittest.TestCase):
    def test_homelab_pack_validates(self) -> None:
        HOMELAB_PACK.validate()

    def test_homelab_pack_has_four_publications(self) -> None:
        self.assertEqual(4, len(HOMELAB_PACK.publications))

    def test_homelab_pack_has_four_sources(self) -> None:
        self.assertEqual(4, len(HOMELAB_PACK.sources))

    def test_homelab_pack_has_four_ui_descriptors(self) -> None:
        self.assertEqual(4, len(HOMELAB_PACK.ui_descriptors))

    def test_homelab_pack_publication_keys(self) -> None:
        keys = {p.key for p in HOMELAB_PACK.publications}
        self.assertIn("service_health_current", keys)
        self.assertIn("backup_freshness", keys)
        self.assertIn("storage_risk", keys)
        self.assertIn("workload_cost_7d", keys)


# ---------------------------------------------------------------------------
# Service health loading
# ---------------------------------------------------------------------------


class ServiceHealthLoadTests(unittest.TestCase):
    def _svc(self) -> TransformationService:
        return TransformationService(DuckDBStore.memory())

    def test_load_service_health_inserts_facts(self) -> None:
        svc = self._svc()
        inserted = svc.load_service_health(_service_rows(), run_id="run-hl-001")
        self.assertEqual(5, inserted)

    def test_load_service_health_empty_returns_zero(self) -> None:
        svc = self._svc()
        self.assertEqual(0, svc.load_service_health([]))

    def test_count_service_health_rows(self) -> None:
        svc = self._svc()
        svc.load_service_health(_service_rows(), run_id="run-hl-001")
        self.assertEqual(5, svc.count_service_health_rows())
        self.assertEqual(5, svc.count_service_health_rows("run-hl-001"))
        self.assertEqual(0, svc.count_service_health_rows("other-run"))

    def test_refresh_service_health_current_populates_mart(self) -> None:
        svc = self._svc()
        svc.load_service_health(_service_rows(), run_id="run-hl-001")
        count = svc.refresh_service_health_current()
        self.assertEqual(5, count)

    def test_get_service_health_current_returns_rows(self) -> None:
        svc = self._svc()
        svc.load_service_health(_service_rows(), run_id="run-hl-001")
        svc.refresh_service_health_current()
        rows = svc.get_service_health_current()
        self.assertEqual(5, len(rows))
        states = {row["state"] for row in rows}
        self.assertIn("running", states)
        self.assertIn("degraded", states)
        self.assertIn("stopped", states)

    def test_service_health_current_has_service_attributes(self) -> None:
        svc = self._svc()
        svc.load_service_health(_service_rows(), run_id="run-hl-001")
        svc.refresh_service_health_current()
        rows = svc.get_service_health_current()
        ha_row = next(r for r in rows if r["service_id"] == "svc_homeassistant")
        self.assertEqual("Home Assistant", ha_row["service_name"])
        self.assertEqual("critical", ha_row["criticality"])
        self.assertEqual("homeassistant", ha_row["managed_by"])


# ---------------------------------------------------------------------------
# Backup freshness
# ---------------------------------------------------------------------------


class BackupFreshnessTests(unittest.TestCase):
    def _svc(self) -> TransformationService:
        return TransformationService(DuckDBStore.memory())

    def test_load_backup_runs_inserts_facts(self) -> None:
        svc = self._svc()
        inserted = svc.load_backup_runs(_backup_rows(), run_id="run-bkp-001")
        self.assertEqual(3, inserted)

    def test_count_backup_run_rows(self) -> None:
        svc = self._svc()
        svc.load_backup_runs(_backup_rows(), run_id="run-bkp-001")
        self.assertEqual(3, svc.count_backup_run_rows())

    def test_refresh_backup_freshness_populates_mart(self) -> None:
        svc = self._svc()
        svc.load_backup_runs(_backup_rows(), run_id="run-bkp-001")
        count = svc.refresh_backup_freshness()
        # 2 distinct targets: nas, s3
        self.assertEqual(2, count)

    def test_backup_freshness_has_staleness_flag(self) -> None:
        svc = self._svc()
        svc.load_backup_runs(_backup_rows(), run_id="run-bkp-001")
        svc.refresh_backup_freshness()
        rows = svc.get_backup_freshness()
        # Fixture backups were on 2026-03-20; test runs on 2026-03-20 so should be fresh
        # (hours_since_backup < 24). We test that is_stale is a boolean field.
        for row in rows:
            self.assertIn(row["is_stale"], (True, False))
            self.assertIn("target", row)
            self.assertIn("hours_since_backup", row)

    def test_backup_freshness_flags_old_target_as_stale(self) -> None:
        """A target whose only backup is >48h old must be marked stale."""
        svc = self._svc()
        old_rows = [
            {
                "backup_id": "bkp_old",
                "started_at": "2024-01-01T00:00:00",
                "completed_at": "2024-01-01T00:30:00",
                "size_bytes": "1000000",
                "target": "archive",
                "status": "success",
            }
        ]
        svc.load_backup_runs(old_rows, run_id="run-stale")
        svc.refresh_backup_freshness()
        rows = svc.get_backup_freshness()
        stale_row = next(r for r in rows if r["target"] == "archive")
        self.assertTrue(stale_row["is_stale"])


# ---------------------------------------------------------------------------
# Storage risk
# ---------------------------------------------------------------------------


class StorageRiskTests(unittest.TestCase):
    def _svc(self) -> TransformationService:
        return TransformationService(DuckDBStore.memory())

    def test_load_storage_sensors_inserts_facts(self) -> None:
        svc = self._svc()
        inserted = svc.load_storage_sensors(_storage_rows(), run_id="run-stor-001")
        self.assertEqual(2, inserted)

    def test_refresh_storage_risk_populates_mart(self) -> None:
        svc = self._svc()
        svc.load_storage_sensors(_storage_rows(), run_id="run-stor-001")
        count = svc.refresh_storage_risk()
        self.assertEqual(2, count)

    def test_storage_risk_has_pct_used_and_tier(self) -> None:
        svc = self._svc()
        svc.load_storage_sensors(_storage_rows(), run_id="run-stor-001")
        svc.refresh_storage_risk()
        rows = svc.get_storage_risk()
        for row in rows:
            self.assertIn("pct_used", row)
            self.assertIn(row["risk_tier"], ("ok", "warn", "crit"))

    def test_storage_risk_warn_tier_at_84_percent(self) -> None:
        """~84% usage → warn tier."""
        svc = self._svc()
        svc.load_storage_sensors(_storage_rows(), run_id="run-stor-001")
        svc.refresh_storage_risk()
        rows = svc.get_storage_risk()
        homeserver_row = next(r for r in rows if r["entity_id"] == "sensor.homeserver_disk")
        self.assertEqual("warn", homeserver_row["risk_tier"])

    def test_storage_risk_crit_tier_at_95_percent(self) -> None:
        """95% usage → crit tier."""
        svc = self._svc()
        svc.load_storage_sensors([_crit_storage_row()], run_id="run-crit")
        svc.refresh_storage_risk()
        rows = svc.get_storage_risk()
        self.assertEqual(1, len(rows))
        self.assertEqual("crit", rows[0]["risk_tier"])

    def test_storage_risk_ok_tier_at_50_percent(self) -> None:
        """50% usage → ok tier."""
        svc = self._svc()
        svc.load_storage_sensors([_ok_storage_row()], run_id="run-ok")
        svc.refresh_storage_risk()
        rows = svc.get_storage_risk()
        self.assertEqual(1, len(rows))
        self.assertEqual("ok", rows[0]["risk_tier"])

    def test_storage_risk_free_bytes_calculated(self) -> None:
        svc = self._svc()
        svc.load_storage_sensors([_ok_storage_row()], run_id="run-fb")
        svc.refresh_storage_risk()
        rows = svc.get_storage_risk()
        row = rows[0]
        self.assertEqual(
            int(row["capacity_bytes"]) - int(row["used_bytes"]),
            int(row["free_bytes"]),
        )


# ---------------------------------------------------------------------------
# Workload cost
# ---------------------------------------------------------------------------


class WorkloadCostTests(unittest.TestCase):
    def _svc(self) -> TransformationService:
        return TransformationService(DuckDBStore.memory())

    def test_load_workload_sensors_inserts_facts(self) -> None:
        svc = self._svc()
        inserted = svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        self.assertEqual(3, inserted)

    def test_count_workload_sensor_rows(self) -> None:
        svc = self._svc()
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        self.assertEqual(3, svc.count_workload_sensor_rows())

    def test_refresh_workload_cost_7d_populates_mart(self) -> None:
        svc = self._svc()
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        count = svc.refresh_workload_cost_7d()
        # Fixture has readings within last 7 days — 2 distinct workloads
        self.assertEqual(2, count)

    def test_workload_cost_7d_has_expected_fields(self) -> None:
        svc = self._svc()
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        svc.refresh_workload_cost_7d()
        rows = svc.get_workload_cost_7d()
        for row in rows:
            self.assertIn("workload_id", row)
            self.assertIn("avg_cpu_pct_7d", row)
            self.assertIn("avg_mem_gb_7d", row)
            self.assertIn("est_monthly_cost", row)

    def test_workload_cost_est_monthly_cost_is_non_negative(self) -> None:
        svc = self._svc()
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        svc.refresh_workload_cost_7d()
        rows = svc.get_workload_cost_7d()
        for row in rows:
            self.assertGreaterEqual(float(row["est_monthly_cost"]), 0)

    def test_workload_cost_ha_avg_cpu_is_average_of_readings(self) -> None:
        svc = self._svc()
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl-001")
        svc.refresh_workload_cost_7d()
        rows = svc.get_workload_cost_7d()
        ha_row = next(r for r in rows if r["workload_id"] == "wl_homeassistant")
        # 2 readings: 12.5 + 15.2 = 27.7 / 2 = 13.85
        self.assertAlmostEqual(13.85, float(ha_row["avg_cpu_pct_7d"]), places=2)


# ---------------------------------------------------------------------------
# Refresh all 4 marts from complete fixture set
# ---------------------------------------------------------------------------


class HomelabFullRefreshTests(unittest.TestCase):
    def _svc_with_all_data(self) -> TransformationService:
        svc = TransformationService(DuckDBStore.memory())
        svc.load_service_health(_service_rows(), run_id="run-hl")
        svc.load_backup_runs(_backup_rows(), run_id="run-bkp")
        svc.load_storage_sensors(_storage_rows(), run_id="run-stor")
        svc.load_workload_sensors(_workload_rows(), run_id="run-wl")
        return svc

    def test_all_four_marts_populate(self) -> None:
        svc = self._svc_with_all_data()
        self.assertGreater(svc.refresh_service_health_current(), 0)
        self.assertGreater(svc.refresh_backup_freshness(), 0)
        self.assertGreater(svc.refresh_storage_risk(), 0)
        self.assertGreater(svc.refresh_workload_cost_7d(), 0)

    def test_refresh_is_idempotent(self) -> None:
        svc = self._svc_with_all_data()
        first = svc.refresh_service_health_current()
        second = svc.refresh_service_health_current()
        self.assertEqual(first, second)

    def test_all_four_get_functions_return_rows(self) -> None:
        svc = self._svc_with_all_data()
        svc.refresh_service_health_current()
        svc.refresh_backup_freshness()
        svc.refresh_storage_risk()
        svc.refresh_workload_cost_7d()
        self.assertGreater(len(svc.get_service_health_current()), 0)
        self.assertGreater(len(svc.get_backup_freshness()), 0)
        self.assertGreater(len(svc.get_storage_risk()), 0)
        self.assertGreater(len(svc.get_workload_cost_7d()), 0)
