"""Tests for HA service — entity ingest and history retrieval.

Acceptance criteria (from sprint docs):
- ingest_ha_states writes fact_ha_state_change rows
- ingest_ha_states upserts dim_ha_entity (insert new, update existing)
- entity_class derived correctly from entity_id prefix
- unit_of_measurement extracted from attributes
- friendly_name extracted from attributes
- canonical_id defaults to entity_id
- get_ha_entities returns all entities
- get_ha_entity_history returns rows for correct entity
- get_ha_entity_history respects limit
- duplicate ingest (same run_id) appends rows (historian model)
- empty states batch returns 0
- states with missing attributes fields are tolerated
"""
from __future__ import annotations

import json
import unittest

from packages.pipelines.ha_models import entity_class_from_id
from packages.pipelines.ha_service import (
    get_ha_entities,
    get_ha_entity_history,
    ingest_ha_states,
)
from packages.storage.duckdb_store import DuckDBStore


def _store() -> DuckDBStore:
    return DuckDBStore.memory()


def _states() -> list[dict]:
    return [
        {
            "entity_id": "sensor.living_room_temp",
            "state": "21.3",
            "attributes": {
                "unit_of_measurement": "°C",
                "friendly_name": "Living Room Temperature",
            },
            "last_changed": "2026-03-21T10:00:00+00:00",
        },
        {
            "entity_id": "light.kitchen",
            "state": "on",
            "attributes": {
                "friendly_name": "Kitchen Light",
                "brightness": 255,
            },
            "last_changed": "2026-03-21T10:00:00+00:00",
        },
        {
            "entity_id": "binary_sensor.front_door",
            "state": "off",
            "attributes": {
                "friendly_name": "Front Door",
                "device_class": "door",
            },
            "last_changed": "2026-03-21T09:55:00+00:00",
        },
        {
            "entity_id": "climate.thermostat",
            "state": "heating",
            "attributes": {
                "friendly_name": "Living Room Thermostat",
                "current_temperature": 20.5,
                "temperature": 22.0,
            },
            "last_changed": "2026-03-21T10:00:00+00:00",
        },
    ]


class EntityClassTests(unittest.TestCase):
    def test_known_prefixes(self) -> None:
        self.assertEqual("sensor", entity_class_from_id("sensor.living_room_temp"))
        self.assertEqual("light", entity_class_from_id("light.kitchen"))
        self.assertEqual("binary_sensor", entity_class_from_id("binary_sensor.front_door"))
        self.assertEqual("climate", entity_class_from_id("climate.thermostat"))
        self.assertEqual("switch", entity_class_from_id("switch.bedroom_fan"))

    def test_unknown_prefix_returns_other(self) -> None:
        self.assertEqual("other", entity_class_from_id("unknown_domain.thing"))

    def test_no_dot_returns_other(self) -> None:
        self.assertEqual("other", entity_class_from_id("no_dot_entity"))


class IngestHaStatesTests(unittest.TestCase):
    def test_ingest_returns_entity_count(self) -> None:
        store = _store()
        count = ingest_ha_states(store, _states(), run_id="run-001")
        self.assertEqual(4, count)

    def test_empty_states_returns_zero(self) -> None:
        store = _store()
        count = ingest_ha_states(store, [], run_id="run-001")
        self.assertEqual(0, count)

    def test_fact_rows_written(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        rows = get_ha_entity_history(store, "sensor.living_room_temp")
        self.assertEqual(1, len(rows))
        self.assertEqual("21.3", rows[0]["state"])

    def test_dim_entity_created(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = get_ha_entities(store)
        entity_ids = {e["entity_id"] for e in entities}
        self.assertIn("sensor.living_room_temp", entity_ids)
        self.assertIn("light.kitchen", entity_ids)

    def test_friendly_name_extracted(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = {e["entity_id"]: e for e in get_ha_entities(store)}
        self.assertEqual("Living Room Temperature", entities["sensor.living_room_temp"]["friendly_name"])
        self.assertEqual("Kitchen Light", entities["light.kitchen"]["friendly_name"])

    def test_unit_extracted(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = {e["entity_id"]: e for e in get_ha_entities(store)}
        self.assertEqual("°C", entities["sensor.living_room_temp"]["unit"])
        self.assertIsNone(entities["light.kitchen"]["unit"])

    def test_entity_class_derived(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = {e["entity_id"]: e for e in get_ha_entities(store)}
        self.assertEqual("sensor", entities["sensor.living_room_temp"]["entity_class"])
        self.assertEqual("light", entities["light.kitchen"]["entity_class"])
        self.assertEqual("binary_sensor", entities["binary_sensor.front_door"]["entity_class"])

    def test_canonical_id_defaults_to_entity_id(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = {e["entity_id"]: e for e in get_ha_entities(store)}
        for entity in entities.values():
            self.assertEqual(entity["entity_id"], entity["canonical_id"])

    def test_upsert_updates_last_state(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        updated = [
            {
                "entity_id": "sensor.living_room_temp",
                "state": "22.0",
                "attributes": {"unit_of_measurement": "°C", "friendly_name": "Living Room Temperature"},
                "last_changed": "2026-03-21T11:00:00+00:00",
            }
        ]
        ingest_ha_states(store, updated, run_id="run-002")
        entities = {e["entity_id"]: e for e in get_ha_entities(store)}
        self.assertEqual("22.0", entities["sensor.living_room_temp"]["last_state"])

    def test_duplicate_ingest_appends_fact_rows(self) -> None:
        """Historian model: every ingest appends, no dedup."""
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        ingest_ha_states(store, _states(), run_id="run-001")
        rows = get_ha_entity_history(store, "sensor.living_room_temp", limit=10)
        self.assertEqual(2, len(rows))

    def test_missing_attributes_tolerated(self) -> None:
        store = _store()
        states = [{"entity_id": "sensor.bare", "state": "42", "last_changed": "2026-03-21T10:00:00"}]
        count = ingest_ha_states(store, states)
        self.assertEqual(1, count)

    def test_run_id_stored_in_fact(self) -> None:
        store = _store()
        ingest_ha_states(store, _states()[:1], run_id="explicit-run-42")
        rows = get_ha_entity_history(store, "sensor.living_room_temp")
        self.assertEqual("explicit-run-42", rows[0]["run_id"])


class GetHaEntitiesTests(unittest.TestCase):
    def test_returns_all_entities(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        entities = get_ha_entities(store)
        self.assertEqual(4, len(entities))

    def test_empty_store_returns_empty(self) -> None:
        store = _store()
        self.assertEqual([], get_ha_entities(store))


class GetHaEntityHistoryTests(unittest.TestCase):
    def test_returns_rows_for_entity(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        rows = get_ha_entity_history(store, "light.kitchen")
        self.assertEqual(1, len(rows))
        self.assertEqual("on", rows[0]["state"])

    def test_unknown_entity_returns_empty(self) -> None:
        store = _store()
        ingest_ha_states(store, _states(), run_id="run-001")
        rows = get_ha_entity_history(store, "sensor.does_not_exist")
        self.assertEqual([], rows)

    def test_limit_respected(self) -> None:
        store = _store()
        # Ingest 5 times to create 5 history rows for one entity
        for i in range(5):
            ingest_ha_states(
                store,
                [{"entity_id": "sensor.temp", "state": str(i), "last_changed": f"2026-03-21T{10 + i}:00:00"}],
                run_id=f"run-{i:03d}",
            )
        rows = get_ha_entity_history(store, "sensor.temp", limit=3)
        self.assertEqual(3, len(rows))

    def test_attributes_json_stored(self) -> None:
        store = _store()
        ingest_ha_states(store, _states()[:1], run_id="run-001")
        rows = get_ha_entity_history(store, "sensor.living_room_temp")
        attrs = json.loads(rows[0]["attributes"])
        self.assertEqual("°C", attrs["unit_of_measurement"])


if __name__ == "__main__":
    unittest.main()
