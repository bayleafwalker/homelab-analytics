"""The API never keeps the DuckDB warehouse open: read-only short-lived handles,
503 under a held write lock, and backups that succeed while the API serves reads."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import build_app
from packages.pipelines.warehouse_session import (
    WarehouseSessionManager,
    WarehouseSessionTransformationService,
    build_read_only_aware_service_factory,
)
from packages.shared.metrics import MetricsRegistry, metrics_registry
from packages.shared.settings import AppSettings
from packages.storage.duckdb_store import WarehouseBusyError

ROOT = Path(__file__).resolve().parents[1]
REPORT = "/reports/monthly-cashflow"

_OPEN = """
import sys, duckdb
connection = duckdb.connect(sys.argv[1], read_only=sys.argv[2] == "ro")
connection.execute("SELECT 1").fetchall()
connection.close()
print("opened", flush=True)
"""

_HOLD_WRITE_LOCK = """
import sys, duckdb
connection = duckdb.connect(sys.argv[1])
print("locked", flush=True)
sys.stdin.readline()
connection.close()
"""


def _settings(root: Path, **overrides: object) -> AppSettings:
    base = AppSettings(
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
        worker_poll_interval_seconds=30,
        api_warehouse_idle_seconds=60.0,
        warehouse_lock_retry_attempts=2,
        warehouse_lock_retry_backoff_seconds=0.01,
    )
    from dataclasses import replace

    return replace(base, **overrides)  # type: ignore[arg-type]


def _open_from_other_process(path: Path, mode: str) -> bool:
    completed = subprocess.run(
        [sys.executable, "-c", _OPEN, str(path), mode],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return completed.returncode == 0 and "opened" in completed.stdout


def _manager(app_client: TestClient) -> WarehouseSessionManager:
    service = app_client.app.state.warehouse_transformation_service  # type: ignore[attr-defined]
    assert isinstance(service, WarehouseSessionTransformationService)
    return service.warehouse_sessions


@pytest.fixture()
def api(tmp_path: Path):
    settings = _settings(tmp_path)
    app = build_app(settings)
    with TestClient(app) as client:
        yield client, settings
    _manager(client).stop()


def test_handle_is_released_after_a_warehouse_read(api) -> None:
    client, settings = api
    warehouse = settings.resolved_analytics_database_path

    response = client.get(REPORT)

    assert response.status_code == 200, response.text
    assert _manager(client).mode is None
    assert _open_from_other_process(warehouse, "ro")
    # Even a writer can attach: the API holds no handle between requests.
    assert _open_from_other_process(warehouse, "rw")
    text = metrics_registry.render_prometheus_text()
    assert 'homelab_analytics_api_warehouse_handle_open{mode="read_only"} 0' in text
    assert 'homelab_analytics_api_warehouse_handle_open{mode="read_write"} 0' in text


def test_reads_return_503_while_another_process_holds_the_write_lock(api) -> None:
    client, settings = api
    assert client.get(REPORT).status_code == 200  # schema bootstrapped
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLD_WRITE_LOCK, str(settings.resolved_analytics_database_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None and holder.stdout.readline().strip() == "locked"
        busy = client.get(REPORT)
    finally:
        assert holder.stdin is not None
        holder.stdin.write("\n")
        holder.stdin.close()
        holder.wait(timeout=30)

    assert busy.status_code == 503
    assert busy.headers["Retry-After"] == "5"
    assert "busy" in busy.json()["error"]
    assert client.get(REPORT).status_code == 200


def test_backup_succeeds_while_the_api_serves_warehouse_reads(api) -> None:
    client, settings = api
    assert client.get(REPORT).status_code == 200
    stop = threading.Event()
    statuses: list[int] = []

    def serve_reads() -> None:
        while not stop.is_set():
            statuses.append(client.get(REPORT).status_code)

    reader = threading.Thread(target=serve_reads)
    reader.start()
    try:
        backup = subprocess.run(
            [sys.executable, "-m", "apps.worker.main", "scheduled-backup"],
            cwd=ROOT,
            env={**os.environ, "HOMELAB_ANALYTICS_DATA_DIR": str(settings.data_dir)},
            capture_output=True,
            text=True,
            timeout=120,
        )
    finally:
        stop.set()
        reader.join(timeout=30)

    assert backup.returncode == 0, backup.stderr
    assert '"succeeded": true' in backup.stdout
    assert statuses and set(statuses) == {200}


# ---------------------------------------------------------------------------
# Manager unit behaviour
# ---------------------------------------------------------------------------


def _unit_manager(tmp_path: Path, **kwargs: object) -> tuple[WarehouseSessionManager, MetricsRegistry]:
    registry = MetricsRegistry()
    manager = WarehouseSessionManager(
        tmp_path / "warehouse.duckdb",
        build_read_only_aware_service_factory(),
        registry=registry,
        lock_retry_attempts=2,
        lock_retry_backoff_seconds=0.01,
        **kwargs,  # type: ignore[arg-type]
    )
    return manager, registry


def test_reads_use_read_only_and_writes_read_write_then_release(tmp_path: Path) -> None:
    manager, registry = _unit_manager(tmp_path)
    service = WarehouseSessionTransformationService(manager)
    seen: list[str | None] = []

    manager.begin_request()
    assert service.count_transactions() == 0
    seen.append(manager.mode)
    service.store.execute("CREATE TABLE IF NOT EXISTS probe (x INTEGER)")
    seen.append(manager.mode)
    assert service.store.fetchall("SELECT count(*) FROM probe") == [(0,)]
    seen.append(manager.mode)
    manager.end_request()

    assert seen == ["read_only", "read_write", "read_write"]
    assert manager.mode is None
    text = registry.render_prometheus_text()
    assert 'homelab_analytics_api_warehouse_opens_total{mode="read_only"} 1' in text
    assert 'homelab_analytics_api_warehouse_opens_total{mode="read_write"} 1' in text


def test_misclassified_write_is_retried_read_write(tmp_path: Path) -> None:
    manager, registry = _unit_manager(tmp_path, idle_timeout_seconds=0)
    service = WarehouseSessionTransformationService(manager)
    service.count_transactions()  # bootstrap + read-only

    # A "read" that writes: the read-only handle rejects it, the call is redone.
    result = manager.call(
        "get_but_writes",
        lambda svc: (svc.store.execute("CREATE TABLE written (x INTEGER)"), "ok")[1],
        write=False,
    )

    assert result == "ok"
    assert manager.mode is None  # idle timeout 0: released immediately
    assert 'write_upgrades_total{method="get_but_writes"} 1' in registry.render_prometheus_text()


def test_idle_reaper_closes_background_handles(tmp_path: Path) -> None:
    clock = {"t": 0.0}
    manager, _ = _unit_manager(tmp_path, idle_timeout_seconds=5, monotonic=lambda: clock["t"])
    service = WarehouseSessionTransformationService(manager)

    service.count_transactions()  # outside any request: kept for reuse
    assert manager.mode == "read_only"
    clock["t"] = 3
    assert manager.close_if_idle() is False
    clock["t"] = 6
    assert manager.close_if_idle() is True
    assert manager.mode is None


def test_lock_conflict_raises_busy_after_retries(tmp_path: Path) -> None:
    manager, registry = _unit_manager(tmp_path)
    service = WarehouseSessionTransformationService(manager)
    service.count_transactions()
    manager.close()
    proc = subprocess.Popen(
        [sys.executable, "-c", _HOLD_WRITE_LOCK, str(tmp_path / "warehouse.duckdb")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert proc.stdout is not None and proc.stdout.readline().strip() == "locked"
        with pytest.raises(WarehouseBusyError):
            service.count_transactions()
    finally:
        assert proc.stdin is not None
        proc.stdin.write("\n")
        proc.stdin.close()
        proc.wait(timeout=30)

    assert manager.mode is None
    assert "homelab_analytics_api_warehouse_busy_total 1" in registry.render_prometheus_text()


# ---------------------------------------------------------------------------
# Read/write classification covers every facet method
# ---------------------------------------------------------------------------

# Verbs that mutate the warehouse. A new facet verb must be added here or to
# READ_METHOD_PREFIXES deliberately, so nothing is classified by accident.
_WRITE_VERBS = frozenset(
    {
        "add",
        "archive",
        "create",
        "ensure",
        "ingest",
        "load",
        "populate",
        "record",
        "refresh",
        "remove",
        "restore",
        "set",
        "update",
        "upsert",
    }
)


def _public_service_methods() -> dict[str, type]:
    import inspect

    from packages.pipelines.transformation_service import TransformationService

    methods: dict[str, type] = {}
    for name, _ in inspect.getmembers(TransformationService, callable):
        if name.startswith("_"):
            continue
        owner = next(k for k in TransformationService.__mro__ if name in k.__dict__)
        methods[name] = owner
    return methods


def test_every_facet_method_has_an_explicit_read_or_write_classification() -> None:
    from packages.pipelines.warehouse_session import READ_METHOD_PREFIXES, is_read_method

    methods = _public_service_methods()
    owners = {owner.__module__ for owner in methods.values()}
    # The facets split by PR #41 are all covered, not just the service module.
    assert any(module.startswith("packages.pipelines.transformation_facets.") for module in owners)
    read_verbs = {prefix.rstrip("_") for prefix in READ_METHOD_PREFIXES}
    unclassified = sorted(
        f"{owner.__name__}.{name}"
        for name, owner in methods.items()
        if name.split("_", 1)[0] not in read_verbs | _WRITE_VERBS
    )
    assert unclassified == []
    misread = sorted(
        name
        for name in methods
        if is_read_method(name) and name.split("_", 1)[0] in _WRITE_VERBS
    )
    assert misread == []


def test_read_named_methods_that_issue_ddl_are_classified_as_writes() -> None:
    import inspect
    import re

    from packages.pipelines.transformation_service import TransformationService
    from packages.pipelines.warehouse_session import (
        READ_METHOD_PREFIXES,
        READ_NAMED_WRITE_METHODS,
    )

    writes = re.compile(r"ensure_\w+\(|\bCREATE\b|\bINSERT\b|\bUPDATE\b|\bDELETE\b")
    found: set[str] = set()
    for name in _public_service_methods():
        if not name.startswith(READ_METHOD_PREFIXES):
            continue
        method = getattr(TransformationService, name)
        source = inspect.getsource(method)
        module = inspect.getmodule(method)
        # Facet methods delegate to a domain function; scan one level deep.
        for callee in re.findall(r"return\s+([a-z_][a-z0-9_]*)\(", source):
            target = getattr(module, callee, None)
            if inspect.isfunction(target):
                source += inspect.getsource(target)
        if writes.search(source):
            found.add(name)

    assert found == set(READ_NAMED_WRITE_METHODS)


def test_read_classified_facet_methods_run_on_a_read_only_handle(tmp_path: Path) -> None:
    import inspect

    from packages.pipelines.warehouse_session import is_read_method

    manager, registry = _unit_manager(tmp_path, idle_timeout_seconds=60)
    service = WarehouseSessionTransformationService(manager)
    service.count_transactions()  # bootstrap the schema, then read-only
    called: list[str] = []
    needed_write: list[str] = []
    for name in sorted(_public_service_methods()):
        if not is_read_method(name):
            continue
        from packages.pipelines.transformation_service import TransformationService

        signature = inspect.signature(getattr(TransformationService, name))
        required = [
            parameter
            for parameter in list(signature.parameters.values())[1:]
            if parameter.default is inspect.Parameter.empty
            and parameter.kind not in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD)
        ]
        if required:
            continue
        getattr(service, name)()
        if manager.mode != "read_only":
            needed_write.append(name)
            manager.close()
        called.append(name)
    manager.close()

    assert len(called) > 50
    assert needed_write == [], needed_write
