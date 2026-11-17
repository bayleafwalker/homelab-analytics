"""Machine-readable stdout/stderr contract for ``upgrade-reporting``.

The installed acceptance driver runs ``python -m apps.worker.main
upgrade-reporting`` as a real subprocess and parses its stdout with
``json.loads``, so this test exercises the global logging configuration: for
this maintenance command only, stdout carries exactly one completion JSON
object and worker/runtime logs go to stderr, with an honest nonzero exit on
refusal. Ordinary worker commands keep their existing stdout logging.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tests.test_reporting_upgrade import _legacy_warehouse


def _run_upgrade(warehouse: Path, *, check: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOMELAB_ANALYTICS_ANALYTICS_DATABASE_PATH"] = str(warehouse)
    env["HOMELAB_ANALYTICS_DATA_DIR"] = str(warehouse.parent / "data")
    argv = [sys.executable, "-m", "apps.worker.main", "upgrade-reporting"]
    if check:
        argv.append("--check")
    return subprocess.run(
        argv,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_subprocess_stdout_is_exactly_one_completion_json(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)

    result = _run_upgrade(warehouse)

    assert result.returncode == 0, (result.stdout, result.stderr)
    # json.loads raises on trailing/extra data, proving exactly one object.
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "complete" and receipt["phase"] == "done"
    # Worker logs stay on stderr, never mixed into the completion JSON.
    assert "worker command starting" in result.stderr


def test_subprocess_check_is_read_only_single_json(tmp_path: Path) -> None:
    warehouse = tmp_path / "warehouse.duckdb"
    _legacy_warehouse(warehouse)
    before = warehouse.read_bytes()

    result = _run_upgrade(warehouse, check=True)

    assert result.returncode == 0, (result.stdout, result.stderr)
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "check_ok"
    assert warehouse.read_bytes() == before


def test_subprocess_refusal_is_single_json_with_nonzero_exit(tmp_path: Path) -> None:
    warehouse = tmp_path / "absent.duckdb"  # never created

    result = _run_upgrade(warehouse)

    assert result.returncode == 2, (result.stdout, result.stderr)
    receipt = json.loads(result.stdout)
    assert receipt["status"] == "refused"
    assert "upgrade-reporting refused" in result.stderr
