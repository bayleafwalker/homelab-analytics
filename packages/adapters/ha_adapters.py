"""Home Assistant adapter wrappers — Stage 6 reference implementation.

These thin wrappers position the existing HA workers as conforming implementations
of the generic adapter protocols defined in ``packages.adapters.contracts``.

Design rules
------------
- Each wrapper holds a reference to the existing worker; it does NOT duplicate
  its behaviour or own its lifecycle.
- HA-specific protocol details (WebSocket subscription format, MQTT discovery
  envelopes, REST service-call payloads) stay in the wrapped worker classes.
- ``get_status()`` on each wrapper returns a typed ``AdapterRuntimeStatus``
  derived from the worker's existing status dict.

Layer mapping (from ``docs/architecture/integration-adapters.md``)
------------------------------------------------------------------
| HA hub layer                     | Adapter role          |
|----------------------------------|-----------------------|
| Layer 2 — Entity normalisation   | HaIngestAdapter       |
| Layer 3 — Event / history bus    | HaIngestAdapter       |
| Layer 5 — Action / approval      | HaActionAdapter       |
| Layer 6 — External federation    | HaMqttPublishAdapter  |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from packages.adapters.contracts import (
    AdapterDirection,
    AdapterManifest,
    AdapterRuntimeStatus,
)

if TYPE_CHECKING:
    from packages.pipelines.ha_action_dispatcher import HaActionDispatcher
    from packages.pipelines.ha_bridge import HaBridgeWorker
    from packages.pipelines.ha_mqtt_publisher import HaMqttPublisher


# ---------------------------------------------------------------------------
# Manifests
# ---------------------------------------------------------------------------

HA_INGEST_MANIFEST = AdapterManifest(
    adapter_key="ha_ingest",
    display_name="Home Assistant — Ingest (WebSocket bridge)",
    version="1.0",
    supported_directions=(AdapterDirection.INGEST,),
    supported_entity_classes=("ha_state",),
    credential_requirements=("ha_url", "ha_token"),
    health_check_contract=(
        "connected=True when WebSocket subscription is active; "
        "last_activity_at reflects the most recent ingested state batch"
    ),
    target_capabilities=("websocket_subscription", "history_replay"),
)

HA_PUBLISH_MANIFEST = AdapterManifest(
    adapter_key="ha_mqtt_publish",
    display_name="Home Assistant — Publish (MQTT synthetic entities)",
    version="1.0",
    supported_directions=(AdapterDirection.PUBLISH,),
    supported_entity_classes=("ha_sensor", "ha_binary_sensor"),
    credential_requirements=("ha_mqtt_broker_url",),
    health_check_contract=(
        "connected=True when MQTT broker session is active; "
        "last_activity_at reflects the most recent publish cycle"
    ),
    target_capabilities=("mqtt_discovery", "lwt_availability"),
)

HA_ACTION_MANIFEST = AdapterManifest(
    adapter_key="ha_action",
    display_name="Home Assistant — Action (persistent notification / service call)",
    version="1.0",
    supported_directions=(AdapterDirection.ACTION,),
    supported_entity_classes=("ha_service_call", "ha_persistent_notification"),
    credential_requirements=("ha_url", "ha_token"),
    health_check_contract=(
        "enabled=True when ha_url and ha_token are configured; "
        "last_activity_at reflects the most recent dispatch"
    ),
    target_capabilities=("approval_gating", "persistent_notification"),
)


# ---------------------------------------------------------------------------
# HaIngestAdapter
# ---------------------------------------------------------------------------


class HaIngestAdapter:
    """IngestAdapter wrapping :class:`~packages.pipelines.ha_bridge.HaBridgeWorker`.

    Conforms to the ``IngestAdapter`` protocol from ``packages.adapters.contracts``.
    """

    manifest: AdapterManifest = HA_INGEST_MANIFEST

    def __init__(self, worker: HaBridgeWorker) -> None:
        self._worker = worker

    def get_status(self) -> AdapterRuntimeStatus:
        raw: dict[str, Any] = self._worker.get_status()
        return AdapterRuntimeStatus(
            enabled=True,
            connected=raw.get("connected", False),
            last_activity_at=raw.get("last_sync_at"),
            error_count=0,
            extra={"reconnect_count": raw.get("reconnect_count", 0)},
        )


# ---------------------------------------------------------------------------
# HaMqttPublishAdapter
# ---------------------------------------------------------------------------


class HaMqttPublishAdapter:
    """PublishAdapter wrapping :class:`~packages.pipelines.ha_mqtt_publisher.HaMqttPublisher`.

    Conforms to the ``PublishAdapter`` protocol from ``packages.adapters.contracts``.
    """

    manifest: AdapterManifest = HA_PUBLISH_MANIFEST

    def __init__(self, worker: HaMqttPublisher) -> None:
        self._worker = worker

    def get_status(self) -> AdapterRuntimeStatus:
        raw: dict[str, Any] = self._worker.get_status()
        return AdapterRuntimeStatus(
            enabled=True,
            connected=raw.get("connected", False),
            last_activity_at=raw.get("last_publish_at"),
            error_count=0,
            extra={
                "publish_count": raw.get("publish_count", 0),
                "entity_count": raw.get("entity_count", 0),
                "publication_keys": raw.get("publication_keys", []),
            },
        )


# ---------------------------------------------------------------------------
# HaActionAdapter
# ---------------------------------------------------------------------------


class HaActionAdapter:
    """ActionAdapter wrapping :class:`~packages.pipelines.ha_action_dispatcher.HaActionDispatcher`.

    Conforms to the ``ActionAdapter`` protocol from ``packages.adapters.contracts``.
    """

    manifest: AdapterManifest = HA_ACTION_MANIFEST

    def __init__(self, worker: HaActionDispatcher) -> None:
        self._worker = worker

    def get_status(self) -> AdapterRuntimeStatus:
        raw: dict[str, Any] = self._worker.get_status()
        return AdapterRuntimeStatus(
            enabled=raw.get("enabled", True),
            connected=raw.get("connected", True),
            last_activity_at=raw.get("last_dispatch_at"),
            error_count=raw.get("error_count", 0),
            extra={
                "dispatch_count": raw.get("dispatch_count", 0),
                "action_log_size": raw.get("action_log_size", 0),
                "tracked_policies": raw.get("tracked_policies", 0),
                "approval_pending_count": raw.get("approval_pending_count", 0),
                "approval_approved_count": raw.get("approval_approved_count", 0),
                "approval_dismissed_count": raw.get("approval_dismissed_count", 0),
            },
        )
