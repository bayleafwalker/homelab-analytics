"""Scheduled backups: staging/verify/prune semantics, cross-process exclusion,
and the worker-loop-owned schedule producing a consistent, restorable bundle
without disturbing ingestion."""

from __future__ import annotations

import fcntl
import io
import json
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest

from apps.worker.main import main
from apps.worker.ops import WorkerMetricsServer, backup_sources_from_settings
from packages.shared.metrics import MetricsRegistry
from packages.shared.settings import AppSettings
from packages.storage import backup_bundle
from packages.storage.backup_bundle import BackupSources, restore_backup, verify_backup
from packages.storage.backup_schedule import (
    BACKUP_STATUS_FILENAME,
    LOCK_FILENAME,
    BackupSchedulePolicy,
    BackupStatus,
    backup_due,
    list_bundles,
    read_backup_status,
    run_scheduled_backup,
)
from packages.storage.blob import PARTIAL_WRITE_SUFFIX, FilesystemBlobStore
from packages.storage.ingestion_config import (
    IngestionConfigRepository,
    IngestionDefinitionCreate,
)
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES
from tests.control_plane_test_support import FIXED_CREATED_AT, seed_source_asset_graph

T0 = datetime(2026, 10, 18, 3, 0, tzinfo=UTC)


def _sources(root: Path) -> BackupSources:
    return BackupSources(
        control_plane_backend="sqlite",
        reporting_backend="duckdb",
        blob_backend="filesystem",
        control_plane_database_path=root / "config.db",
        warehouse_database_path=root / "analytics" / "warehouse.duckdb",
        landing_root=root / "landing",
    )


def _seed_warehouse(path: Path, rows: int = 3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(path))
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS facts (id INTEGER, label VARCHAR)")
        for index in range(rows):
            connection.execute("INSERT INTO facts VALUES (?, ?)", [index, f"row-{index}"])
    finally:
        connection.close()


def _policy(root: Path, *, interval: int = 3600, retention: int = 2) -> BackupSchedulePolicy:
    return BackupSchedulePolicy(root / "backups", interval_seconds=interval, retention_count=retention)


# ---------------------------------------------------------------------------
# Schedule decisions
# ---------------------------------------------------------------------------


def test_backup_due_respects_interval_and_failure_backoff(tmp_path: Path) -> None:
    policy = _policy(tmp_path, interval=3600)
    assert backup_due(policy, None, now=T0) is True
    assert backup_due(replace(policy, interval_seconds=0), None, now=T0) is False

    succeeded = BackupStatus(last_attempt_at="2026-10-18T03:00:00Z", last_success_at="2026-10-18T03:00:00Z")
    assert backup_due(policy, succeeded, now=T0 + timedelta(minutes=59)) is False
    assert backup_due(policy, succeeded, now=T0 + timedelta(minutes=60)) is True

    failed = BackupStatus(
        last_attempt_at="2026-10-18T04:00:00Z",
        last_success_at="2026-10-18T02:00:00Z",
        last_failure_at="2026-10-18T04:00:00Z",
    )
    # Overdue, but a recent failure backs off for min(interval, 15 min).
    assert backup_due(policy, failed, now=T0 + timedelta(minutes=70)) is False
    assert backup_due(policy, failed, now=T0 + timedelta(minutes=75)) is True


# ---------------------------------------------------------------------------
# Staging, verification, retention, status
# ---------------------------------------------------------------------------


def test_scheduled_backup_publishes_verified_bundles_and_prunes(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    _seed_warehouse(sources.warehouse_database_path)
    FilesystemBlobStore(sources.landing_root).write_bytes("bank/2026/a.csv", b"a,b\n1,2\n")
    policy = _policy(tmp_path, retention=2)

    results = [
        run_scheduled_backup(sources, policy, now=T0 + timedelta(hours=hour), monotonic=lambda: 0.0)
        for hour in range(3)
    ]

    assert all(result.succeeded for result in results)
    bundles = list_bundles(policy.destination_root)
    assert [bundle.name for bundle in bundles] == [
        "backup-20261018T040000Z",
        "backup-20261018T050000Z",
    ]
    assert results[2].pruned == [policy.destination_root / "backup-20261018T030000Z"]
    assert not list(policy.destination_root.glob(".staging-*"))
    for bundle in bundles:
        assert verify_backup(bundle).passed
    status = read_backup_status(policy.destination_root)
    assert status is not None
    assert status.last_success_at == "2026-10-18T05:00:00Z"
    assert status.successes_total == 3
    assert status.bundles_retained == 2
    assert status.last_bundle == "backup-20261018T050000Z"


def test_failed_backup_records_status_and_leaves_no_partial_bundle(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    policy = _policy(tmp_path)

    def exploding_create(src: BackupSources, destination: Path, **kwargs: Any) -> dict[str, Any]:
        destination.mkdir(parents=True)
        (destination / "half-written").write_text("x")
        raise OSError("No space left on device")

    result = run_scheduled_backup(sources, policy, now=T0, create=exploding_create)

    assert result.succeeded is False
    assert "No space left" in (result.error or "")
    assert list_bundles(policy.destination_root) == []
    assert not list(policy.destination_root.glob(".staging-*"))
    status = read_backup_status(policy.destination_root)
    assert status is not None
    assert status.consecutive_failures == 1
    assert status.last_success_at is None
    assert status.failures_total == 1


def test_scheduled_backup_refuses_destination_inside_landing(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    policy = BackupSchedulePolicy(sources.landing_root / "backups", 3600, 2)

    result = run_scheduled_backup(sources, policy, now=T0)

    assert result.succeeded is False
    assert "inside the landing root" in (result.error or "")


def test_only_one_scheduled_backup_runs_at_a_time(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    policy = _policy(tmp_path)
    policy.destination_root.mkdir(parents=True)
    with (policy.destination_root / LOCK_FILENAME).open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        result = run_scheduled_backup(sources, policy, now=T0)

    assert result.succeeded is False
    assert "already running" in (result.error or "")


def test_in_flight_blob_writes_are_not_captured(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    store = FilesystemBlobStore(sources.landing_root)
    store.write_bytes("bank/complete.csv", b"done\n")
    assert not list(sources.landing_root.rglob(f"*{PARTIAL_WRITE_SUFFIX}"))
    # Simulate a payload an API upload is still writing.
    (sources.landing_root / "bank" / f".pending.csv.abc{PARTIAL_WRITE_SUFFIX}").write_bytes(b"ha")

    result = run_scheduled_backup(sources, _policy(tmp_path), now=T0)

    assert result.succeeded and result.bundle_dir is not None
    manifest = json.loads((result.bundle_dir / "manifest.json").read_text())
    landing = next(c for c in manifest["components"] if c["name"] == "landing_filesystem")
    assert [entry["path"] for entry in landing["files"]] == ["landing/bank/complete.csv"]


# ---------------------------------------------------------------------------
# Cross-process exclusion on the DuckDB warehouse
# ---------------------------------------------------------------------------

_HOLD_WRITE_LOCK = """
import sys, duckdb
connection = duckdb.connect(sys.argv[1])
connection.execute("INSERT INTO facts VALUES (99, 'held')")
print("locked", flush=True)
sys.stdin.readline()
connection.close()
"""

_TRY_WRITE = """
import sys, duckdb
try:
    connection = duckdb.connect(sys.argv[1])
except duckdb.Error as exc:
    print("blocked", flush=True)
else:
    connection.execute("INSERT INTO facts VALUES (100, 'raced')")
    connection.close()
    print("wrote", flush=True)
"""


def test_backup_fails_cleanly_while_another_process_holds_the_warehouse(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    _seed_warehouse(sources.warehouse_database_path)
    policy = replace(_policy(tmp_path), lock_retry_attempts=3, lock_retry_backoff_seconds=0.05)
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_WRITE_LOCK, str(sources.warehouse_database_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "locked"
        blocked = run_scheduled_backup(sources, policy, now=T0)
    finally:
        assert holder.stdin is not None
        holder.stdin.write("\n")
        holder.stdin.close()
        holder.wait(timeout=30)

    assert blocked.succeeded is False
    assert "read-only" in (blocked.error or "")
    assert list_bundles(policy.destination_root) == []

    # The holder's write was untouched; once it exits the retry succeeds.
    retried = run_scheduled_backup(sources, policy, now=T0 + timedelta(minutes=20))
    assert retried.succeeded
    status = read_backup_status(policy.destination_root)
    assert status is not None and status.consecutive_failures == 0
    connection = duckdb.connect(str(sources.warehouse_database_path), read_only=True)
    try:
        assert connection.execute("SELECT count(*) FROM facts").fetchone() == (4,)
    finally:
        connection.close()


_HOLD_WRITE_LOCK_BRIEFLY = """
import sys, time, duckdb
connection = duckdb.connect(sys.argv[1])
print("locked", flush=True)
time.sleep(float(sys.argv[2]))
connection.close()
"""


def test_backup_retries_a_brief_lock_inside_the_same_attempt(tmp_path: Path) -> None:
    sources = _sources(tmp_path)
    _seed_warehouse(sources.warehouse_database_path)
    # 0.2 + 0.4 + 0.8 + 1.6 s of backoff outlasts a 1 s writer.
    policy = replace(_policy(tmp_path), lock_retry_attempts=5, lock_retry_backoff_seconds=0.2)
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_WRITE_LOCK_BRIEFLY, str(sources.warehouse_database_path), "1.0"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "locked"
        result = run_scheduled_backup(sources, policy, now=T0)
    finally:
        holder.wait(timeout=30)

    assert result.succeeded, result.error
    status = read_backup_status(policy.destination_root)
    assert status is not None
    assert status.failures_total == 0 and status.consecutive_failures == 0


def test_writers_are_excluded_while_the_warehouse_is_copied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sources = _sources(tmp_path)
    _seed_warehouse(sources.warehouse_database_path)
    attempts: list[str] = []
    real_copy = backup_bundle.shutil.copyfile

    def copy_while_racing(src: Any, dst: Any, *args: Any, **kwargs: Any) -> Any:
        if str(src) == str(sources.warehouse_database_path):
            race = subprocess.run(
                [sys.executable, "-c", _TRY_WRITE, str(sources.warehouse_database_path)],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            attempts.append(race.stdout.strip())
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(backup_bundle.shutil, "copyfile", copy_while_racing)
    result = run_scheduled_backup(sources, _policy(tmp_path), now=T0)

    assert attempts == ["blocked"]
    assert result.succeeded and result.bundle_dir is not None
    copied = duckdb.connect(str(result.bundle_dir / "warehouse" / "warehouse.duckdb"), read_only=True)
    try:
        assert copied.execute("SELECT count(*) FROM facts").fetchone() == (3,)
    finally:
        copied.close()


# ---------------------------------------------------------------------------
# Worker-loop-owned schedule
# ---------------------------------------------------------------------------


def _worker_settings(root: Path) -> AppSettings:
    return AppSettings(
        data_dir=root,
        landing_root=root / "landing",
        metadata_database_path=root / "metadata" / "runs.db",
        account_transactions_inbox_dir=root / "inbox" / "account-transactions",
        processed_files_dir=root / "processed" / "account-transactions",
        failed_files_dir=root / "failed" / "account-transactions",
        api_host="127.0.0.1",
        api_port=8080,
        web_host="127.0.0.1",
        web_port=8081,
        worker_poll_interval_seconds=0,
        backup_interval_seconds=3600,
        backup_retention_count=3,
    )


def _configure_watch_definition(root: Path, repository: IngestionConfigRepository) -> Path:
    seeded = seed_source_asset_graph(repository)
    inbox = root / "watch-inbox"
    inbox.mkdir()
    repository.update_ingestion_definition(
        IngestionDefinitionCreate(
            ingestion_definition_id=seeded["ingestion_definition"].ingestion_definition_id,
            source_asset_id=seeded["source_asset"].source_asset_id,
            transport="filesystem",
            schedule_mode="watch-folder",
            source_path=str(inbox),
            file_pattern="*.csv",
            processed_path=str(root / "watch-processed"),
            failed_path=str(root / "watch-failed"),
            poll_interval_seconds=30,
            enabled=True,
            source_name="folder-watch",
            created_at=FIXED_CREATED_AT,
        )
    )
    return inbox


def _json_documents(text: str) -> list[dict[str, Any]]:
    decoder = json.JSONDecoder()
    documents: list[dict[str, Any]] = []
    index = 0
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        document, index = decoder.raw_decode(text, index)
        documents.append(document)
    return documents


def _warehouse_counts(path: Path) -> dict[str, int]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' ORDER BY table_name"
            ).fetchall()
        ]
        return {
            table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in tables
        }
    finally:
        connection.close()


def _watch(settings: AppSettings, iterations: int) -> tuple[int, list[dict[str, Any]]]:
    stdout = io.StringIO()
    exit_code = main(
        [
            "watch-schedule-dispatches",
            "--worker-id",
            "worker-backup",
            "--max-iterations",
            str(iterations),
        ],
        stdout=stdout,
        stderr=io.StringIO(),
        settings=settings,
    )
    return exit_code, _json_documents(stdout.getvalue())


def test_worker_loop_backs_up_between_dispatches_without_disturbing_ingestion(
    tmp_path: Path,
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    settings = _worker_settings(root)
    repository = IngestionConfigRepository(settings.resolved_config_database_path)
    inbox = _configure_watch_definition(root, repository)
    (inbox / "first.csv").write_text(
        (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
    )

    # Iteration 1 processes the dispatch (promotion writes the warehouse);
    # iteration 2 is idle, which is where the scheduled backup runs.
    exit_code, payloads = _watch(settings, 2)

    assert exit_code == 0
    assert payloads[0]["dispatch"]["status"] == "completed"
    assert "scheduled_backup" not in payloads[0]
    assert payloads[1]["scheduled_backup"]["succeeded"] is True, payloads[1]
    bundle = settings.resolved_backup_dir / payloads[1]["scheduled_backup"]["bundle"]
    assert verify_backup(bundle).passed
    live_counts = _warehouse_counts(settings.resolved_analytics_database_path)
    assert sum(live_counts.values()) > 0

    # The bundle restores into a scratch instance with the same warehouse
    # contents and the same landed payloads.
    scratch = tmp_path / "scratch"
    restore_backup(bundle, backup_sources_from_settings(_worker_settings(scratch)))
    assert _warehouse_counts(scratch / "analytics" / "warehouse.duckdb") == live_counts
    live_landing = sorted(
        p.relative_to(settings.landing_root).as_posix()
        for p in settings.landing_root.rglob("*")
        if p.is_file()
    )
    restored_landing = sorted(
        p.relative_to(scratch / "landing").as_posix()
        for p in (scratch / "landing").rglob("*")
        if p.is_file()
    )
    assert restored_landing == live_landing and live_landing

    # Ingestion keeps working after the backup: a later dispatch completes and
    # the warehouse is still writable and readable.
    (inbox / "second.csv").write_text(
        (ACCOUNT_FIXTURES / "configured_account_transactions_source.csv").read_text()
    )
    repository.enqueue_due_execution_schedules(as_of=datetime.now(UTC) + timedelta(days=400))
    exit_code, payloads = _watch(settings, 1)
    assert exit_code == 0
    assert payloads[0]["dispatch"]["status"] == "completed"
    after_counts = _warehouse_counts(settings.resolved_analytics_database_path)
    assert set(after_counts) >= set(live_counts)
    # Not due again within the interval: no second bundle.
    assert len(list_bundles(settings.resolved_backup_dir)) == 1


def test_worker_loop_without_schedule_never_backs_up(tmp_path: Path) -> None:
    settings = replace(_worker_settings(tmp_path), backup_interval_seconds=0)

    exit_code, payloads = _watch(settings, 1)

    assert exit_code == 0
    assert "scheduled_backup" not in payloads[0]
    assert not settings.resolved_backup_dir.exists()


def test_scheduled_backup_command_and_worker_metrics_endpoint(tmp_path: Path) -> None:
    settings = _worker_settings(tmp_path)
    _seed_warehouse(settings.resolved_analytics_database_path)
    stdout = io.StringIO()

    exit_code = main(["scheduled-backup"], stdout=stdout, stderr=io.StringIO(), settings=settings)

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())["scheduled_backup"]
    assert payload["succeeded"] is True
    assert (settings.resolved_backup_dir / BACKUP_STATUS_FILENAME).is_file()

    server = WorkerMetricsServer(
        host="127.0.0.1",
        port=0,
        token="scrape-me",
        registry=MetricsRegistry(),
        backup_dir=settings.resolved_backup_dir,
    )
    server.start()
    try:
        url = f"http://127.0.0.1:{server.port}/metrics"
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(url, timeout=10)
        assert denied.value.code == 401
        request = urllib.request.Request(url, headers={"Authorization": "Metrics scrape-me"})
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode()
    finally:
        server.stop()

    assert "homelab_analytics_backup_last_success_timestamp_seconds " in body
    assert "homelab_analytics_backup_status_present 1" in body


# ---------------------------------------------------------------------------
# Restore drill
# ---------------------------------------------------------------------------


def test_restore_drill_restores_newest_bundle_into_scratch(tmp_path: Path) -> None:
    settings = _worker_settings(tmp_path / "live")
    _seed_warehouse(settings.resolved_analytics_database_path, rows=5)
    FilesystemBlobStore(settings.landing_root).write_bytes("bank/a.csv", b"x\n")
    assert main(["scheduled-backup"], stdout=io.StringIO(), stderr=io.StringIO(), settings=settings) == 0
    live_before = sorted(p.name for p in settings.data_dir.rglob("*"))
    stdout = io.StringIO()

    exit_code = main(["restore-drill"], stdout=stdout, stderr=io.StringIO(), settings=settings)

    assert exit_code == 0
    receipt = json.loads(stdout.getvalue())["restore_drill"]
    assert receipt["passed"] is True, receipt
    assert receipt["warehouse_tables"] == {"main.facts": 5}
    assert receipt["landing_files"] == 1
    assert not Path(receipt["scratch_dir"]).exists()
    # The live instance is untouched apart from the drill receipt.
    live_after = sorted(p.name for p in settings.data_dir.rglob("*"))
    assert sorted(set(live_after) - set(live_before)) == ["restore-drill-status.json"]

    registry = MetricsRegistry()
    from packages.application.use_cases.ops_metrics import collect_backup_status_metrics

    collect_backup_status_metrics(registry, settings.resolved_backup_dir)
    text = registry.render_prometheus_text()
    assert "homelab_analytics_backup_restore_drill_last_passed 1" in text


def test_restore_drill_fails_on_tampered_bundle(tmp_path: Path) -> None:
    settings = _worker_settings(tmp_path)
    _seed_warehouse(settings.resolved_analytics_database_path)
    assert main(["scheduled-backup"], stdout=io.StringIO(), stderr=io.StringIO(), settings=settings) == 0
    bundle = list_bundles(settings.resolved_backup_dir)[-1]
    with (bundle / "warehouse" / "warehouse.duckdb").open("ab") as handle:
        handle.write(b"corrupt")
    stderr = io.StringIO()

    exit_code = main(["restore-drill"], stdout=io.StringIO(), stderr=stderr, settings=settings)

    assert exit_code == 1
    assert "failed verification" in stderr.getvalue()
