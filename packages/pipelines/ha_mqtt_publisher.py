"""Home Assistant MQTT publisher for bridge, policy, and contract-backed HA entities.

The publisher connects to an MQTT broker and periodically publishes computed
platform entities back into HA via MQTT discovery.  It runs as a long-lived
asyncio task alongside uvicorn (started/stopped via FastAPI lifespan).

Entities published:
    sensor.homelab_analytics_freshness          — WebSocket bridge health timestamp
    sensor.homelab_analytics_budget_status      — budget utilization verdict
    sensor.homelab_analytics_monthly_spend_rate — spending pace verdict
    sensor.homelab_analytics_bridge_health      — bridge freshness verdict
    sensor.homelab_analytics_approval_pending_count
                                              — number of pending approval proposals
    sensor.homelab_analytics_peak_tariff_active  — current tariff band state
    sensor.homelab_analytics_electricity_cost_forecast_today
                                              — today’s electricity cost estimate
    sensor.homelab_analytics_maintenance_due    — maintenance pressure indicator
    sensor.homelab_analytics_*                  — contract-backed publication summaries

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
from typing import Any, Callable, Sequence

from packages.pipelines.ha_mqtt_models import HaMqttEntityDefinition

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

_STATIC_ENTITIES: tuple[HaMqttEntityDefinition, ...] = (
    HaMqttEntityDefinition(
        object_id="homelab_analytics_freshness",
        name="Homelab Analytics Freshness",
        state_key="bridge_last_sync_at",
        icon="mdi:sync-circle",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_budget_status",
        name="Homelab Analytics Budget Status",
        state_key="policy_budget_status",
        icon="mdi:currency-usd",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_monthly_spend_rate",
        name="Homelab Analytics Monthly Spend Rate",
        state_key="policy_monthly_spend_rate",
        icon="mdi:chart-line",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_bridge_health",
        name="Homelab Analytics Bridge Health",
        state_key="policy_bridge_health",
        icon="mdi:lan-connect",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_approval_pending_count",
        name="Homelab Analytics Approval Pending Count",
        state_key="approval_pending_count",
        icon="mdi:shield-alert",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_approval_tracked_count",
        name="Homelab Analytics Approval Tracked Count",
        state_key="approval_tracked_count",
        icon="mdi:shield-account",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_peak_tariff_active",
        name="Homelab Analytics Peak Tariff Active",
        state_key="peak_tariff_active",
        icon="mdi:flash",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_electricity_cost_forecast_today",
        name="Homelab Analytics Electricity Cost Forecast Today",
        state_key="electricity_cost_forecast_today",
        icon="mdi:currency-eur",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_maintenance_due",
        name="Homelab Analytics Maintenance Due",
        state_key="maintenance_due",
        icon="mdi:wrench",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_maintenance_issue_count",
        name="Homelab Analytics Maintenance Issue Count",
        state_key="maintenance_issue_count",
        icon="mdi:wrench-clock",
    ),
    HaMqttEntityDefinition(
        object_id="homelab_analytics_contract_renewal_due_count",
        name="Homelab Analytics Contract Renewal Due Count",
        state_key="contract_renewal_due_count",
        icon="mdi:calendar-alert",
    ),
)

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


def _build_discovery_payload(entity: HaMqttEntityDefinition) -> str:
    """Build the MQTT discovery config JSON for one entity."""
    object_id = entity.object_id
    payload: dict[str, Any] = {
        "name": entity.name,
        "unique_id": object_id,
        "state_topic": _state_topic(object_id),
        "availability_topic": _DEVICE_AVAILABILITY_TOPIC,
        "payload_available": "online",
        "payload_not_available": "offline",
        "device": _DEVICE_INFO,
    }
    if entity.icon:
        payload["icon"] = entity.icon
    if entity.device_class:
        payload["device_class"] = entity.device_class
    if entity.unit_of_measurement:
        payload["unit_of_measurement"] = entity.unit_of_measurement
    return json.dumps(payload)


def _build_state_value(
    entity: HaMqttEntityDefinition,
    platform_state: dict[str, Any],
) -> str:
    """Extract the state string to publish for one entity."""
    value = platform_state.get(entity.state_key)
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
        action_dispatcher: Any | None = None,
        entities: Sequence[HaMqttEntityDefinition] | None = None,
    ) -> None:
        self._fetch_fn = fetch_fn
        self._action_dispatcher = action_dispatcher
        self._entities = (
            _STATIC_ENTITIES
            if entities is None
            else (*_STATIC_ENTITIES, *tuple(entities))
        )
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
        publication_keys = sorted(
            {
                entity.publication_key
                for entity in self._entities
                if entity.publication_key is not None
            }
        )
        return {
            "connected": self.connected,
            "last_publish_at": self.last_publish_at,
            "publish_count": self.publish_count,
            "entity_count": len(self._entities),
            "static_entity_count": len(
                [entity for entity in self._entities if entity.publication_key is None]
            ),
            "contract_entity_count": len(
                [entity for entity in self._entities if entity.publication_key is not None]
            ),
            "publication_keys": publication_keys,
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
        """Send retained discovery config for all configured entities."""
        for entity in self._entities:
            topic = _discovery_topic(entity.object_id)
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

        for entity in self._entities:
            topic = _state_topic(entity.object_id)
            value = _build_state_value(entity, platform_state)
            await client.publish(topic, payload=value, qos=1)
            logger.debug("MQTT state published: %s = %s", topic, value)

        self.last_publish_at = datetime.now(UTC).isoformat()
        self.publish_count += 1

        # Phase 5: dispatch outbound actions after state publish.
        if self._action_dispatcher is not None:
            try:
                await self._action_dispatcher.dispatch_from_cache()
            except Exception as exc:
                logger.warning("Action dispatch error", extra={"error": str(exc)})

    async def _publish_availability(self, client: Any, payload: str) -> None:
        """Publish availability payload ("online" or "offline") for the device."""
        await client.publish(
            _DEVICE_AVAILABILITY_TOPIC, payload=payload, retain=True, qos=1
        )
