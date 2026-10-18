"""Off-site shipment status: the backup-ship sidecar writes it, /metrics exports it."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from apps.worker.ops import WorkerMetricsServer
from packages.application.use_cases.ops_metrics import (
    collect_backup_ship_metrics,
    collect_backup_status_metrics,
)
from packages.shared.metrics import MetricsRegistry
from packages.storage.backup_ship import (
    SHIP_STATUS_FILENAME,
    SHIPPED_STATE_FILENAME,
    pending_bundle_names,
    read_ship_status,
)

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENT_PROPOSAL = ROOT / "docs" / "notes" / "appservice-proposals" / "deployment.yaml"


def _bundle(backup_dir: Path, name: str) -> Path:
    bundle = backup_dir / name
    (bundle / "warehouse").mkdir(parents=True)
    (bundle / "manifest.json").write_text("{}\n")
    (bundle / "warehouse" / "warehouse.duckdb").write_bytes(b"x" * 64)
    return bundle


def _write_status(backup_dir: Path, **fields: object) -> None:
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / SHIP_STATUS_FILENAME).write_text(json.dumps(fields))


def test_absent_status_exports_only_presence(tmp_path: Path) -> None:
    registry = MetricsRegistry()

    collect_backup_ship_metrics(registry, tmp_path / "backups")

    text = registry.render_prometheus_text()
    assert "homelab_analytics_backup_ship_status_present 0" in text
    assert "homelab_analytics_backup_ship_last_success_timestamp_seconds" not in text
    assert "homelab_analytics_backup_ship_pending_bundles" not in text


def test_status_and_pending_bundles_are_exported(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    _bundle(backups, "backup-20261017T000000Z")
    _bundle(backups, "backup-20261018T000000Z")
    (backups / "backup-20261018T010000Z").mkdir()  # incomplete: no manifest
    (backups / SHIPPED_STATE_FILENAME).write_text("backup-20261017T000000Z\n")
    _write_status(
        backups,
        last_pass_at="2026-10-18T00:15:00Z",
        last_attempt_at="2026-10-17T00:10:00Z",
        last_success_at="2026-10-17T00:11:00Z",
        last_failure_at=None,
        last_error=None,
        last_shipped_bundle="backup-20261017T000000Z",
        last_size_bytes=4096,
        consecutive_failures=0,
        shipped_total=7,
        failures_total=2,
    )
    registry = MetricsRegistry()

    collect_backup_status_metrics(registry, backups)

    text = registry.render_prometheus_text()
    success = int(datetime(2026, 10, 17, 0, 11, tzinfo=UTC).timestamp())
    assert "homelab_analytics_backup_ship_status_present 1" in text
    assert f"homelab_analytics_backup_ship_last_success_timestamp_seconds {success}" in text
    assert "homelab_analytics_backup_ship_last_failure_timestamp_seconds 0" in text
    assert "homelab_analytics_backup_ship_pending_bundles 1" in text
    assert "homelab_analytics_backup_ship_last_size_bytes 4096" in text
    assert "# TYPE homelab_analytics_backup_ship_shipped_total counter" in text
    assert "homelab_analytics_backup_ship_shipped_total 7" in text
    assert "homelab_analytics_backup_ship_failures_total 2" in text
    assert pending_bundle_names(backups) == ["backup-20261018T000000Z"]


@pytest.mark.parametrize("content", ["not json", "[1, 2]", ""])
def test_unreadable_status_counts_as_absent(tmp_path: Path, content: str) -> None:
    (tmp_path / SHIP_STATUS_FILENAME).write_text(content)

    assert read_ship_status(tmp_path) is None
    registry = MetricsRegistry()
    collect_backup_ship_metrics(registry, tmp_path)
    assert "homelab_analytics_backup_ship_status_present 0" in registry.render_prometheus_text()


def test_bad_field_types_degrade_to_defaults(tmp_path: Path) -> None:
    _write_status(tmp_path, last_success_at=5, consecutive_failures="x", shipped_total=True)

    status = read_ship_status(tmp_path)

    assert status is not None
    assert status.last_success_at is None
    assert status.consecutive_failures == 0
    assert status.shipped_total == 0


def test_worker_metrics_endpoint_exports_ship_status(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    _bundle(backups, "backup-20261018T000000Z")
    _write_status(backups, last_success_at="2026-10-18T00:05:00Z", consecutive_failures=0)
    server = WorkerMetricsServer(
        host="127.0.0.1", port=0, token=None, registry=MetricsRegistry(), backup_dir=backups
    )
    server.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.port}/metrics", timeout=10) as response:
            body = response.read().decode()
    finally:
        server.stop()

    success = int(datetime(2026, 10, 18, 0, 5, tzinfo=UTC).timestamp())
    assert "homelab_analytics_backup_ship_status_present 1" in body
    assert f"homelab_analytics_backup_ship_last_success_timestamp_seconds {success}" in body
    assert "homelab_analytics_backup_ship_pending_bundles 1" in body


# ---------------------------------------------------------------------------
# Contract: the proposal sidecar script writes a file this reader understands.
# ---------------------------------------------------------------------------


def _sidecar() -> tuple[str, dict[str, str]]:
    deployment = yaml.safe_load(DEPLOYMENT_PROPOSAL.read_text())
    containers = deployment["spec"]["template"]["spec"]["containers"]
    sidecar = next(c for c in containers if c["name"] == "backup-ship")
    env = {item["name"]: item["value"] for item in sidecar["env"] if "value" in item}
    return sidecar["args"][0], env


def test_sidecar_script_has_no_flux_substituted_expansions() -> None:
    script, env = _sidecar()

    # Flux postBuild substitution runs on this file; "${x}" would be blanked.
    assert "${" not in script
    assert env["BACKUP_DIR"] == "/data/backups"
    assert env["TOOLS_DIR"] == "/tools"


def _stub(path: Path, body: str) -> None:
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


def _run_sidecar_until(
    tmp_path: Path, predicate: Callable[[], bool], *, fail_upload: bool = False, timeout: float = 20.0
) -> None:
    script, env = _sidecar()
    stubs = tmp_path / "stubs"
    tools = tmp_path / "tools"
    remote = tmp_path / "remote"
    for directory in (stubs, tools, remote):
        directory.mkdir(exist_ok=True)
    _stub(tools / "age", "cat\n")
    _stub(
        stubs / "rclone",
        'for a; do last="$a"; done\n'
        'case "$1" in\n'
        '  rcat) [ -n "${RCLONE_FAIL:-}" ] && { cat >/dev/null; exit 1; }\n'
        '        cat > "$STUB_REMOTE/$(basename "$last")" ;;\n'
        '  size) printf \'{"count":1,"bytes":%s}\\n\' "$(wc -c < "$STUB_REMOTE/$(basename "$last")")" ;;\n'
        "  delete) exit 0 ;;\n"
        "esac\n",
    )
    run_env = {
        **os.environ,
        **env,
        "BACKUP_DIR": str(tmp_path / "backups"),
        "TOOLS_DIR": str(tools),
        "SHIP_INTERVAL_SECONDS": "1",
        "STUB_REMOTE": str(remote),
        "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
    }
    if fail_upload:
        run_env["RCLONE_FAIL"] = "1"
    process = subprocess.Popen(
        [*_SIDECAR_SHELL, "-c", script],
        env=run_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            if process.poll() is not None:
                break
            time.sleep(0.1)
        output = process.stdout.read().decode() if process.poll() is not None else ""  # type: ignore[union-attr]
        pytest.fail(f"sidecar never reached the expected state; output: {output}")
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


def _sidecar_shell() -> list[str] | None:
    """A shell with `set -o pipefail`, like the rclone image's busybox ash.

    Plain `sh` is dash on Debian/Ubuntu runners, which rejects pipefail.
    """
    if shutil.which("busybox"):
        return ["busybox", "sh"]
    if shutil.which("bash"):
        return ["bash"]
    return None


_SIDECAR_SHELL = _sidecar_shell() or ["sh"]
_NEEDS_SHELL = pytest.mark.skipif(
    _sidecar_shell() is None or shutil.which("tar") is None,
    reason="needs busybox or bash, and tar",
)


@_NEEDS_SHELL
def test_sidecar_records_a_pass_before_the_backup_dir_exists(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    assert not backups.exists()

    def passed() -> bool:
        status = read_ship_status(backups)
        return status is not None and status.last_pass_at is not None

    _run_sidecar_until(tmp_path, passed)

    status = read_ship_status(backups)
    assert status is not None
    assert status.shipped_total == 0
    assert status.consecutive_failures == 0


@_NEEDS_SHELL
def test_sidecar_script_round_trips_status_through_reader(tmp_path: Path) -> None:
    backups = tmp_path / "backups"
    _bundle(backups, "backup-20261017T000000Z")
    # The stubbed remote size must clear the sidecar's 512-byte floor.
    (backups / "backup-20261017T000000Z" / "warehouse" / "warehouse.duckdb").write_bytes(b"x" * 4096)

    def shipped() -> bool:
        status = read_ship_status(backups)
        return status is not None and status.shipped_total == 1

    _run_sidecar_until(tmp_path, shipped)

    first = read_ship_status(backups)
    assert first is not None
    assert first.last_shipped_bundle == "backup-20261017T000000Z"
    assert first.last_success_at is not None
    assert first.last_pass_at is not None
    assert first.consecutive_failures == 0
    assert first.last_size_bytes >= 4096
    assert pending_bundle_names(backups) == []
    assert (tmp_path / "remote" / "backup-20261017T000000Z.tar.age").is_file()

    # A restart keeps the durable fields; failed uploads count up and do not
    # move last_success_at.
    _bundle(backups, "backup-20261018T000000Z")

    def failed_twice() -> bool:
        status = read_ship_status(backups)
        return status is not None and status.consecutive_failures >= 2

    _run_sidecar_until(tmp_path, failed_twice, fail_upload=True)

    second = read_ship_status(backups)
    assert second is not None
    assert second.last_success_at == first.last_success_at
    assert second.shipped_total == 1
    assert second.failures_total >= 2
    assert second.last_failure_at is not None
    assert second.last_error == "shipping backup-20261018T000000Z failed"
    assert pending_bundle_names(backups) == ["backup-20261018T000000Z"]
