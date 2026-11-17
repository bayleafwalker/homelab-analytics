"""Observed-backup visibility and latest-attempt recovery-point contracts.

Regression tests for the ``mart_backup_freshness`` builder: every target with
observed runs stays visible before its first success, the recovery point
(``last_backup_at`` / ``last_size_bytes``) always comes from the latest success,
and ``last_status`` reports the latest attempt of any status.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.domains.homelab.pipelines.transformation_homelab import (
    get_backup_freshness,
    refresh_backup_freshness,
)
from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


def _row(backup_id, target, status, hours, size):
    at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)
    return {
        "backup_id": backup_id,
        "target": target,
        "status": status,
        "started_at": at.isoformat(),
        "completed_at": (at + timedelta(minutes=5)).isoformat(),
        "size_bytes": str(size),
    }


def _refresh(rows):
    svc = TransformationService(DuckDBStore.memory())
    svc.load_backup_runs(rows, run_id="run")
    refresh_backup_freshness(svc.store)
    return {r["target"]: r for r in get_backup_freshness(svc.store)}


def test_failed_only_target_is_visible_with_unknown_recovery_point():
    actual = _refresh(
        [
            _row("a", "failed-only", "failed", 2, 0),
            _row("b", "failed-only", "partial", 1, 15),
        ]
    )
    assert set(actual) == {"failed-only"}
    row = actual["failed-only"]
    assert row["last_backup_at"] is None
    assert row["last_size_bytes"] is None
    assert row["hours_since_backup"] is None
    assert row["is_stale"] is True
    assert row["last_status"] == "partial"
    assert row["backup_count_7d"] == 2


def test_success_then_failed_retry_keeps_recovery_point_and_reports_latest_status():
    actual = _refresh(
        [
            _row("s", "retrying", "success", 49, 200),
            _row("f", "retrying", "failed", 1, 999),
        ]
    )
    row = actual["retrying"]
    assert row["last_status"] == "failed"
    assert row["last_size_bytes"] == 200
    assert float(row["hours_since_backup"]) >= 24
    assert row["is_stale"] is True
    assert row["backup_count_7d"] == 2


def test_latest_success_started_at_is_the_recovery_point():
    latest_success = _row("success-later", "target", "success", 3, 321)
    actual = _refresh(
        [
            latest_success,
            _row("success-earlier", "target", "success", 6, 123),
            _row("failure-latest", "target", "failed", 1, 999),
        ]
    )
    row = actual["target"]
    assert row["last_backup_at"].isoformat() == latest_success["started_at"]
    assert row["last_size_bytes"] == 321
    assert row["last_status"] == "failed"
    assert row["is_stale"] is False


def test_observation_window_and_attempt_order():
    actual = _refresh(
        [
            _row("new", "ordered", "partial", 1, 4),
            _row("old", "ordered", "failed", 192, 5),
            _row("middle", "ordered", "failed", 2, 6),
            _row("only-old", "older-only", "failed", 192, 7),
        ]
    )
    assert set(actual) == {"ordered", "older-only"}
    assert actual["ordered"]["last_status"] == "partial"
    assert actual["ordered"]["backup_count_7d"] == 2
    assert actual["older-only"]["backup_count_7d"] == 0
    assert actual["older-only"]["last_status"] == "failed"
    assert actual["older-only"]["last_backup_at"] is None
    assert actual["older-only"]["hours_since_backup"] is None
    assert actual["older-only"]["is_stale"] is True
