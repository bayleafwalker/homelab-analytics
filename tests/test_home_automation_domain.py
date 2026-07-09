from __future__ import annotations

import unittest
from datetime import date
from decimal import Decimal

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

    def test_refresh_climate_summary_aggregates_by_day_area_and_measure(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_home_automation_state(
            [
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "21.0",
                    "attributes": {
                        "unit_of_measurement": "°C",
                        "area_id": "living-room",
                    },
                    "last_changed": "2026-03-28T08:00:00+00:00",
                },
                {
                    "entity_id": "sensor.living_room_temperature",
                    "state": "23.0",
                    "attributes": {
                        "unit_of_measurement": "°C",
                        "area_id": "living-room",
                    },
                    "last_changed": "2026-03-28T14:00:00+00:00",
                },
                {
                    "entity_id": "sensor.living_room_humidity",
                    "state": "44.0",
                    "attributes": {
                        "unit_of_measurement": "%",
                        "area_id": "living-room",
                    },
                    "last_changed": "2026-03-28T08:00:00+00:00",
                },
                # non-numeric state must be skipped, not crash the refresh
                {
                    "entity_id": "sensor.bedroom_temperature",
                    "state": "unavailable",
                    "attributes": {
                        "unit_of_measurement": "°C",
                        "area_id": "bedroom",
                    },
                    "last_changed": "2026-03-28T08:00:00+00:00",
                },
                # non-climate sensor is ignored entirely
                {
                    "entity_id": "sensor.front_door_lock",
                    "state": "locked",
                    "attributes": {"area_id": "hallway"},
                    "last_changed": "2026-03-28T08:00:00+00:00",
                },
            ],
            run_id="ha-run-010",
            source_system="home_assistant",
        )

        count = service.refresh_climate_summary()

        self.assertEqual(2, count)
        rows = service.get_climate_summary()
        by_measure = {row["measure"]: row for row in rows}
        temperature = by_measure["temperature"]
        self.assertEqual(date(2026, 3, 28), temperature["period_day"])
        self.assertEqual("living-room", temperature["area"])
        self.assertEqual(Decimal("22.0000"), Decimal(temperature["avg_value"]))
        self.assertEqual(Decimal("21.0000"), Decimal(temperature["min_value"]))
        self.assertEqual(Decimal("23.0000"), Decimal(temperature["max_value"]))
        self.assertEqual(2, temperature["reading_count"])

        humidity_rows = service.get_climate_summary(measure="humidity")
        self.assertEqual(1, len(humidity_rows))
        self.assertEqual(Decimal("44.0000"), Decimal(humidity_rows[0]["avg_value"]))

    def test_refresh_automation_reliability_counts_success_and_failure(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_automation_events(
            [
                {
                    "entity_id": "automation.morning_routine",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Morning Routine",
                        "result": "success",
                    },
                    "last_changed": "2026-03-01T07:00:00+00:00",
                },
                {
                    "entity_id": "automation.morning_routine",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Morning Routine",
                        "result": "error",
                    },
                    "last_changed": "2026-03-02T07:00:00+00:00",
                },
                {
                    "entity_id": "automation.morning_routine",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Morning Routine",
                        "result": "success",
                    },
                    "last_changed": "2026-03-03T07:00:00+00:00",
                },
                {
                    "entity_id": "automation.night_mode",
                    "state": "on",
                    "attributes": {
                        "friendly_name": "Night Mode",
                        "result": "success",
                    },
                    "last_changed": "2026-04-01T22:00:00+00:00",
                },
            ],
            run_id="ha-run-011",
            source_system="home_assistant",
        )

        count = service.refresh_automation_reliability()

        self.assertEqual(2, count)
        morning_rows = service.get_automation_reliability(
            entity_id="automation.morning_routine"
        )
        self.assertEqual(1, len(morning_rows))
        morning = morning_rows[0]
        self.assertEqual("2026-03", morning["period_month"])
        self.assertEqual(3, morning["run_count"])
        self.assertEqual(2, morning["success_count"])
        self.assertEqual(1, morning["failure_count"])
        self.assertEqual(Decimal("66.667"), Decimal(morning["success_rate_pct"]))
        self.assertEqual("success", morning["last_result"])

        night = service.get_automation_reliability(entity_id="automation.night_mode")[0]
        self.assertEqual("2026-04", night["period_month"])
        self.assertEqual(Decimal("100.000"), Decimal(night["success_rate_pct"]))

    def test_refresh_device_battery_projects_drain_and_status(self) -> None:
        service = TransformationService(DuckDBStore.memory())
        service.load_home_automation_state(
            [
                # 90% → 80% over 5 days: 2%/day drain, 40 days to empty
                {
                    "entity_id": "sensor.door_sensor_battery",
                    "state": "90",
                    "attributes": {
                        "unit_of_measurement": "%",
                        "area_id": "hallway",
                        "device_name": "Door Sensor",
                    },
                    "last_changed": "2026-03-01T00:00:00+00:00",
                },
                {
                    "entity_id": "sensor.door_sensor_battery",
                    "state": "80",
                    "attributes": {
                        "unit_of_measurement": "%",
                        "area_id": "hallway",
                        "device_name": "Door Sensor",
                    },
                    "last_changed": "2026-03-06T00:00:00+00:00",
                },
                # single low reading: no drain estimate, low status
                {
                    "entity_id": "sensor.motion_sensor_battery",
                    "state": "18",
                    "attributes": {"unit_of_measurement": "%"},
                    "last_changed": "2026-03-06T00:00:00+00:00",
                },
            ],
            run_id="ha-run-012",
            source_system="home_assistant",
        )

        count = service.refresh_device_battery()

        self.assertEqual(2, count)
        rows = {row["entity_id"]: row for row in service.get_device_battery()}

        door = rows["sensor.door_sensor_battery"]
        self.assertEqual(Decimal("80.00"), Decimal(door["battery_pct"]))
        self.assertEqual(Decimal("2.0000"), Decimal(door["avg_daily_drain_pct"]))
        self.assertEqual(40, door["est_days_to_empty"])
        self.assertEqual("ok", door["battery_status"])
        self.assertEqual("hallway", door["area"])

        motion = rows["sensor.motion_sensor_battery"]
        self.assertIsNone(motion["avg_daily_drain_pct"])
        self.assertIsNone(motion["est_days_to_empty"])
        self.assertEqual("low", motion["battery_status"])

        low_rows = service.get_device_battery(battery_status="low")
        self.assertEqual(1, len(low_rows))
