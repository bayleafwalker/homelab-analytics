"""Internal platform ingestion connectors for Prometheus and Home Assistant."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx

from packages.pipelines.csv_validation import (
    ColumnContract,
    ColumnType,
    DatasetContract,
)
from packages.pipelines.run_context import RunControlContext
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.landing_service import LandingRunResult, LandingService
from packages.storage.run_metadata import RunMetadataStore

PROMETHEUS_QUERY_CONTRACT = DatasetContract(
    dataset_name="prometheus_query_results",
    columns=(
        ColumnContract("timestamp", ColumnType.DATETIME),
        ColumnContract("metric_name", ColumnType.STRING),
        ColumnContract("value", ColumnType.DECIMAL),
        ColumnContract("labels_json", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

HOME_ASSISTANT_STATE_CONTRACT = DatasetContract(
    dataset_name="home_assistant_states",
    columns=(
        ColumnContract("entity_id", ColumnType.STRING),
        ColumnContract("domain", ColumnType.STRING),
        ColumnContract("state", ColumnType.STRING),
        ColumnContract("last_changed", ColumnType.DATETIME),
        ColumnContract("attributes_json", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

KUBERNETES_RESOURCE_USAGE_CONTRACT = DatasetContract(
    dataset_name="kubernetes_resource_usage",
    columns=(
        ColumnContract("timestamp", ColumnType.DATETIME),
        ColumnContract("node", ColumnType.STRING),
        ColumnContract("metric_name", ColumnType.STRING),
        ColumnContract("value", ColumnType.DECIMAL),
        ColumnContract("unit", ColumnType.STRING),
        ColumnContract("namespace", ColumnType.STRING, required=False),
        ColumnContract("pod", ColumnType.STRING, required=False),
        ColumnContract("container", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)


@dataclass(frozen=True)
class InternalPlatformIngestionResult:
    run: LandingRunResult
    rows: int


class InternalPlatformIngestionService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        blob_store: BlobStore | None = None,
        client_factory: Callable[..., Any] = httpx.Client,
    ) -> None:
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.metadata_repository = metadata_repository
        self.landing_service = LandingService(
            blob_store=self.blob_store,
            metadata_repository=self.metadata_repository,
        )
        self._client_factory = client_factory

    def ingest_prometheus_query(
        self,
        *,
        base_url: str,
        query: str,
        source_name: str = "prometheus-query",
        run_context: RunControlContext | None = None,
        headers: dict[str, str] | None = None,
    ) -> InternalPlatformIngestionResult:
        raw_bytes, payload = self._fetch_json(
            f"{base_url.rstrip('/')}/api/v1/query",
            params={"query": query},
            headers=headers,
        )
        rows = _prometheus_rows_from_payload(payload)
        csv_bytes = _rows_to_csv_bytes(
            rows,
            fieldnames=("timestamp", "metric_name", "value", "labels_json"),
        )
        landing_result = self.landing_service.ingest_raw_bytes(
            source_bytes=raw_bytes,
            file_name="prometheus-query.json",
            source_name=source_name,
            contract=PROMETHEUS_QUERY_CONTRACT,
            validation_source_bytes=csv_bytes,
            canonical_source_bytes=csv_bytes,
            run_context=run_context,
        )
        return InternalPlatformIngestionResult(run=landing_result, rows=len(rows))

    def ingest_home_assistant_states(
        self,
        *,
        base_url: str,
        token: str,
        source_name: str = "home-assistant-states",
        run_context: RunControlContext | None = None,
    ) -> InternalPlatformIngestionResult:
        raw_bytes, payload = self._fetch_json(
            f"{base_url.rstrip('/')}/api/states",
            headers={"Authorization": f"Bearer {token}"},
        )
        rows = _home_assistant_rows_from_payload(payload)
        csv_bytes = _rows_to_csv_bytes(
            rows,
            fieldnames=("entity_id", "domain", "state", "last_changed", "attributes_json"),
        )
        landing_result = self.landing_service.ingest_raw_bytes(
            source_bytes=raw_bytes,
            file_name="home-assistant-states.json",
            source_name=source_name,
            contract=HOME_ASSISTANT_STATE_CONTRACT,
            validation_source_bytes=csv_bytes,
            canonical_source_bytes=csv_bytes,
            run_context=run_context,
        )
        return InternalPlatformIngestionResult(run=landing_result, rows=len(rows))

    def ingest_kubernetes_resource_usage(
        self,
        *,
        base_url: str,
        path: str = "/api/v1/resource-usage",
        source_name: str = "kubernetes-resource-usage",
        run_context: RunControlContext | None = None,
        headers: dict[str, str] | None = None,
    ) -> InternalPlatformIngestionResult:
        raw_bytes, payload = self._fetch_json(
            f"{base_url.rstrip('/')}{path}",
            headers=headers,
        )
        rows = _kubernetes_rows_from_payload(payload)
        csv_bytes = _rows_to_csv_bytes(
            rows,
            fieldnames=(
                "timestamp",
                "node",
                "metric_name",
                "value",
                "unit",
                "namespace",
                "pod",
                "container",
            ),
        )
        landing_result = self.landing_service.ingest_raw_bytes(
            source_bytes=raw_bytes,
            file_name="kubernetes-resource-usage.json",
            source_name=source_name,
            contract=KUBERNETES_RESOURCE_USAGE_CONTRACT,
            validation_source_bytes=csv_bytes,
            canonical_source_bytes=csv_bytes,
            run_context=run_context,
        )
        return InternalPlatformIngestionResult(run=landing_result, rows=len(rows))

    def _fetch_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> tuple[bytes, Any]:
        with self._client_factory(timeout=30) as client:
            response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.content, response.json()


def _prometheus_rows_from_payload(payload: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(payload, dict):
        raise ValueError("Prometheus query response must be a JSON object.")
    data = payload.get("data") or {}
    result_type = str(data.get("resultType") or "").strip()
    results = data.get("result") or []
    if result_type not in {"vector", "matrix"}:
        raise ValueError(f"Unsupported Prometheus resultType: {result_type!r}")

    rows: list[dict[str, str]] = []
    for item in results:
        metric = item.get("metric") or {}
        metric_name = str(metric.get("__name__") or metric.get("metric") or "").strip()
        labels = {key: value for key, value in metric.items() if key != "__name__"}
        if result_type == "vector":
            sample = item.get("value") or []
            if len(sample) != 2:
                continue
            rows.append(
                {
                    "timestamp": _prometheus_timestamp(sample[0]),
                    "metric_name": metric_name,
                    "value": str(sample[1]),
                    "labels_json": json.dumps(labels, sort_keys=True),
                }
            )
            continue

        for sample in item.get("values") or []:
            if len(sample) != 2:
                continue
            rows.append(
                {
                    "timestamp": _prometheus_timestamp(sample[0]),
                    "metric_name": metric_name,
                    "value": str(sample[1]),
                    "labels_json": json.dumps(labels, sort_keys=True),
                }
            )
    return rows


def _home_assistant_rows_from_payload(payload: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise ValueError("Home Assistant states response must be a JSON array.")
    rows: list[dict[str, str]] = []
    for state in payload:
        entity_id = str(state.get("entity_id") or "").strip()
        if not entity_id:
            continue
        domain = entity_id.split(".", 1)[0]
        attributes = state.get("attributes") or {}
        if not isinstance(attributes, dict):
            attributes = {}
        changed_at = str(
            state.get("last_changed")
            or state.get("last_updated")
            or ""
        ).strip()
        rows.append(
            {
                "entity_id": entity_id,
                "domain": domain,
                "state": str(state.get("state") or ""),
                "last_changed": changed_at,
                "attributes_json": json.dumps(attributes, sort_keys=True),
            }
        )
    return rows


def _kubernetes_rows_from_payload(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, dict):
        rows = payload.get("items") or payload.get("rows") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("Kubernetes resource usage response must be a JSON array.")

    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = str(row.get("timestamp") or row.get("recorded_at") or "").strip()
        node = str(row.get("node") or row.get("node_name") or "").strip()
        metric_name = str(row.get("metric_name") or row.get("metric") or "").strip()
        value = str(row.get("value") or row.get("usage") or "").strip()
        unit = str(row.get("unit") or row.get("resource_unit") or "").strip()
        if not timestamp or not node or not metric_name or not value or not unit:
            continue
        normalized_rows.append(
            {
                "timestamp": timestamp,
                "node": node,
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
                "namespace": str(row.get("namespace") or "").strip(),
                "pod": str(row.get("pod") or row.get("pod_name") or "").strip(),
                "container": str(row.get("container") or row.get("container_name") or "").strip(),
            }
        )
    return normalized_rows


def _prometheus_timestamp(raw_timestamp: Any) -> str:
    return datetime.fromtimestamp(float(raw_timestamp), tz=UTC).isoformat()


def _rows_to_csv_bytes(
    rows: list[dict[str, str]],
    *,
    fieldnames: tuple[str, ...],
) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue().encode("utf-8")


__all__ = [
    "HOME_ASSISTANT_STATE_CONTRACT",
    "InternalPlatformIngestionResult",
    "InternalPlatformIngestionService",
    "KUBERNETES_RESOURCE_USAGE_CONTRACT",
    "PROMETHEUS_QUERY_CONTRACT",
]
