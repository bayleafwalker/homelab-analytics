"""Tests for HaBridgeWorker — WebSocket bridge event handling and status.

These tests exercise the synchronous parts of the bridge (event handler,
status reporting, WS URL construction) without requiring a live HA instance
or a real WebSocket connection.
"""
from __future__ import annotations

import unittest

from packages.pipelines.ha_bridge import HaBridgeWorker, _ws_url_from_ha_url


def _make_state_changed_msg(entity_id="sensor.temp", state="21.5", attrs=None) -> dict:
    """Build a minimal HA state_changed WS event message."""
    return {
        "type": "event",
        "event": {
            "event_type": "state_changed",
            "data": {
                "entity_id": entity_id,
                "new_state": {
                    "entity_id": entity_id,
                    "state": state,
                    "attributes": attrs or {"unit_of_measurement": "°C"},
                    "last_changed": "2026-03-21T10:00:00+00:00",
                },
                "old_state": None,
            },
        },
    }


def _bridge(ingest_fn=None) -> HaBridgeWorker:
    return HaBridgeWorker(
        ingest_fn or (lambda states, **kw: len(states)),
        ha_url="http://homeassistant.local:8123",
        ha_token="test-token",
    )


class WsUrlConstructionTests(unittest.TestCase):
    def test_http_becomes_ws(self) -> None:
        self.assertEqual(
            "ws://homeassistant.local:8123/api/websocket",
            _ws_url_from_ha_url("http://homeassistant.local:8123"),
        )

    def test_https_becomes_wss(self) -> None:
        self.assertEqual(
            "wss://ha.example.com/api/websocket",
            _ws_url_from_ha_url("https://ha.example.com"),
        )

    def test_trailing_slash_stripped(self) -> None:
        self.assertEqual(
            "ws://ha.local:8123/api/websocket",
            _ws_url_from_ha_url("http://ha.local:8123/"),
        )

    def test_ws_url_stored_on_worker(self) -> None:
        bridge = _bridge()
        self.assertEqual("ws://homeassistant.local:8123/api/websocket", bridge._ws_url)


class BridgeStatusTests(unittest.TestCase):
    def test_initial_status_not_connected(self) -> None:
        bridge = _bridge()
        status = bridge.get_status()
        self.assertFalse(status["connected"])
        self.assertIsNone(status["last_sync_at"])
        self.assertEqual(0, status["reconnect_count"])

    def test_status_keys_present(self) -> None:
        bridge = _bridge()
        status = bridge.get_status()
        self.assertIn("connected", status)
        self.assertIn("last_sync_at", status)
        self.assertIn("reconnect_count", status)


class HandleEventTests(unittest.TestCase):
    def test_state_changed_event_calls_ingest(self) -> None:
        ingested: list = []

        def fake_ingest(states, *, run_id=None, source_system="home_assistant"):
            ingested.extend(states)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event(_make_state_changed_msg("sensor.temp", "21.5"))

        self.assertEqual(1, len(ingested))
        self.assertEqual("sensor.temp", ingested[0]["entity_id"])
        self.assertEqual("21.5", ingested[0]["state"])

    def test_source_system_set_to_ha_websocket(self) -> None:
        captured: list[str] = []

        def fake_ingest(states, *, run_id=None, source_system="home_assistant"):
            captured.append(source_system)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event(_make_state_changed_msg())
        self.assertEqual(["ha_websocket"], captured)

    def test_last_sync_at_updated_on_event(self) -> None:
        bridge = _bridge()
        self.assertIsNone(bridge.last_sync_at)
        bridge._handle_event(_make_state_changed_msg())
        self.assertIsNotNone(bridge.last_sync_at)

    def test_non_event_message_ignored(self) -> None:
        ingested: list = []

        def fake_ingest(states, **kw):
            ingested.extend(states)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event({"type": "result", "success": True})
        self.assertEqual([], ingested)

    def test_non_state_changed_event_type_ignored(self) -> None:
        ingested: list = []

        def fake_ingest(states, **kw):
            ingested.extend(states)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event({
            "type": "event",
            "event": {"event_type": "call_service", "data": {}},
        })
        self.assertEqual([], ingested)

    def test_event_without_new_state_ignored(self) -> None:
        ingested: list = []

        def fake_ingest(states, **kw):
            ingested.extend(states)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event({
            "type": "event",
            "event": {
                "event_type": "state_changed",
                "data": {"entity_id": "sensor.temp", "new_state": None},
            },
        })
        self.assertEqual([], ingested)

    def test_run_id_is_unique_per_event(self) -> None:
        run_ids: list[str] = []

        def fake_ingest(states, *, run_id=None, source_system="home_assistant"):
            if run_id:
                run_ids.append(run_id)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event(_make_state_changed_msg("sensor.a", "1"))
        bridge._handle_event(_make_state_changed_msg("sensor.b", "2"))

        self.assertEqual(2, len(run_ids))
        self.assertNotEqual(run_ids[0], run_ids[1])

    def test_attributes_passed_through(self) -> None:
        ingested: list = []

        def fake_ingest(states, **kw):
            ingested.extend(states)
            return len(states)

        bridge = _bridge(fake_ingest)
        bridge._handle_event(
            _make_state_changed_msg("sensor.temp", "22", attrs={"unit_of_measurement": "°C"})
        )
        self.assertEqual({"unit_of_measurement": "°C"}, ingested[0]["attributes"])


if __name__ == "__main__":
    unittest.main()
