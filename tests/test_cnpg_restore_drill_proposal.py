"""The proposed CNPG restore drill CronJob (docs/notes/appservice-proposals/).

Static checks always run. The slow test runs the ConfigMap's restore.sh and
app_check.py against a real local Postgres 16 (needs initdb, pg_ctl, pg_dump,
pg_restore, psql and pg_isready on PATH), with rclone and age stubbed by a
local "bucket" directory: seed a live instance, dump it, restore it like the
drill, and require a passing receipt.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "notes" / "appservice-proposals" / "cronjob-cnpg-restore-drill.yaml"
FIXTURE = ROOT / "tests" / "fixtures" / "account_transactions_valid.csv"


def _documents() -> tuple[dict, dict]:
    configmap, cronjob = [doc for doc in yaml.safe_load_all(MANIFEST.read_text()) if doc]
    return configmap, cronjob


def _pod_spec(cronjob: dict) -> dict:
    return cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]


def test_scripts_are_isolated_from_flux_substitution() -> None:
    configmap, cronjob = _documents()

    assert configmap["metadata"]["annotations"]["kustomize.toolkit.fluxcd.io/substitute"] == "disabled"
    # The CronJob is substituted (for the Hetzner endpoint); nothing else may
    # use the dollar-brace form there.
    rendered = yaml.safe_dump(cronjob)
    assert rendered.count("${") == rendered.count("${HETZNER_S3_BUCKET_ENDPOINT}") == 1
    assert set(configmap["data"]) == {"postgres.sh", "restore.sh", "app_check.py"}


def test_pod_meets_restricted_pod_security() -> None:
    _, cronjob = _documents()
    spec = _pod_spec(cronjob)

    assert cronjob["metadata"]["namespace"] == "cnpg-dump-drill"
    assert spec["securityContext"]["runAsNonRoot"] is True
    assert spec["securityContext"]["seccompProfile"]["type"] == "RuntimeDefault"
    assert spec["automountServiceAccountToken"] is False
    for container in spec["initContainers"] + spec["containers"]:
        context = container["securityContext"]
        assert context["allowPrivilegeEscalation"] is False, container["name"]
        assert context["capabilities"]["drop"] == ["ALL"], container["name"]
        assert context["runAsUser"] != 0, container["name"]
        image = container["image"]
        assert "@sha256:" in image, container["name"]


def test_postgres_is_a_native_sidecar_and_app_check_is_main() -> None:
    _, cronjob = _documents()
    spec = _pod_spec(cronjob)
    init = {container["name"]: container for container in spec["initContainers"]}

    assert list(init) == ["fetch-age", "copy-rclone", "postgres", "restore"]
    assert init["postgres"]["restartPolicy"] == "Always"
    assert "startupProbe" in init["postgres"]
    assert [container["name"] for container in spec["containers"]] == ["app-check"]
    assert "REPLACE_WITH_RELEASE_DIGEST" in spec["containers"][0]["image"]
    identity = next(volume for volume in spec["volumes"] if volume["name"] == "identity")
    assert identity["secret"]["secretName"] == "drill-identity"


def test_scripts_parse() -> None:
    configmap, _ = _documents()
    if shutil.which("bash") is None:
        pytest.skip("bash is not installed")
    for name in ("postgres.sh", "restore.sh"):
        result = subprocess.run(["bash", "-n"], input=configmap["data"][name], text=True, capture_output=True)
        assert result.returncode == 0, (name, result.stderr)
    compile(configmap["data"]["app_check.py"], "app_check.py", "exec")


# ---------------------------------------------------------------------------
# End to end against a local Postgres
# ---------------------------------------------------------------------------

PG_TOOLS = ("initdb", "pg_ctl", "pg_dump", "pg_restore", "psql", "pg_isready")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%SZ")


RCLONE_STUB = """#!/usr/bin/env bash
cmd="$1"; shift
include=""; args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --include) include="$2"; shift 2 ;;
    --*) shift ;;
    *) args+=("$1"); shift ;;
  esac
done
path="$STUB_BUCKET/${args[0]#hetzner:}"
case "$cmd" in
  lsf) cd "$path" && for f in $include; do [ -f "$f" ] && echo "$f"; done ;;
  cat) cat "$path" ;;
esac
"""


@pytest.mark.slow
@pytest.mark.skipif(
    any(shutil.which(tool) is None for tool in (*PG_TOOLS, "bash", "tar")),
    reason="needs a local Postgres 16 toolchain, bash and tar",
)
def test_drill_scripts_restore_and_check_a_real_dump(tmp_path: Path) -> None:
    configmap, _ = _documents()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name, body in configmap["data"].items():
        (scripts / name).write_text(body)
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    (stubs / "rclone").write_text(RCLONE_STUB)
    (stubs / "age").write_text("#!/bin/sh\nexec cat\n")
    for stub in stubs.iterdir():
        stub.chmod(0o755)

    port = _free_port()
    bin_dir = Path(sys.executable).parent
    base_env = {
        **os.environ,
        "PATH": f"{stubs}{os.pathsep}{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "PGHOST": "127.0.0.1",
        "PGPORT": str(port),
        "PGUSER": "postgres",
    }
    pgdata = tmp_path / "pgdata"
    subprocess.run(
        ["initdb", "-D", str(pgdata), "-U", "postgres", "--auth=trust", "-E", "UTF8"],
        check=True, capture_output=True, env=base_env,
    )
    subprocess.run(
        [
            "pg_ctl", "-D", str(pgdata), "-w", "-l", str(tmp_path / "pg.log"), "-o",
            f"-c listen_addresses=127.0.0.1 -c port={port} -c unix_socket_directories={tmp_path} -c fsync=off",
            "start",
        ],
        check=True, capture_output=True, env=base_env,
    )
    try:
        subprocess.run(
            ["psql", "-qAtX", "-d", "postgres", "-c", "CREATE ROLE homelab_analytics LOGIN",
             "-c", "CREATE DATABASE live OWNER homelab_analytics"],
            check=True, capture_output=True, env=base_env,
        )
        app_env = {
            **base_env,
            "HOMELAB_ANALYTICS_CONTROL_PLANE_BACKEND": "postgres",
            "HOMELAB_ANALYTICS_REPORTING_BACKEND": "postgres",
            "HOMELAB_ANALYTICS_BLOB_BACKEND": "filesystem",
            "HOMELAB_ANALYTICS_IDENTITY_MODE": "disabled",
        }
        live_dsn = f"postgresql://homelab_analytics@127.0.0.1:{port}/live"
        live_env = {
            **app_env,
            "HOMELAB_ANALYTICS_DATA_DIR": str(tmp_path / "live"),
            "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN": live_dsn,
            "HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN": live_dsn,
        }
        for command in (["ingest-account-transactions", str(FIXTURE)], ["scheduled-backup"]):
            subprocess.run(
                [str(bin_dir / "homelab-analytics-worker"), *command],
                check=True, capture_output=True, env=live_env, cwd=ROOT,
            )

        bucket = tmp_path / "bucket" / "appservice-pgdump-locked" / "backups"
        dumps = bucket / "pgdump-age" / "analytics" / "analytics-postgres"
        bundles = bucket / "app-bundles" / "analytics" / "homelab-analytics"
        dumps.mkdir(parents=True)
        bundles.mkdir(parents=True)
        now = datetime.now(UTC)
        stamp, old = _stamp(now), _stamp(now - timedelta(hours=30))
        for moment in (stamp, old):
            with (dumps / f"analytics-postgres-homelab_analytics-{moment}.dump.age").open("wb") as handle:
                subprocess.run(["pg_dump", "--format=custom", "-d", "live"], check=True, stdout=handle, env=base_env)
        # Another database whose name extends the series must not be picked.
        (dumps / f"analytics-postgres-homelab_analytics_x-{stamp}.dump.age").write_text("junk")
        bundle = sorted(p for p in (tmp_path / "live" / "backups").glob("backup-*") if p.is_dir())[-1]
        with (bundles / f"backup-{stamp}.tar.age").open("wb") as handle:
            subprocess.run(["tar", "-C", str(bundle), "-cf", "-", "."], check=True, stdout=handle)
        (bundles / f"backup-{old}.tar.age").write_text("junk")

        work = tmp_path / "work"
        restore = subprocess.run(
            ["bash", str(scripts / "restore.sh")],
            capture_output=True, text=True,
            env={
                **base_env,
                "STUB_BUCKET": str(tmp_path / "bucket"),
                "BUCKET": "appservice-pgdump-locked",
                "DATABASE": "homelab_analytics",
                "MAX_DUMP_AGE_HOURS": "3",
                "MAX_BUNDLE_AGE_HOURS": "26",
                "WORK": str(work),
                "IDENTITY_FILE": "/dev/null",
            },
        )
        assert restore.returncode == 0, restore.stdout + restore.stderr
        restored = json.loads((work / "drill" / "restore.json").read_text())
        assert restored["dump_object"] == f"analytics-postgres-homelab_analytics-{stamp}.dump.age"
        assert restored["bundle"] == f"backup-{stamp}"

        scratch_dsn = f"postgresql://postgres@127.0.0.1:{port}/homelab_analytics"
        check = subprocess.run(
            [sys.executable, str(scripts / "app_check.py")],
            capture_output=True, text=True, cwd=tmp_path, timeout=600,
            env={
                **app_env,
                "DRILL_WORK_DIR": str(work),
                "HOMELAB_ANALYTICS_DATA_DIR": str(work / "data"),
                "HOMELAB_ANALYTICS_CONTROL_PLANE_DSN": scratch_dsn,
                "HOMELAB_ANALYTICS_REPORTING_POSTGRES_DSN": scratch_dsn,
                "HOMELAB_ANALYTICS_ENABLE_BOOTSTRAP_LOCAL_ADMIN": "false",
                "HOMELAB_ANALYTICS_API_HOST": "127.0.0.1",
                "HOMELAB_ANALYTICS_API_PORT": str(_free_port()),
            },
        )
        receipt = json.loads(check.stdout.strip().splitlines()[-1])["cnpg_restore_drill"]
        assert check.returncode == 0 and receipt["passed"], receipt
        assert receipt["runs"] >= 1
        assert receipt["warehouse_drill"]["passed"] is True
    finally:
        subprocess.run(["pg_ctl", "-D", str(pgdata), "-m", "fast", "stop"], capture_output=True, env=base_env)
