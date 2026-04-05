from __future__ import annotations

import unittest

from packages.pipelines.transformation_service import TransformationService
from packages.storage.duckdb_store import DuckDBStore


class HomeAutomationDomainTests(unittest.TestCase):
    def test_sensor_readings_load_entities_and_facts(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        inserted = service.load_domain_rows(
            "home_automation_state",
            [
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "21.3",
                    "attributes": {
                        "friendly_name": "Living Room Temperature",
                        "unit_of_measurement": "°C",
                        "area_id": "living-room",
                        "integration": "home_assistant",
                    },
                    "last_changed": "2026-03-28T10:00:00+00:00",
                },
                {
                    "entity_id": "sensor.living_room_humidity",
                    "state": "44.0",
                    "attributes": {
                        "friendly_name": "Living Room Humidity",
                        "unit_of_measurement": "%",
                        "area_id": "living-room",
                        "integration": "home_assistant",
                    },
                    "last_changed": "2026-03-28T10:00:00+00:00",
                },
            ],
            run_id="ha-run-001",
            source_system="home_assistant",
        )

        self.assertEqual(2, inserted)
        self.assertEqual(2, service.count_sensor_reading_rows())
        self.assertEqual(0, service.count_automation_event_rows())
        entities = {row["entity_id"]: row for row in service.get_current_entities()}
        self.assertEqual("Living Room Temperature", entities["sensor.living_room_temperature"]["entity_name"])
        self.assertEqual("sensor", entities["sensor.living_room_temperature"]["entity_class"])
        self.assertEqual("living-room", entities["sensor.living_room_temperature"]["area"])

    def test_automation_events_append_and_update_entity_metadata(self) -> None:
        service = TransformationService(DuckDBStore.memory())

        service.load_home_automation_state(
            [
                {
                    "entity_id": "automation.morning_routine",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Morning Routine",
                        "trigger": "time",
                        "result": "success",
                        "area_id": "hallway",
                        "integration": "home_assistant",
                    },
                    "last_changed": "2026-03-28T07:00:00+00:00",
                }
            ],
            run_id="ha-run-002",
            source_system="home_assistant",
        )

        service.load_automation_events(
            [
                {
                    "entity_id": "automation.morning_routine",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Morning Routine v2",
                        "trigger": "time",
                        "result": "success",
                        "area_id": "hallway",
                        "integration": "home_assistant",
                    },
                    "last_changed": "2026-03-28T08:00:00+00:00",
                }
            ],
            run_id="ha-run-003",
            source_system="home_assistant",
        )

        self.assertEqual(2, service.count_automation_event_rows())
        self.assertEqual(2, service.count_home_automation_state_rows())
        entities = {row["entity_id"]: row for row in service.get_current_entities()}
        self.assertEqual("Morning Routine v2", entities["automation.morning_routine"]["entity_name"])
        self.assertEqual("automation", entities["automation.morning_routine"]["entity_class"])
        self.assertEqual("hallway", entities["automation.morning_routine"]["area"])
