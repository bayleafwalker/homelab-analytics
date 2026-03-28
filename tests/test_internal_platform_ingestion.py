from __future__ import annotations

import csv
import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.pipelines.internal_platform_ingestion import (
    HOME_ASSISTANT_STATE_CONTRACT,
    KUBERNETES_RESOURCE_USAGE_CONTRACT,
    PROMETHEUS_QUERY_CONTRACT,
    InternalPlatformIngestionService,
)
from packages.storage.blob import FilesystemBlobStore
from packages.storage.run_metadata import RunMetadataRepository


class _FakeResponse:
    def __init__(self, *, content: bytes, payload: object) -> None:
        self.content = content
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> object:
        return self._payload


def _client_factory(
    response_map: dict[str, tuple[bytes, object]],
    calls: list[tuple[str, dict | None, dict | None]],
):
    class _FakeClient:
        def __init__(self, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self) -> "_FakeClient":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def get(
            self,
            url: str,
            *,
            headers: dict | None = None,
            params: dict | None = None,
        ) -> _FakeResponse:
            calls.append((url, headers, params))
            content, payload = response_map[url]
            return _FakeResponse(content=content, payload=payload)

    return _FakeClient


class InternalPlatformIngestionTests(unittest.TestCase):
    def test_prometheus_query_lands_raw_json_and_canonical_csv(self) -> None:
        response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {
                            "__name__": "node_load1",
                            "instance": "homeserver",
                            "job": "node",
                        },
                        "value": [1711725600.0, "0.42"],
                    }
                ],
            },
        }
        raw_response = json.dumps(response, separators=(",", ":"), sort_keys=True).encode("utf-8")
        calls: list[tuple[str, dict | None, dict | None]] = []
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            service = InternalPlatformIngestionService(
                temp_root / "landing",
                RunMetadataRepository(temp_root / "runs.db"),
                blob_store=FilesystemBlobStore(temp_root / "landing"),
                client_factory=_client_factory(
                    {"http://prometheus.local/api/v1/query": (raw_response, response)},
                    calls,
                ),
            )

            result = service.ingest_prometheus_query(
                base_url="http://prometheus.local",
                query="node_load1",
                source_name="prometheus-query",
            )

            self.assertEqual(1, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual("prometheus_query_results", PROMETHEUS_QUERY_CONTRACT.dataset_name)
            self.assertFalse(PROMETHEUS_QUERY_CONTRACT.allow_extra_columns)
            self.assertEqual(
                raw_response,
                Path(result.run.raw_path).read_bytes(),
            )
            self.assertEqual(
                [
                    {
                        "timestamp": datetime.fromtimestamp(1711725600.0, tz=UTC).isoformat(),
                        "metric_name": "node_load1",
                        "value": "0.42",
                        "labels_json": '{"instance": "homeserver", "job": "node"}',
                    }
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )
            self.assertEqual(
                [
                    (
                        "http://prometheus.local/api/v1/query",
                        None,
                        {"query": "node_load1"},
                    )
                ],
                calls,
            )

    def test_home_assistant_states_lands_raw_json_and_canonical_csv(self) -> None:
        response = [
            {
                "entity_id": "sensor.living_room_temp",
                "state": "21.3",
                "attributes": {"unit_of_measurement": "°C", "friendly_name": "LR Temp"},
                "last_changed": "2026-03-21T10:00:00+00:00",
            },
            {
                "entity_id": "light.kitchen",
                "state": "on",
                "attributes": {"friendly_name": "Kitchen Light"},
                "last_changed": "2026-03-21T10:05:00+00:00",
            },
        ]
        raw_response = json.dumps(response, separators=(",", ":"), sort_keys=True).encode("utf-8")
        calls: list[tuple[str, dict | None, dict | None]] = []
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            service = InternalPlatformIngestionService(
                temp_root / "landing",
                RunMetadataRepository(temp_root / "runs.db"),
                blob_store=FilesystemBlobStore(temp_root / "landing"),
                client_factory=_client_factory(
                    {"http://homeassistant.local/api/states": (raw_response, response)},
                    calls,
                ),
            )

            result = service.ingest_home_assistant_states(
                base_url="http://homeassistant.local",
                token="secret-token",
                source_name="home-assistant-states",
            )

            self.assertEqual(2, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual(
                HOME_ASSISTANT_STATE_CONTRACT.dataset_name,
                "home_assistant_states",
            )
            self.assertFalse(HOME_ASSISTANT_STATE_CONTRACT.allow_extra_columns)
            self.assertEqual(
                raw_response,
                Path(result.run.raw_path).read_bytes(),
            )
            self.assertEqual(
                [
                    {
                        "entity_id": "sensor.living_room_temp",
                        "domain": "sensor",
                        "state": "21.3",
                        "last_changed": "2026-03-21T10:00:00+00:00",
                        "attributes_json": '{"friendly_name": "LR Temp", "unit_of_measurement": "\\u00b0C"}',
                    },
                    {
                        "entity_id": "light.kitchen",
                        "domain": "light",
                        "state": "on",
                        "last_changed": "2026-03-21T10:05:00+00:00",
                        "attributes_json": '{"friendly_name": "Kitchen Light"}',
                    },
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )
            self.assertEqual(
                [
                    (
                        "http://homeassistant.local/api/states",
                        {"Authorization": "Bearer secret-token"},
                        None,
                    )
                ],
                calls,
            )

    def test_kubernetes_resource_usage_lands_raw_json_and_canonical_csv(self) -> None:
        response = [
            {
                "timestamp": "2026-03-21T10:00:00+00:00",
                "node": "homeserver",
                "metric_name": "node_cpu_usage",
                "value": "0.62",
                "unit": "cores",
                "namespace": "kube-system",
                "pod": "metrics-server-abc123",
                "container": "metrics-server",
            },
            {
                "timestamp": "2026-03-21T10:00:00+00:00",
                "node": "homeserver",
                "metric_name": "node_memory_usage",
                "value": "536870912",
                "unit": "bytes",
            },
        ]
        raw_response = json.dumps(response, separators=(",", ":"), sort_keys=True).encode("utf-8")
        calls: list[tuple[str, dict | None, dict | None]] = []
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            service = InternalPlatformIngestionService(
                temp_root / "landing",
                RunMetadataRepository(temp_root / "runs.db"),
                blob_store=FilesystemBlobStore(temp_root / "landing"),
                client_factory=_client_factory(
                    {"http://kubernetes.local/api/v1/resource-usage": (raw_response, response)},
                    calls,
                ),
            )

            result = service.ingest_kubernetes_resource_usage(
                base_url="http://kubernetes.local",
                source_name="kubernetes-resource-usage",
            )

            self.assertEqual(2, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual(
                KUBERNETES_RESOURCE_USAGE_CONTRACT.dataset_name,
                "kubernetes_resource_usage",
            )
            self.assertFalse(KUBERNETES_RESOURCE_USAGE_CONTRACT.allow_extra_columns)
            self.assertEqual(
                raw_response,
                Path(result.run.raw_path).read_bytes(),
            )
            self.assertEqual(
                [
                    {
                        "timestamp": "2026-03-21T10:00:00+00:00",
                        "node": "homeserver",
                        "metric_name": "node_cpu_usage",
                        "value": "0.62",
                        "unit": "cores",
                        "namespace": "kube-system",
                        "pod": "metrics-server-abc123",
                        "container": "metrics-server",
                    },
                    {
                        "timestamp": "2026-03-21T10:00:00+00:00",
                        "node": "homeserver",
                        "metric_name": "node_memory_usage",
                        "value": "536870912",
                        "unit": "bytes",
                        "namespace": "",
                        "pod": "",
                        "container": "",
                    },
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )
            self.assertEqual(
                [
                    (
                        "http://kubernetes.local/api/v1/resource-usage",
                        None,
                        None,
                    )
                ],
                calls,
            )
def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
