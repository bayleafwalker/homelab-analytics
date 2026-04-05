from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
import pytest

POSTGRES_IMAGE = "postgres:16-alpine"


def docker_is_available() -> bool:
    if shutil.which("docker") is None:
        return False
    completed = subprocess.run(
        ["docker", "info"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def _container_host_port(container_name: str, container_port: str) -> int:
    completed = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{(index (index .NetworkSettings.Ports \"" + container_port + "\") 0).HostPort}}",
            container_name,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(completed.stdout.strip())


def _wait_for_postgres(dsn: str, *, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with psycopg.connect(dsn):
                return
        except psycopg.Error:
            time.sleep(0.5)
    raise TimeoutError("Timed out waiting for postgres test container.")


@contextmanager
def running_postgres_container() -> Iterator[str]:
    if not docker_is_available():
        pytest.skip("Docker is required for Postgres adapter integration tests.")

    container_name = f"homelab-analytics-postgres-{uuid.uuid4().hex[:8]}"
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            container_name,
            "--env",
            "POSTGRES_DB=homelab",
            "--env",
            "POSTGRES_USER=homelab",
            "--env",
            "POSTGRES_PASSWORD=homelab",
            "--publish",
            "127.0.0.1::5432",
            POSTGRES_IMAGE,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        host_port = _container_host_port(container_name, "5432/tcp")
        dsn = f"postgresql://homelab:homelab@127.0.0.1:{host_port}/homelab"
        _wait_for_postgres(dsn)
        yield dsn
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            check=False,
            capture_output=True,
            text=True,
        )
