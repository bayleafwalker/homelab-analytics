"""Round-trip and refusal tests for the worker backup / verify-backup / restore commands."""
from __future__ import annotations

import io
import json
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import Any

import duckdb
import pytest

from apps.worker.main import main
from packages.shared.settings import AppSettings
from packages.storage.backup_bundle import (
    BACKUP_FORMAT_VERSION,
    MANIFEST_FILENAME,
    current_schema_heads,
)
from tests.account_test_support import FIXTURES as ACCOUNT_FIXTURES


def _settings(root: Path) -> AppSettings:
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
        worker_poll_interval_seconds=30,
    )


def _run(argv: list[str], settings: AppSettings) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(argv, stdout=stdout, stderr=stderr, settings=settings)
    return exit_code, stdout.getvalue(), stderr.getvalue()


def _sqlite_rows(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    connection = sqlite3.connect(path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        return {
            table: sorted(
                connection.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr
            )
            for table in tables
        }
    finally:
        connection.close()


def _duckdb_rows(path: Path) -> dict[str, list[tuple[Any, ...]]]:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        tables = [
            (row[0], row[1])
            for row in connection.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' ORDER BY 1, 2"
            ).fetchall()
        ]
        return {
            f"{schema}.{table}": sorted(
                connection.execute(f'SELECT * FROM "{schema}"."{table}"').fetchall(),
                key=repr,
            )
            for schema, table in tables
        }
    finally:
        connection.close()


def _landing_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture()
def populated_backup(tmp_path: Path) -> tuple[AppSettings, Path]:
    source = _settings(tmp_path / "source")
    exit_code, _, stderr = _run(
        [
            "ingest-account-transactions",
            str(ACCOUNT_FIXTURES / "account_transactions_valid.csv"),
            "--source-name",
            "manual-upload",
        ],
        source,
    )
    assert exit_code == 0, stderr
    backup_dir = tmp_path / "backup"
    exit_code, stdout, stderr = _run(["backup", str(backup_dir)], source)
    assert exit_code == 0, stderr
    summary = json.loads(stdout)
    included = {c["name"] for c in summary["components"] if c["included"]}
    assert included == {"control_plane_sqlite", "warehouse_duckdb", "landing_filesystem"}
    return source, backup_dir


def test_backup_restore_round_trip_reproduces_sqlite_duckdb_and_landing(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    source, backup_dir = populated_backup
    manifest = json.loads((backup_dir / MANIFEST_FILENAME).read_text())
    assert manifest["format_version"] == BACKUP_FORMAT_VERSION
    assert manifest["schema_heads"] == current_schema_heads()
    landing_component = next(
        c for c in manifest["components"] if c["name"] == "landing_filesystem"
    )
    assert landing_component["files"], "expected landed payloads in the backup"
    assert all(len(entry["sha256"]) == 64 for entry in landing_component["files"])

    exit_code, stdout, stderr = _run(["verify-backup", str(backup_dir)], source)
    assert exit_code == 0, stderr
    assert json.loads(stdout)["verification"]["passed"] is True

    target = _settings(tmp_path / "target")
    exit_code, stdout, stderr = _run(["restore", str(backup_dir)], target)
    assert exit_code == 0, stderr
    restored = {item["name"] for item in json.loads(stdout)["restore"]["restored"]}
    assert restored == {"control_plane_sqlite", "warehouse_duckdb", "landing_filesystem"}
    # Run metadata stores absolute landing locators; a path change is surfaced.
    assert "Landing root differs" in stderr

    source_sqlite = _sqlite_rows(source.resolved_config_database_path)
    assert any(source_sqlite.values()), "source control plane should hold rows"
    assert _sqlite_rows(target.resolved_config_database_path) == source_sqlite

    source_duckdb = _duckdb_rows(source.resolved_analytics_database_path)
    assert any(source_duckdb.values()), "source warehouse should hold rows"
    assert _duckdb_rows(target.resolved_analytics_database_path) == source_duckdb

    assert _landing_files(target.landing_root) == _landing_files(source.landing_root)

    # The restored instance is usable through the normal runtime.
    _, source_runs, _ = _run(["list-runs"], source)
    exit_code, target_runs, stderr = _run(["list-runs"], target)
    assert exit_code == 0, stderr
    assert json.loads(target_runs) == json.loads(source_runs)


def test_verify_and_restore_refuse_checksum_mismatch(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    source, backup_dir = populated_backup
    landed = next((backup_dir / "landing").rglob("*.csv"))
    landed.write_bytes(landed.read_bytes().replace(b",", b";", 1))

    exit_code, stdout, stderr = _run(["verify-backup", str(backup_dir)], source)
    assert exit_code == 1
    assert json.loads(stdout)["verification"]["passed"] is False
    assert "Checksum mismatch" in stderr

    target = _settings(tmp_path / "target")
    exit_code, _, stderr = _run(["restore", str(backup_dir)], target)
    assert exit_code == 1
    assert "Checksum mismatch" in stderr
    assert not target.resolved_config_database_path.exists()
    assert not target.resolved_analytics_database_path.exists()


def test_restore_refuses_schema_version_mismatch(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    _, backup_dir = populated_backup
    manifest_path = backup_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["schema_heads"]["sqlite"] = "0001_initial_schema"
    manifest_path.write_text(json.dumps(manifest))

    target = _settings(tmp_path / "target")
    exit_code, _, stderr = _run(["restore", str(backup_dir)], target)
    assert exit_code == 1
    assert "Schema version mismatch for control_plane_sqlite" in stderr
    assert not target.resolved_config_database_path.exists()


def test_restore_refuses_unsupported_format_version(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    source, backup_dir = populated_backup
    manifest_path = backup_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    manifest["format_version"] = BACKUP_FORMAT_VERSION + 1
    manifest_path.write_text(json.dumps(manifest))

    exit_code, _, stderr = _run(["verify-backup", str(backup_dir)], source)
    assert exit_code == 1
    assert "Unsupported backup format_version" in stderr


def test_restore_refuses_unsafe_manifest_paths(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    _, backup_dir = populated_backup
    manifest_path = backup_dir / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text())
    landing = next(c for c in manifest["components"] if c["name"] == "landing_filesystem")
    landing["files"][0]["path"] = "landing/../../escape.csv"
    manifest_path.write_text(json.dumps(manifest))

    target = _settings(tmp_path / "target")
    exit_code, _, stderr = _run(["restore", str(backup_dir)], target)
    assert exit_code == 1
    assert "Unsafe path" in stderr
    assert not (tmp_path / "escape.csv").exists()


def test_restore_refuses_non_empty_target_unless_forced(
    tmp_path: Path, populated_backup: tuple[AppSettings, Path]
) -> None:
    source, backup_dir = populated_backup
    target = _settings(tmp_path / "target")
    assert _run(["restore", str(backup_dir)], target)[0] == 0

    stray = target.landing_root / "stray.txt"
    stray.write_text("keep")
    exit_code, _, stderr = _run(["restore", str(backup_dir)], target)
    assert exit_code == 1
    assert "not empty" in stderr
    assert "--force" in stderr

    exit_code, stdout, stderr = _run(["restore", str(backup_dir), "--force"], target)
    assert exit_code == 0, stderr
    assert json.loads(stdout)["restore"]["forced"] is True
    assert _sqlite_rows(target.resolved_config_database_path) == _sqlite_rows(
        source.resolved_config_database_path
    )


def test_backup_refuses_non_empty_destination(tmp_path: Path) -> None:
    source = _settings(tmp_path / "source")
    destination = tmp_path / "backup"
    destination.mkdir()
    (destination / "existing.txt").write_text("x")
    exit_code, _, stderr = _run(["backup", str(destination)], source)
    assert exit_code == 1
    assert "not empty" in stderr


def test_backup_refuses_while_warehouse_is_held_open(tmp_path: Path) -> None:
    source = _settings(tmp_path / "source")
    warehouse = source.resolved_analytics_database_path
    warehouse.parent.mkdir(parents=True)
    writer = duckdb.connect(str(warehouse))
    try:
        writer.execute("CREATE TABLE t (x INTEGER)")
        exit_code, _, stderr = _run(["backup", str(tmp_path / "backup")], source)
    finally:
        writer.close()
    assert exit_code == 1
    assert "Stop worker and API processes" in stderr


def test_backup_writes_no_secrets_and_excludes_postgres_stores(tmp_path: Path) -> None:
    secrets = [
        "pg-super-secret-password",
        "s3-secret-access-key-value",
        "ha-long-lived-token",
    ]
    settings = replace(
        _settings(tmp_path / "source"),
        control_plane_backend="postgres",
        control_plane_dsn=f"postgresql://app:{secrets[0]}@db:5432/app",
        reporting_backend="postgres",
        blob_backend="s3",
        s3_bucket="landing",
        s3_access_key_id="AKIAEXAMPLE",
        s3_secret_access_key=secrets[1],
        ha_token=secrets[2],
    )
    backup_dir = tmp_path / "backup"
    exit_code, stdout, stderr = _run(["backup", str(backup_dir)], settings)
    assert exit_code == 0, stderr
    components = {c["name"]: c for c in json.loads(stdout)["components"]}
    assert components["control_plane_postgres"]["included"] is False
    assert components["reporting_postgres"]["included"] is False
    assert components["landing_s3"]["included"] is False

    for path in backup_dir.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            for secret in [*secrets, "AKIAEXAMPLE", "db:5432"]:
                assert secret.encode() not in content, f"{secret!r} leaked into {path}"
