from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

MINIO_IMAGE = "minio/minio:RELEASE.2025-09-07T16-13-09Z-cpuv1"


@dataclass(frozen=True)
class MinioConnectionInfo:
    endpoint_url: str
    access_key_id: str
    secret_access_key: str
    region_name: str
    bucket: str


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


def _wait_for_minio(connection_info: MinioConnectionInfo, *, timeout_seconds: float = 30.0) -> None:
    client = boto3.client(
        "s3",
        endpoint_url=connection_info.endpoint_url,
        region_name=connection_info.region_name,
        aws_access_key_id=connection_info.access_key_id,
        aws_secret_access_key=connection_info.secret_access_key,
        config=Config(s3={"addressing_style": "path"}),
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            client.list_buckets()
            return
        except (BotoCoreError, ClientError):
            time.sleep(0.5)
    raise TimeoutError("Timed out waiting for MinIO test container.")


@contextmanager
def running_minio_container() -> Iterator[MinioConnectionInfo]:
    if not docker_is_available():
        pytest.skip("Docker is required for MinIO adapter integration tests.")

    container_name = f"homelab-analytics-minio-{uuid.uuid4().hex[:8]}"
    access_key_id = "minioadmin"
    secret_access_key = "minioadmin"
    region_name = "us-east-1"
    bucket = "landing"
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--name",
            container_name,
            "--env",
            f"MINIO_ROOT_USER={access_key_id}",
            "--env",
            f"MINIO_ROOT_PASSWORD={secret_access_key}",
            "--publish",
            "127.0.0.1::9000",
            MINIO_IMAGE,
            "server",
            "/data",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    try:
        host_port = _container_host_port(container_name, "9000/tcp")
        connection_info = MinioConnectionInfo(
            endpoint_url=f"http://127.0.0.1:{host_port}",
            access_key_id=access_key_id,
            secret_access_key=secret_access_key,
            region_name=region_name,
            bucket=bucket,
        )
        _wait_for_minio(connection_info)
        yield connection_info
    finally:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            check=False,
            capture_output=True,
            text=True,
        )
