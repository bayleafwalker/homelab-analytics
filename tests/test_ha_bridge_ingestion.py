from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from packages.domains.homelab.pipelines.ha_bridge_ingestion import (
    HA_BRIDGE_EVENTS_CONTRACT,
    HA_BRIDGE_HEARTBEAT_CONTRACT,
    HA_BRIDGE_REGISTRY_CONTRACT,
    HA_BRIDGE_STATES_CONTRACT,
    HA_BRIDGE_STATISTICS_CONTRACT,
    HaBridgeEventsPayload,
    HaBridgeHeartbeatPayload,
    HaBridgeLandingService,
    HaBridgeRegistryPayload,
    HaBridgeStatesPayload,
    HaBridgeStatisticsPayload,
    canonical_ha_area_id,
    canonical_ha_device_id,
    canonical_ha_entity_id,
)
from packages.storage.blob import FilesystemBlobStore
from packages.storage.run_metadata import RunMetadataRepository


class HaBridgeLandingServiceTests(unittest.TestCase):
    def test_registry_payload_lands_raw_json_and_canonical_csv(self) -> None:
        payload_dict = {
            "schema_version": "1.0",
            "bridge_instance_id": "bridge-1",
            "captured_at": "2026-04-08T10:00:00+00:00",
            "entities": [
                {
                    "entity_id": "sensor.kitchen_power",
                    "entity_registry_id": "entity-reg-1",
                    "unique_id": "kitchen-power",
                    "device_id": "device-1",
                    "area_id": "kitchen",
                    "platform": "mqtt",
                    "domain": "sensor",
                    "device_class": "power",
                    "unit_of_measurement": "W",
                    "state_class": "measurement",
                    "labels": ["energy", "kitchen"],
                }
            ],
            "devices": [
                {
                    "device_id": "device-1",
                    "name": "Kitchen Plug",
                    "manufacturer": "Shelly",
                    "model": "Plug S",
                    "area_id": "kitchen",
                    "integration": "mqtt",
                    "entry_type": "service",
                }
            ],
            "areas": [
                {
                    "area_id": "kitchen",
                    "name": "Kitchen",
                    "floor_id": "ground",
                }
            ],
        }
        raw_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = HaBridgeRegistryPayload.model_validate(payload_dict)

        with TemporaryDirectory() as temp_dir:
            service = _build_service(Path(temp_dir))
            result = service.ingest_registry_payload(raw_bytes=raw_bytes, payload=payload)
            assert result.run.canonical_path is not None

            self.assertEqual(3, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual(
                HA_BRIDGE_REGISTRY_CONTRACT.dataset_name,
                "ha_bridge_registry_snapshot",
            )
            self.assertEqual(raw_bytes, Path(result.run.raw_path).read_bytes())
            self.assertEqual(
                [
                    {
                        "captured_at": "2026-04-08T10:00:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "record_type": "entity",
                        "entity_id": "sensor.kitchen_power",
                        "entity_registry_id": "entity-reg-1",
                        "unique_id": "kitchen-power",
                        "device_id": "device-1",
                        "area_id": "kitchen",
                        "canonical_entity_id": "ha-entity:bridge-1:entity-reg-1",
                        "canonical_device_id": "ha-device:bridge-1:device-1",
                        "canonical_area_id": "ha-area:bridge-1:kitchen",
                        "floor_id": "",
                        "name": "",
                        "domain": "sensor",
                        "platform": "mqtt",
                        "device_class": "power",
                        "unit_of_measurement": "W",
                        "state_class": "measurement",
                        "disabled_by": "",
                        "labels_json": '["energy", "kitchen"]',
                        "manufacturer": "",
                        "model": "",
                        "integration": "",
                        "entry_type": "",
                    },
                    {
                        "captured_at": "2026-04-08T10:00:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "record_type": "device",
                        "entity_id": "",
                        "entity_registry_id": "",
                        "unique_id": "",
                        "device_id": "device-1",
                        "area_id": "kitchen",
                        "canonical_entity_id": "",
                        "canonical_device_id": "ha-device:bridge-1:device-1",
                        "canonical_area_id": "ha-area:bridge-1:kitchen",
                        "floor_id": "",
                        "name": "Kitchen Plug",
                        "domain": "",
                        "platform": "",
                        "device_class": "",
                        "unit_of_measurement": "",
                        "state_class": "",
                        "disabled_by": "",
                        "labels_json": "",
                        "manufacturer": "Shelly",
                        "model": "Plug S",
                        "integration": "mqtt",
                        "entry_type": "service",
                    },
                    {
                        "captured_at": "2026-04-08T10:00:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "record_type": "area",
                        "entity_id": "",
                        "entity_registry_id": "",
                        "unique_id": "",
                        "device_id": "",
                        "area_id": "kitchen",
                        "canonical_entity_id": "",
                        "canonical_device_id": "",
                        "canonical_area_id": "ha-area:bridge-1:kitchen",
                        "floor_id": "ground",
                        "name": "Kitchen",
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
                    },
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )

    def test_states_payload_lands_raw_json_and_canonical_csv(self) -> None:
        payload_dict = {
            "schema_version": "1.0",
            "bridge_instance_id": "bridge-1",
            "captured_at": "2026-04-08T10:05:00+00:00",
            "batch_source": "startup",
            "states": [
                {
                    "entity_id": "sensor.kitchen_power",
                    "entity_registry_id": "entity-reg-1",
                    "state": "42.5",
                    "last_changed": "2026-04-08T10:04:58+00:00",
                    "last_updated": "2026-04-08T10:04:59+00:00",
                    "attributes": {"friendly_name": "Kitchen Power", "unit_of_measurement": "W"},
                }
            ],
        }
        raw_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = HaBridgeStatesPayload.model_validate(payload_dict)

        with TemporaryDirectory() as temp_dir:
            service = _build_service(Path(temp_dir))
            result = service.ingest_states_payload(raw_bytes=raw_bytes, payload=payload)
            assert result.run.canonical_path is not None

            self.assertEqual(1, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual("ha_bridge_states", HA_BRIDGE_STATES_CONTRACT.dataset_name)
            self.assertEqual(raw_bytes, Path(result.run.raw_path).read_bytes())
            self.assertEqual(
                [
                    {
                        "captured_at": "2026-04-08T10:05:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "batch_source": "startup",
                        "entity_id": "sensor.kitchen_power",
                        "entity_registry_id": "entity-reg-1",
                        "canonical_entity_id": "ha-entity:bridge-1:entity-reg-1",
                        "state": "42.5",
                        "last_changed": "2026-04-08T10:04:58+00:00",
                        "last_updated": "2026-04-08T10:04:59+00:00",
                        "attributes_json": '{"friendly_name": "Kitchen Power", "unit_of_measurement": "W"}',
                    }
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )

    def test_events_payload_lands_raw_json_and_canonical_csv(self) -> None:
        payload_dict = {
            "schema_version": "1.0",
            "bridge_instance_id": "bridge-1",
            "captured_at": "2026-04-08T10:06:00+00:00",
            "events": [
                {
                    "event_type": "state_changed",
                    "event_fired_at": "2026-04-08T10:05:59+00:00",
                    "entity_id": "binary_sensor.front_door",
                    "entity_registry_id": "entity-reg-2",
                    "state": "on",
                    "old_state": "off",
                    "last_changed": "2026-04-08T10:05:59+00:00",
                    "last_updated": "2026-04-08T10:05:59+00:00",
                    "attributes": {"friendly_name": "Front Door"},
                }
            ],
        }
        raw_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = HaBridgeEventsPayload.model_validate(payload_dict)

        with TemporaryDirectory() as temp_dir:
            service = _build_service(Path(temp_dir))
            result = service.ingest_events_payload(raw_bytes=raw_bytes, payload=payload)
            assert result.run.canonical_path is not None

            self.assertEqual(1, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual("ha_bridge_events", HA_BRIDGE_EVENTS_CONTRACT.dataset_name)
            self.assertEqual(
                [
                    {
                        "captured_at": "2026-04-08T10:06:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "event_type": "state_changed",
                        "event_fired_at": "2026-04-08T10:05:59+00:00",
                        "entity_id": "binary_sensor.front_door",
                        "entity_registry_id": "entity-reg-2",
                        "canonical_entity_id": "ha-entity:bridge-1:entity-reg-2",
                        "state": "on",
                        "old_state": "off",
                        "last_changed": "2026-04-08T10:05:59+00:00",
                        "last_updated": "2026-04-08T10:05:59+00:00",
                        "attributes_json": '{"friendly_name": "Front Door"}',
                    }
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )

    def test_statistics_payload_lands_raw_json_and_canonical_csv(self) -> None:
        payload_dict = {
            "schema_version": "1.0",
            "bridge_instance_id": "bridge-1",
            "captured_at": "2026-04-08T10:10:00+00:00",
            "statistics": [
                {
                    "entity_id": "sensor.daily_energy",
                    "entity_registry_id": "entity-reg-3",
                    "statistic_id": "sensor.daily_energy",
                    "unit": "kWh",
                    "bucket_start": "2026-04-08T09:00:00+00:00",
                    "bucket_end": "2026-04-08T10:00:00+00:00",
                    "mean": "1.25",
                    "minimum": "0.4",
                    "maximum": "2.5",
                    "sum": "5.0",
                }
            ],
        }
        raw_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = HaBridgeStatisticsPayload.model_validate(payload_dict)

        with TemporaryDirectory() as temp_dir:
            service = _build_service(Path(temp_dir))
            result = service.ingest_statistics_payload(raw_bytes=raw_bytes, payload=payload)
            assert result.run.canonical_path is not None

            self.assertEqual(1, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual(
                "ha_bridge_statistics",
                HA_BRIDGE_STATISTICS_CONTRACT.dataset_name,
            )
            self.assertEqual(
                [
                    {
                        "captured_at": "2026-04-08T10:10:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "entity_id": "sensor.daily_energy",
                        "entity_registry_id": "entity-reg-3",
                        "canonical_entity_id": "ha-entity:bridge-1:entity-reg-3",
                        "statistic_id": "sensor.daily_energy",
                        "unit": "kWh",
                        "bucket_start": "2026-04-08T09:00:00+00:00",
                        "bucket_end": "2026-04-08T10:00:00+00:00",
                        "mean": "1.25",
                        "minimum": "0.4",
                        "maximum": "2.5",
                        "sum": "5.0",
                    }
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )

    def test_canonical_identity_helpers_namespace_ha_registry_ids(self) -> None:
        self.assertEqual(
            "ha-entity:bridge-1:entity-reg-1",
            canonical_ha_entity_id("bridge-1", "entity-reg-1"),
        )
        self.assertEqual(
            "ha-device:bridge-1:device-reg-1",
            canonical_ha_device_id("bridge-1", "device-reg-1"),
        )
        self.assertEqual(
            "ha-area:bridge-1:kitchen",
            canonical_ha_area_id("bridge-1", "kitchen"),
        )

    def test_heartbeat_payload_lands_raw_json_and_canonical_csv(self) -> None:
        payload_dict = {
            "schema_version": "1.0",
            "bridge_instance_id": "bridge-1",
            "observed_at": "2026-04-08T10:15:00+00:00",
            "bridge_version": "0.1.0",
            "ha_version": "2026.4.0",
            "connected": True,
            "buffering": False,
            "entity_count": 128,
            "queued_events": 3,
            "oldest_queued_at": "2026-04-08T10:14:30+00:00",
            "last_delivery_at": "2026-04-08T10:14:59+00:00",
        }
        raw_bytes = json.dumps(payload_dict, separators=(",", ":"), sort_keys=True).encode("utf-8")
        payload = HaBridgeHeartbeatPayload.model_validate(payload_dict)

        with TemporaryDirectory() as temp_dir:
            service = _build_service(Path(temp_dir))
            result = service.ingest_heartbeat_payload(raw_bytes=raw_bytes, payload=payload)
            assert result.run.canonical_path is not None

            self.assertEqual(1, result.rows)
            self.assertTrue(result.run.validation.passed)
            self.assertEqual(
                "ha_bridge_heartbeat",
                HA_BRIDGE_HEARTBEAT_CONTRACT.dataset_name,
            )
            self.assertEqual(
                [
                    {
                        "observed_at": "2026-04-08T10:15:00+00:00",
                        "bridge_instance_id": "bridge-1",
                        "schema_version": "1.0",
                        "bridge_version": "0.1.0",
                        "ha_version": "2026.4.0",
                        "connected": "true",
                        "buffering": "false",
                        "entity_count": "128",
                        "queued_events": "3",
                        "oldest_queued_at": "2026-04-08T10:14:30+00:00",
                        "last_delivery_at": "2026-04-08T10:14:59+00:00",
                    }
                ],
                _read_csv_rows(Path(result.run.canonical_path)),
            )


def _build_service(temp_root: Path) -> HaBridgeLandingService:
    return HaBridgeLandingService(
        temp_root / "landing",
        RunMetadataRepository(temp_root / "runs.db"),
        blob_store=FilesystemBlobStore(temp_root / "landing"),
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    unittest.main()
