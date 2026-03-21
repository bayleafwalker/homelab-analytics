"""Tests for HaMqttPublisher — MQTT synthetic entity publication.

These tests exercise the synchronous parts of the publisher (URL parsing,
discovery payload construction, state value resolution, status reporting)
without requiring a live MQTT broker.
"""
from __future__ import annotations

import json
import unittest

from packages.pipelines.ha_mqtt_publisher import (
    _DEVICE_AVAILABILITY_TOPIC,
    _SYNTHETIC_ENTITIES,
    HaMqttPublisher,
    _build_discovery_payload,
    _build_state_value,
    _discovery_topic,
    _parse_broker_url,
    _state_topic,
)


def _publisher(fetch_fn=None) -> HaMqttPublisher:
    return HaMqttPublisher(
        fetch_fn or (lambda: {"bridge_last_sync_at": None, "bridge_connected": False}),
        broker_url="mqtt://mosquitto.local:1883",
    )


class BrokerUrlParseTests(unittest.TestCase):
    def test_full_mqtt_url(self) -> None:
        host, port = _parse_broker_url("mqtt://mosquitto.local:1883")
        self.assertEqual("mosquitto.local", host)
        self.assertEqual(1883, port)

    def test_https_scheme_stripped(self) -> None:
        host, port = _parse_broker_url("mqtts://broker.example.com:8883")
        self.assertEqual("broker.example.com", host)
        self.assertEqual(8883, port)

    def test_host_port_only(self) -> None:
        host, port = _parse_broker_url("broker.local:1884")
        self.assertEqual("broker.local", host)
        self.assertEqual(1884, port)

    def test_hostname_only_defaults_port_1883(self) -> None:
        host, port = _parse_broker_url("broker.local")
        self.assertEqual("broker.local", host)
        self.assertEqual(1883, port)

    def test_trailing_slash_stripped(self) -> None:
        host, port = _parse_broker_url("mqtt://broker.local:1883/")
        self.assertEqual("broker.local", host)
        self.assertEqual(1883, port)

    def test_stored_on_publisher(self) -> None:
        pub = _publisher()
        self.assertEqual("mosquitto.local", pub._broker_host)
        self.assertEqual(1883, pub._broker_port)


class PublisherStatusTests(unittest.TestCase):
    def test_initial_status_not_connected(self) -> None:
        pub = _publisher()
        status = pub.get_status()
        self.assertFalse(status["connected"])
        self.assertIsNone(status["last_publish_at"])
        self.assertEqual(0, status["publish_count"])

    def test_status_keys_present(self) -> None:
        pub = _publisher()
        status = pub.get_status()
        self.assertIn("connected", status)
        self.assertIn("last_publish_at", status)
        self.assertIn("publish_count", status)
        self.assertIn("entity_count", status)

    def test_entity_count_matches_synthetic_entities(self) -> None:
        pub = _publisher()
        self.assertEqual(len(_SYNTHETIC_ENTITIES), pub.get_status()["entity_count"])

    def test_optional_credentials_stored(self) -> None:
        pub = HaMqttPublisher(
            lambda: {},
            broker_url="mqtt://broker.local",
            username="user",
            password="secret",
        )
        self.assertEqual("user", pub._username)
        self.assertEqual("secret", pub._password)

    def test_no_credentials_by_default(self) -> None:
        pub = _publisher()
        self.assertIsNone(pub._username)
        self.assertIsNone(pub._password)


class TopicConstructionTests(unittest.TestCase):
    def test_discovery_topic_format(self) -> None:
        self.assertEqual(
            "homeassistant/sensor/homelab_analytics_freshness/config",
            _discovery_topic("homelab_analytics_freshness"),
        )

    def test_state_topic_format(self) -> None:
        self.assertEqual(
            "homelab_analytics/sensor/homelab_analytics_freshness/state",
            _state_topic("homelab_analytics_freshness"),
        )

    def test_device_availability_topic(self) -> None:
        self.assertEqual("homelab_analytics/availability", _DEVICE_AVAILABILITY_TOPIC)


class DiscoveryPayloadTests(unittest.TestCase):
    def _payload(self, entity=None) -> dict:
        e = entity or _SYNTHETIC_ENTITIES[0]
        return json.loads(_build_discovery_payload(e))

    def test_payload_is_valid_json(self) -> None:
        raw = _build_discovery_payload(_SYNTHETIC_ENTITIES[0])
        parsed = json.loads(raw)
        self.assertIsInstance(parsed, dict)

    def test_name_in_payload(self) -> None:
        p = self._payload()
        self.assertEqual(_SYNTHETIC_ENTITIES[0]["name"], p["name"])

    def test_unique_id_matches_object_id(self) -> None:
        p = self._payload()
        self.assertEqual(_SYNTHETIC_ENTITIES[0]["object_id"], p["unique_id"])

    def test_state_topic_in_payload(self) -> None:
        entity = _SYNTHETIC_ENTITIES[0]
        p = self._payload(entity)
        self.assertEqual(_state_topic(entity["object_id"]), p["state_topic"])

    def test_availability_topic_is_device_topic(self) -> None:
        p = self._payload()
        self.assertEqual(_DEVICE_AVAILABILITY_TOPIC, p["availability_topic"])

    def test_availability_payloads_set(self) -> None:
        p = self._payload()
        self.assertEqual("online", p["payload_available"])
        self.assertEqual("offline", p["payload_not_available"])

    def test_device_info_present(self) -> None:
        p = self._payload()
        self.assertIn("device", p)
        self.assertIn("homelab_analytics", p["device"]["identifiers"])

    def test_icon_present(self) -> None:
        p = self._payload()
        self.assertIn("icon", p)


class StateValueTests(unittest.TestCase):
    def _entity(self) -> dict:
        return _SYNTHETIC_ENTITIES[0]

    def test_none_value_returns_unavailable(self) -> None:
        entity = self._entity()
        value = _build_state_value(entity, {entity["value_key"]: None})
        self.assertEqual("unavailable", value)

    def test_missing_key_returns_unavailable(self) -> None:
        entity = self._entity()
        value = _build_state_value(entity, {})
        self.assertEqual("unavailable", value)

    def test_timestamp_string_returned_as_is(self) -> None:
        entity = self._entity()
        ts = "2026-03-21T10:05:23.441000+00:00"
        value = _build_state_value(entity, {entity["value_key"]: ts})
        self.assertEqual(ts, value)

    def test_value_stringified(self) -> None:
        entity = self._entity()
        value = _build_state_value(entity, {entity["value_key"]: 42})
        self.assertEqual("42", value)


if __name__ == "__main__":
    unittest.main()
