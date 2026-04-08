"""Landing-first ingestion contracts for Home Assistant bridge payloads."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.pipelines.csv_validation import ColumnContract, ColumnType, DatasetContract
from packages.pipelines.run_context import RunControlContext
from packages.storage.blob import BlobStore, FilesystemBlobStore
from packages.storage.landing_service import LandingRunResult, LandingService
from packages.storage.run_metadata import RunMetadataStore

HA_BRIDGE_SCHEMA_VERSION = "1.0"

HA_BRIDGE_REGISTRY_CONTRACT = DatasetContract(
    dataset_name="ha_bridge_registry_snapshot",
    columns=(
        ColumnContract("captured_at", ColumnType.DATETIME),
        ColumnContract("bridge_instance_id", ColumnType.STRING),
        ColumnContract("schema_version", ColumnType.STRING),
        ColumnContract("record_type", ColumnType.STRING),
        ColumnContract("entity_id", ColumnType.STRING, required=False),
        ColumnContract("entity_registry_id", ColumnType.STRING, required=False),
        ColumnContract("unique_id", ColumnType.STRING, required=False),
        ColumnContract("device_id", ColumnType.STRING, required=False),
        ColumnContract("area_id", ColumnType.STRING, required=False),
        ColumnContract("canonical_entity_id", ColumnType.STRING, required=False),
        ColumnContract("canonical_device_id", ColumnType.STRING, required=False),
        ColumnContract("canonical_area_id", ColumnType.STRING, required=False),
        ColumnContract("floor_id", ColumnType.STRING, required=False),
        ColumnContract("name", ColumnType.STRING, required=False),
        ColumnContract("domain", ColumnType.STRING, required=False),
        ColumnContract("platform", ColumnType.STRING, required=False),
        ColumnContract("device_class", ColumnType.STRING, required=False),
        ColumnContract("unit_of_measurement", ColumnType.STRING, required=False),
        ColumnContract("state_class", ColumnType.STRING, required=False),
        ColumnContract("disabled_by", ColumnType.STRING, required=False),
        ColumnContract("labels_json", ColumnType.STRING, required=False),
        ColumnContract("manufacturer", ColumnType.STRING, required=False),
        ColumnContract("model", ColumnType.STRING, required=False),
        ColumnContract("integration", ColumnType.STRING, required=False),
        ColumnContract("entry_type", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

HA_BRIDGE_STATES_CONTRACT = DatasetContract(
    dataset_name="ha_bridge_states",
    columns=(
        ColumnContract("captured_at", ColumnType.DATETIME),
        ColumnContract("bridge_instance_id", ColumnType.STRING),
        ColumnContract("schema_version", ColumnType.STRING),
        ColumnContract("batch_source", ColumnType.STRING),
        ColumnContract("entity_id", ColumnType.STRING),
        ColumnContract("entity_registry_id", ColumnType.STRING),
        ColumnContract("canonical_entity_id", ColumnType.STRING),
        ColumnContract("state", ColumnType.STRING),
        ColumnContract("last_changed", ColumnType.DATETIME, required=False),
        ColumnContract("last_updated", ColumnType.DATETIME, required=False),
        ColumnContract("attributes_json", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

HA_BRIDGE_EVENTS_CONTRACT = DatasetContract(
    dataset_name="ha_bridge_events",
    columns=(
        ColumnContract("captured_at", ColumnType.DATETIME),
        ColumnContract("bridge_instance_id", ColumnType.STRING),
        ColumnContract("schema_version", ColumnType.STRING),
        ColumnContract("event_type", ColumnType.STRING),
        ColumnContract("event_fired_at", ColumnType.DATETIME),
        ColumnContract("entity_id", ColumnType.STRING),
        ColumnContract("entity_registry_id", ColumnType.STRING),
        ColumnContract("canonical_entity_id", ColumnType.STRING),
        ColumnContract("state", ColumnType.STRING),
        ColumnContract("old_state", ColumnType.STRING, required=False),
        ColumnContract("last_changed", ColumnType.DATETIME, required=False),
        ColumnContract("last_updated", ColumnType.DATETIME, required=False),
        ColumnContract("attributes_json", ColumnType.STRING, required=False),
    ),
    allow_extra_columns=False,
)

HA_BRIDGE_STATISTICS_CONTRACT = DatasetContract(
    dataset_name="ha_bridge_statistics",
    columns=(
        ColumnContract("captured_at", ColumnType.DATETIME),
        ColumnContract("bridge_instance_id", ColumnType.STRING),
        ColumnContract("schema_version", ColumnType.STRING),
        ColumnContract("entity_id", ColumnType.STRING, required=False),
        ColumnContract("entity_registry_id", ColumnType.STRING),
        ColumnContract("canonical_entity_id", ColumnType.STRING),
        ColumnContract("statistic_id", ColumnType.STRING),
        ColumnContract("unit", ColumnType.STRING),
        ColumnContract("bucket_start", ColumnType.DATETIME),
        ColumnContract("bucket_end", ColumnType.DATETIME, required=False),
        ColumnContract("mean", ColumnType.DECIMAL, required=False),
        ColumnContract("minimum", ColumnType.DECIMAL, required=False),
        ColumnContract("maximum", ColumnType.DECIMAL, required=False),
        ColumnContract("sum", ColumnType.DECIMAL, required=False),
    ),
    allow_extra_columns=False,
)

HA_BRIDGE_HEARTBEAT_CONTRACT = DatasetContract(
    dataset_name="ha_bridge_heartbeat",
    columns=(
        ColumnContract("observed_at", ColumnType.DATETIME),
        ColumnContract("bridge_instance_id", ColumnType.STRING),
        ColumnContract("schema_version", ColumnType.STRING),
        ColumnContract("bridge_version", ColumnType.STRING, required=False),
        ColumnContract("ha_version", ColumnType.STRING, required=False),
        ColumnContract("connected", ColumnType.BOOLEAN),
        ColumnContract("buffering", ColumnType.BOOLEAN),
        ColumnContract("entity_count", ColumnType.INTEGER),
        ColumnContract("queued_events", ColumnType.INTEGER),
        ColumnContract("oldest_queued_at", ColumnType.DATETIME, required=False),
        ColumnContract("last_delivery_at", ColumnType.DATETIME, required=False),
    ),
    allow_extra_columns=False,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _HaBridgeModel(_StrictModel):
    schema_version: str = HA_BRIDGE_SCHEMA_VERSION
    bridge_instance_id: str

    @field_validator("schema_version")
    @classmethod
    def _validate_schema_version(cls, value: str) -> str:
        normalized = value.strip()
        if normalized != HA_BRIDGE_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported HA bridge schema_version "
                f"{value!r}; expected {HA_BRIDGE_SCHEMA_VERSION!r}."
            )
        return normalized


class HaBridgeEntityRegistryRecord(_StrictModel):
    entity_id: str
    entity_registry_id: str
    unique_id: str | None = None
    device_id: str | None = None
    area_id: str | None = None
    platform: str | None = None
    domain: str | None = None
    device_class: str | None = None
    unit_of_measurement: str | None = None
    state_class: str | None = None
    disabled_by: str | None = None
    labels: list[str] = Field(default_factory=list)


class HaBridgeDeviceRegistryRecord(_StrictModel):
    device_id: str
    name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    area_id: str | None = None
    integration: str | None = None
    entry_type: str | None = None


class HaBridgeAreaRegistryRecord(_StrictModel):
    area_id: str
    name: str
    floor_id: str | None = None


class HaBridgeRegistryPayload(_HaBridgeModel):
    captured_at: datetime
    entities: list[HaBridgeEntityRegistryRecord] = Field(default_factory=list)
    devices: list[HaBridgeDeviceRegistryRecord] = Field(default_factory=list)
    areas: list[HaBridgeAreaRegistryRecord] = Field(default_factory=list)


class HaBridgeStateRecord(_StrictModel):
    entity_id: str
    entity_registry_id: str
    state: str
    last_changed: datetime | None = None
    last_updated: datetime | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class HaBridgeStatesPayload(_HaBridgeModel):
    captured_at: datetime
    batch_source: str = "snapshot"
    states: list[HaBridgeStateRecord] = Field(default_factory=list)


class HaBridgeEventRecord(_StrictModel):
    event_type: str = "state_changed"
    event_fired_at: datetime
    entity_id: str
    entity_registry_id: str
    state: str
    old_state: str | None = None
    last_changed: datetime | None = None
    last_updated: datetime | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class HaBridgeEventsPayload(_HaBridgeModel):
    captured_at: datetime
    events: list[HaBridgeEventRecord] = Field(default_factory=list)


class HaBridgeStatisticRecord(_StrictModel):
    entity_id: str | None = None
    entity_registry_id: str
    statistic_id: str
    unit: str
    bucket_start: datetime
    bucket_end: datetime | None = None
    mean: str | None = None
    minimum: str | None = None
    maximum: str | None = None
    sum: str | None = None


class HaBridgeStatisticsPayload(_HaBridgeModel):
    captured_at: datetime
    statistics: list[HaBridgeStatisticRecord] = Field(default_factory=list)


class HaBridgeHeartbeatPayload(_HaBridgeModel):
    observed_at: datetime
    bridge_version: str | None = None
    ha_version: str | None = None
    connected: bool
    buffering: bool = False
    entity_count: int = 0
    queued_events: int = 0
    oldest_queued_at: datetime | None = None
    last_delivery_at: datetime | None = None


@dataclass(frozen=True)
class HaBridgeLandingIngestionResult:
    run: LandingRunResult
    rows: int


class HaBridgeLandingService:
    def __init__(
        self,
        landing_root: Path,
        metadata_repository: RunMetadataStore,
        blob_store: BlobStore | None = None,
    ) -> None:
        self.blob_store = blob_store or FilesystemBlobStore(landing_root)
        self.metadata_repository = metadata_repository
        self.landing_service = LandingService(
            blob_store=self.blob_store,
            metadata_repository=self.metadata_repository,
        )

    def ingest_registry_payload(
        self,
        *,
        raw_bytes: bytes,
        payload: HaBridgeRegistryPayload,
        source_name: str = "ha-bridge-registry",
        run_context: RunControlContext | None = None,
    ) -> HaBridgeLandingIngestionResult:
        rows: list[dict[str, str]] = []
        captured_at = payload.captured_at.isoformat()
        for entity in payload.entities:
            canonical_entity_id = canonical_ha_entity_id(
                payload.bridge_instance_id,
                entity.entity_registry_id,
            )
            canonical_device_id = _canonical_ha_device_id_or_empty(
                payload.bridge_instance_id,
                entity.device_id,
            )
            canonical_area_id = _canonical_ha_area_id_or_empty(
                payload.bridge_instance_id,
                entity.area_id,
            )
            rows.append(
                {
                    "captured_at": captured_at,
                    "bridge_instance_id": payload.bridge_instance_id,
                    "schema_version": payload.schema_version,
                    "record_type": "entity",
                    "entity_id": entity.entity_id,
                    "entity_registry_id": entity.entity_registry_id,
                    "unique_id": _string_or_empty(entity.unique_id),
                    "device_id": _string_or_empty(entity.device_id),
                    "area_id": _string_or_empty(entity.area_id),
                    "canonical_entity_id": canonical_entity_id,
                    "canonical_device_id": canonical_device_id,
                    "canonical_area_id": canonical_area_id,
                    "floor_id": "",
                    "name": "",
                    "domain": _string_or_empty(entity.domain),
                    "platform": _string_or_empty(entity.platform),
                    "device_class": _string_or_empty(entity.device_class),
                    "unit_of_measurement": _string_or_empty(entity.unit_of_measurement),
                    "state_class": _string_or_empty(entity.state_class),
                    "disabled_by": _string_or_empty(entity.disabled_by),
                    "labels_json": _json_or_empty(entity.labels),
                    "manufacturer": "",
                    "model": "",
                    "integration": "",
                    "entry_type": "",
                }
            )
        for device in payload.devices:
            canonical_device_id = canonical_ha_device_id(
                payload.bridge_instance_id,
                device.device_id,
            )
            canonical_area_id = _canonical_ha_area_id_or_empty(
                payload.bridge_instance_id,
                device.area_id,
            )
            rows.append(
                {
                    "captured_at": captured_at,
                    "bridge_instance_id": payload.bridge_instance_id,
                    "schema_version": payload.schema_version,
                    "record_type": "device",
                    "entity_id": "",
                    "entity_registry_id": "",
                    "unique_id": "",
                    "device_id": device.device_id,
                    "area_id": _string_or_empty(device.area_id),
                    "canonical_entity_id": "",
                    "canonical_device_id": canonical_device_id,
                    "canonical_area_id": canonical_area_id,
                    "floor_id": "",
                    "name": _string_or_empty(device.name),
                    "domain": "",
                    "platform": "",
                    "device_class": "",
                    "unit_of_measurement": "",
                    "state_class": "",
                    "disabled_by": "",
                    "labels_json": "",
                    "manufacturer": _string_or_empty(device.manufacturer),
                    "model": _string_or_empty(device.model),
                    "integration": _string_or_empty(device.integration),
                    "entry_type": _string_or_empty(device.entry_type),
                }
            )
        for area in payload.areas:
            canonical_area_id = canonical_ha_area_id(
                payload.bridge_instance_id,
                area.area_id,
            )
            rows.append(
                {
                    "captured_at": captured_at,
                    "bridge_instance_id": payload.bridge_instance_id,
                    "schema_version": payload.schema_version,
                    "record_type": "area",
                    "entity_id": "",
                    "entity_registry_id": "",
                    "unique_id": "",
                    "device_id": "",
                    "area_id": area.area_id,
                    "canonical_entity_id": "",
                    "canonical_device_id": "",
                    "canonical_area_id": canonical_area_id,
                    "floor_id": _string_or_empty(area.floor_id),
                    "name": area.name,
                    "domain": "",
                    "platform": "",
                    "device_class": "",
                    "unit_of_measurement": "",
                    "state_class": "",
                    "disabled_by": "",
                    "labels_json": "",
                    "manufacturer": "",
                    "model": "",
                    "integration": "",
                    "entry_type": "",
                }
            )
        return self._land_payload(
            raw_bytes=raw_bytes,
            file_name="ha-bridge-registry.json",
            source_name=source_name,
            contract=HA_BRIDGE_REGISTRY_CONTRACT,
            rows=rows,
            run_context=run_context,
        )

    def ingest_states_payload(
        self,
        *,
        raw_bytes: bytes,
        payload: HaBridgeStatesPayload,
        source_name: str = "ha-bridge-states",
        run_context: RunControlContext | None = None,
    ) -> HaBridgeLandingIngestionResult:
        rows = [
            {
                "captured_at": payload.captured_at.isoformat(),
                "bridge_instance_id": payload.bridge_instance_id,
                "schema_version": payload.schema_version,
                "batch_source": payload.batch_source,
                "entity_id": record.entity_id,
                "entity_registry_id": record.entity_registry_id,
                "canonical_entity_id": canonical_ha_entity_id(
                    payload.bridge_instance_id,
                    record.entity_registry_id,
                ),
                "state": record.state,
                "last_changed": _datetime_or_empty(record.last_changed),
                "last_updated": _datetime_or_empty(record.last_updated),
                "attributes_json": _json_or_empty(record.attributes),
            }
            for record in payload.states
        ]
        return self._land_payload(
            raw_bytes=raw_bytes,
            file_name="ha-bridge-states.json",
            source_name=source_name,
            contract=HA_BRIDGE_STATES_CONTRACT,
            rows=rows,
            run_context=run_context,
        )

    def ingest_events_payload(
        self,
        *,
        raw_bytes: bytes,
        payload: HaBridgeEventsPayload,
        source_name: str = "ha-bridge-events",
        run_context: RunControlContext | None = None,
    ) -> HaBridgeLandingIngestionResult:
        rows = [
            {
                "captured_at": payload.captured_at.isoformat(),
                "bridge_instance_id": payload.bridge_instance_id,
                "schema_version": payload.schema_version,
                "event_type": record.event_type,
                "event_fired_at": record.event_fired_at.isoformat(),
                "entity_id": record.entity_id,
                "entity_registry_id": record.entity_registry_id,
                "canonical_entity_id": canonical_ha_entity_id(
                    payload.bridge_instance_id,
                    record.entity_registry_id,
                ),
                "state": record.state,
                "old_state": _string_or_empty(record.old_state),
                "last_changed": _datetime_or_empty(record.last_changed),
                "last_updated": _datetime_or_empty(record.last_updated),
                "attributes_json": _json_or_empty(record.attributes),
            }
            for record in payload.events
        ]
        return self._land_payload(
            raw_bytes=raw_bytes,
            file_name="ha-bridge-events.json",
            source_name=source_name,
            contract=HA_BRIDGE_EVENTS_CONTRACT,
            rows=rows,
            run_context=run_context,
        )

    def ingest_statistics_payload(
        self,
        *,
        raw_bytes: bytes,
        payload: HaBridgeStatisticsPayload,
        source_name: str = "ha-bridge-statistics",
        run_context: RunControlContext | None = None,
    ) -> HaBridgeLandingIngestionResult:
        rows = [
            {
                "captured_at": payload.captured_at.isoformat(),
                "bridge_instance_id": payload.bridge_instance_id,
                "schema_version": payload.schema_version,
                "entity_id": _string_or_empty(record.entity_id),
                "entity_registry_id": record.entity_registry_id,
                "canonical_entity_id": canonical_ha_entity_id(
                    payload.bridge_instance_id,
                    record.entity_registry_id,
                ),
                "statistic_id": record.statistic_id,
                "unit": record.unit,
                "bucket_start": record.bucket_start.isoformat(),
                "bucket_end": _datetime_or_empty(record.bucket_end),
                "mean": _string_or_empty(record.mean),
                "minimum": _string_or_empty(record.minimum),
                "maximum": _string_or_empty(record.maximum),
                "sum": _string_or_empty(record.sum),
            }
            for record in payload.statistics
        ]
        return self._land_payload(
            raw_bytes=raw_bytes,
            file_name="ha-bridge-statistics.json",
            source_name=source_name,
            contract=HA_BRIDGE_STATISTICS_CONTRACT,
            rows=rows,
            run_context=run_context,
        )

    def ingest_heartbeat_payload(
        self,
        *,
        raw_bytes: bytes,
        payload: HaBridgeHeartbeatPayload,
        source_name: str = "ha-bridge-heartbeat",
        run_context: RunControlContext | None = None,
    ) -> HaBridgeLandingIngestionResult:
        rows = [
            {
                "observed_at": payload.observed_at.isoformat(),
                "bridge_instance_id": payload.bridge_instance_id,
                "schema_version": payload.schema_version,
                "bridge_version": _string_or_empty(payload.bridge_version),
                "ha_version": _string_or_empty(payload.ha_version),
                "connected": str(payload.connected).lower(),
                "buffering": str(payload.buffering).lower(),
                "entity_count": str(payload.entity_count),
                "queued_events": str(payload.queued_events),
                "oldest_queued_at": _datetime_or_empty(payload.oldest_queued_at),
                "last_delivery_at": _datetime_or_empty(payload.last_delivery_at),
            }
        ]
        return self._land_payload(
            raw_bytes=raw_bytes,
            file_name="ha-bridge-heartbeat.json",
            source_name=source_name,
            contract=HA_BRIDGE_HEARTBEAT_CONTRACT,
            rows=rows,
            run_context=run_context,
        )

    def _land_payload(
        self,
        *,
        raw_bytes: bytes,
        file_name: str,
        source_name: str,
        contract: DatasetContract,
        rows: list[dict[str, str]],
        run_context: RunControlContext | None,
    ) -> HaBridgeLandingIngestionResult:
        canonical_bytes = _rows_to_csv_bytes(
            rows,
            fieldnames=tuple(column.name for column in contract.columns),
        )
        run = self.landing_service.ingest_raw_bytes(
            source_bytes=raw_bytes,
            file_name=file_name,
            source_name=source_name,
            contract=contract,
            validation_source_bytes=canonical_bytes,
            canonical_source_bytes=canonical_bytes,
            run_context=run_context,
        )
        return HaBridgeLandingIngestionResult(run=run, rows=len(rows))


def _datetime_or_empty(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def canonical_ha_entity_id(bridge_instance_id: str, entity_registry_id: str) -> str:
    return _canonical_ha_identity("entity", bridge_instance_id, entity_registry_id)


def canonical_ha_device_id(bridge_instance_id: str, device_id: str) -> str:
    return _canonical_ha_identity("device", bridge_instance_id, device_id)


def canonical_ha_area_id(bridge_instance_id: str, area_id: str) -> str:
    return _canonical_ha_identity("area", bridge_instance_id, area_id)


def _canonical_ha_device_id_or_empty(
    bridge_instance_id: str,
    device_id: str | None,
) -> str:
    if device_id is None or not str(device_id).strip():
        return ""
    return canonical_ha_device_id(bridge_instance_id, device_id)


def _canonical_ha_area_id_or_empty(
    bridge_instance_id: str,
    area_id: str | None,
) -> str:
    if area_id is None or not str(area_id).strip():
        return ""
    return canonical_ha_area_id(bridge_instance_id, area_id)


def _canonical_ha_identity(identity_kind: str, bridge_instance_id: str, source_id: str) -> str:
    normalized_bridge_instance_id = bridge_instance_id.strip()
    normalized_source_id = source_id.strip()
    if not normalized_bridge_instance_id:
        raise ValueError("HA bridge canonical identity requires a bridge_instance_id.")
    if not normalized_source_id:
        raise ValueError(
            f"HA bridge canonical identity requires a non-empty {identity_kind} source id."
        )
    return f"ha-{identity_kind}:{normalized_bridge_instance_id}:{normalized_source_id}"


def _string_or_empty(value: object | None) -> str:
    return "" if value is None else str(value)


def _json_or_empty(value: object) -> str:
    if value in ({}, [], (), None):
        return ""
    return json.dumps(value, sort_keys=True)


def _rows_to_csv_bytes(rows: list[dict[str, str]], *, fieldnames: tuple[str, ...]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({name: row.get(name, "") for name in fieldnames})
    return buffer.getvalue().encode("utf-8")


__all__ = [
    "HA_BRIDGE_SCHEMA_VERSION",
    "HA_BRIDGE_REGISTRY_CONTRACT",
    "HA_BRIDGE_STATES_CONTRACT",
    "HA_BRIDGE_EVENTS_CONTRACT",
    "HA_BRIDGE_STATISTICS_CONTRACT",
    "HA_BRIDGE_HEARTBEAT_CONTRACT",
    "canonical_ha_entity_id",
    "canonical_ha_device_id",
    "canonical_ha_area_id",
    "HaBridgeRegistryPayload",
    "HaBridgeStatesPayload",
    "HaBridgeEventsPayload",
    "HaBridgeStatisticsPayload",
    "HaBridgeHeartbeatPayload",
    "HaBridgeLandingIngestionResult",
    "HaBridgeLandingService",
]
