"""Home Assistant MQTT publisher — Phase 3/4 synthetic entity publication.

The publisher connects to an MQTT broker and periodically publishes computed
platform entities back into HA via MQTT discovery.  It runs as a long-lived
asyncio task alongside uvicorn (started/stopped via FastAPI lifespan).

Entities published:
    sensor.homelab_analytics_freshness         — WebSocket bridge health timestamp
    sensor.homelab_analytics_budget_status     — budget utilization verdict
    sensor.homelab_analytics_monthly_spend_rate — spending pace verdict
    sensor.homelab_analytics_bridge_health     — bridge freshness verdict

Discovery protocol:
    homeassistant/sensor/<object_id>/config       → JSON config (retain=True)
    homelab_analytics/sensor/<object_id>/state    → current state value
    homelab_analytics/availability                → device online/offline (LWT)

Configuration (via AppSettings):
    HOMELAB_ANALYTICS_HA_MQTT_BROKER_URL  — e.g. ``mqtt://mosquitto.local:1883``
    HOMELAB_ANALYTICS_HA_MQTT_USERNAME    — MQTT username (optional)
    HOMELAB_ANALYTICS_HA_MQTT_PASSWORD    — MQTT password (optional)
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any, Callable

logger = logging.getLogger("homelab_analytics.ha_mqtt_publisher")

_BACKOFF_BASE: float = 1.0
_BACKOFF_MAX: float = 60.0
_PUBLISH_INTERVAL: int = 30  # seconds between state refreshes

_DISCOVERY_PREFIX = "homeassistant"
_STATE_PREFIX = "homelab_analytics"
_DEVICE_AVAILABILITY_TOPIC = f"{_STATE_PREFIX}/availability"

_DEVICE_INFO: dict[str, Any] = {
    "identifiers": ["homelab_analytics"],
    "name": "Homelab Analytics",
    "manufacturer": "homelab-analytics",
}

# Synthetic entity definitions.
# value_key: key in the platform_state dict returned by fetch_fn.
_SYNTHETIC_ENTITIES: list[dict[str, Any]] = [
    {
        "object_id": "homelab_analytics_freshness",
        "name": "Homelab Analytics Freshness",
        "icon": "mdi:sync-circle",
        "value_key": "bridge_last_sync_at",
    },
    {
        "object_id": "homelab_analytics_budget_status",
        "name": "Homelab Analytics Budget Status",
        "icon": "mdi:currency-usd",
        "value_key": "policy_budget_status",
    },
    {
        "object_id": "homelab_analytics_monthly_spend_rate",
        "name": "Homelab Analytics Monthly Spend Rate",
        "icon": "mdi:chart-line",
        "value_key": "policy_monthly_spend_rate",
    },
    {
        "object_id": "homelab_analytics_bridge_health",
        "name": "Homelab Analytics Bridge Health",
        "icon": "mdi:lan-connect",
        "value_key": "policy_bridge_health",
    },
]

# Type alias for the platform-state fetch callable.
FetchFn = Callable[[], dict[str, Any]]


def _parse_broker_url(url: str) -> tuple[str, int]:
    """Parse ``mqtt://host:port`` (or ``host:port`` or ``host``) into (host, port)."""
    url = url.strip().rstrip("/")
    if "://" in url:
        url = url.split("://", 1)[1]
    if ":" in url:
        host, port_str = url.rsplit(":", 1)
        try:
            return host, int(port_str)
        except ValueError:
            pass
    return url, 1883


def _discovery_topic(object_id: str) -> str:
    return f"{_DISCOVERY_PREFIX}/sensor/{object_id}/config"


def _state_topic(object_id: str) -> str:
    return f"{_STATE_PREFIX}/sensor/{object_id}/state"


def _build_discovery_payload(entity: dict[str, Any]) -> str:
    """Build the MQTT discovery config JSON for one synthetic entity."""
    object_id = entity["object_id"]
    payload: dict[str, Any] = {
        "name": entity["name"],
        "unique_id": object_id,
        "state_topic": _state_topic(object_id),
        "availability_topic": _DEVICE_AVAILABILITY_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": _DEVICE_INFO,
    }
    if entity.get("icon"):
        payload["icon"] = entity["icon"]
    if entity.get("device_class"):
        payload["device_class"] = entity["device_class"]
    if entity.get("unit_of_measurement"):
        payload["unit_of_measurement"] = entity["unit_of_measurement"]
    return json.dumps(payload)


def _build_state_value(entity: dict[str, Any], platform_state: dict[str, Any]) -> str:
    """Extract the state string to publish for one entity."""
    value = platform_state.get(entity["value_key"])
    if value is None:
        return "unavailable"
    return str(value)


class HaMqttPublisher:
    """Long-running MQTT publisher worker.

    Parameters
    ----------
    fetch_fn:
        Callable with no arguments that returns a dict of platform state values.
        Expected keys: ``bridge_last_sync_at`` (str | None), ``bridge_connected`` (bool).
    broker_url:
        MQTT broker URL, e.g. ``mqtt://mosquitto.local:1883``.
    username:
        Optional MQTT username.
    password:
        Optional MQTT password.
    """

    def __init__(
        self,
        fetch_fn: FetchFn,
        *,
        broker_url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._broker_host, self._broker_port = _parse_broker_url(broker_url)
        self._username = username
        self._password = password

        self._running: bool = False
        self._task: asyncio.Task | None = None

        # Status fields — read by get_status()
        self.connected: bool = False
        self.last_publish_at: str | None = None
        self.publish_count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Schedule the publisher loop as an asyncio background task."""
        self._running = True
        self._task = asyncio.create_task(self._run(), name="ha_mqtt_publisher")
        logger.info(
            "HA MQTT publisher started (broker: %s:%d)",
            self._broker_host,
            self._broker_port,
        )

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.connected = False
        logger.info("HA MQTT publisher stopped")

    def get_status(self) -> dict[str, Any]:
        """Return current publisher health snapshot."""
        return {
            "connected": self.connected,
            "last_publish_at": self.last_publish_at,
            "publish_count": self.publish_count,
            "entity_count": len(_SYNTHETIC_ENTITIES),
        }

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Outer reconnect loop with exponential backoff."""
        backoff = _BACKOFF_BASE
        while self._running:
            try:
                await self._connect_and_publish()
                backoff = _BACKOFF_BASE
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "HA MQTT publisher connection lost",
                    extra={"error": str(exc), "backoff_seconds": backoff},
                )
            finally:
                self.connected = False

            if not self._running:
                break

            logger.info("HA MQTT publisher reconnecting in %.1f s", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)

    async def _connect_and_publish(self) -> None:
        """Connect to broker, publish discovery, then loop publishing states."""
        try:
            import aiomqtt
        except ImportError as exc:
            raise RuntimeError(
                "aiomqtt is required for MQTT publishing. "
                "Install it with: pip install 'aiomqtt>=2.0'"
            ) from exc

        kwargs: dict[str, Any] = {
            "hostname": self._broker_host,
            "port": self._broker_port,
            "will": aiomqtt.Will(
                topic=_DEVICE_AVAILABILITY_TOPIC,
                payload="offline",
                retain=True,
                qos=1,
            ),
        }
        if self._username is not None:
            kwargs["username"] = self._username
        if self._password is not None:
            kwargs["password"] = self._password

        async with aiomqtt.Client(**kwargs) as client:
            self.connected = True
            logger.info(
                "HA MQTT publisher connected to %s:%d",
                self._broker_host,
                self._broker_port,
            )
            await self._publish_discovery(client)
            await self._publish_availability(client, "online")
            while self._running:
                await self._publish_states(client)
                await asyncio.sleep(_PUBLISH_INTERVAL)

    async def _publish_discovery(self, client: Any) -> None:
        """Send retained discovery config for all synthetic entities."""
        for entity in _SYNTHETIC_ENTITIES:
            topic = _discovery_topic(entity["object_id"])
            payload = _build_discovery_payload(entity)
            await client.publish(topic, payload=payload, retain=True, qos=1)
            logger.debug("MQTT discovery published: %s", topic)

    async def _publish_states(self, client: Any) -> None:
        """Fetch platform state and publish state topics for all entities."""
        try:
            platform_state = self._fetch_fn()
        except Exception as exc:
            logger.warning("MQTT state fetch error", extra={"error": str(exc)})
            return

        for entity in _SYNTHETIC_ENTITIES:
            topic = _state_topic(entity["object_id"])
            value = _build_state_value(entity, platform_state)
            await client.publish(topic, payload=value, qos=1)
            logger.debug("MQTT state published: %s = %s", topic, value)

        self.last_publish_at = datetime.now(UTC).isoformat()
        self.publish_count += 1

    async def _publish_availability(self, client: Any, payload: str) -> None:
        """Publish availability payload ("online" or "offline") for the device."""
        await client.publish(
            _DEVICE_AVAILABILITY_TOPIC, payload=payload, retain=True, qos=1
        )
