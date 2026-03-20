# Home Assistant Integration Hub

## Purpose

This document specifies the architecture of the Home Assistant integration hub — the technical bridge between Home Assistant and the household operating platform. It defines the six layers of the hub, the protocol choices at each layer, the entity normalization contract, the bidirectional command fabric, the synthetic entity publication model, and the resilience model.

## Design goals

- HA is the edge runtime and actuation layer; the platform is the semantic and planning core
- Bidirectional: HA feeds state and events to the platform; the platform feeds outputs and commands back to HA
- Protocol-first: use standard HA APIs (WebSocket, REST, MQTT) rather than custom agents or HA-resident code
- Normalization happens at the bridge layer, not inside HA or inside the platform core
- Synthetic entities allow platform outputs to be consumed in HA dashboards, automations, and voice surfaces without HA needing to understand the platform's data model
- Resilient by default: bridge failures should not prevent HA from operating; platform degradation should be transparent to the operator

## Six-layer architecture

### Layer 1 — Device and ecosystem ingress

This layer encompasses all sources that flow state into HA. HA-native integrations are the primary ingress surface: they absorb direct device protocols (Zigbee, Z-Wave, Matter, Thread, Wi-Fi), vendor cloud integrations where no local path exists, energy and tariff data feeds, media and presence systems, building systems including HVAC, security, and access control, and consumer ecosystem state where it is useful for presence or multi-admin control. The bridge treats all of this as HA state — it does not reach behind HA to consume raw device protocols independently.

### Layer 2 — Entity normalization bridge

The normalization bridge is a dedicated component that translates HA objects into canonical platform concepts. This is the layer where entity ID instability, duplicate devices across integrations, vendor-specific naming, device-to-asset mapping, area and floor and location semantics, unit normalization, and quality and confidence metadata are all resolved. No normalization logic belongs inside HA itself, and no raw HA entity references should leak into the platform core.

Canonical concept mapping:

| HA concept | Canonical platform concept |
|---|---|
| Entity (sensor, switch, binary_sensor, etc.) | Sensor, load, actuator, or meter depending on entity class |
| Device | Asset or component of an asset |
| Area / floor | Location with spatial context |
| Integration domain | Source system or vendor |
| Energy dashboard entry | Metered load or generation source |
| HA person / user | Household member |
| HA helper (input_boolean, input_number, etc.) | Policy state or configuration surface |

Bridge responsibilities:

- resolve entity ID changes between HA versions or device re-pairings
- deduplicate devices that appear across multiple integrations
- apply device-to-asset mapping rules from the platform asset register
- normalize units of measure to platform-canonical forms
- attach confidence and quality metadata to normalized state
- publish normalized state events to the platform event bus

### Layer 3 — Event and history bus

The bridge uses three HA communication paths, each with a distinct role.

**WebSocket API** is the primary path for live household state. The bridge subscribes to state-change events and receives real-time entity updates as they occur. This is the main feed for operational telemetry flowing from HA into the platform.

**REST API** is used for targeted queries, bulk historical state reads, and service call dispatch. When the bridge needs to read historical state for a date range, verify entity configuration, or send an action command to HA, it uses the REST API.

**MQTT** is used for dynamic entity discovery and decoupled publishing. MQTT discovery is the preferred mechanism for registering platform-synthesized entities into HA. The bridge publishes discovery configuration payloads to the HA-standard discovery topic prefix and maintains state update topics separately from the discovery config. Where HA's MQTT discovery model simplifies integration of platform-derived devices, MQTT is preferred over REST state writes.

The bridge maintains a local entity state cache synchronized from the WebSocket subscription. REST is used to backfill the cache on startup and to recover missed events after reconnection. MQTT discovery manages synthetic entity registration.

### Layer 4 — Semantic and planning core

homelab-analytics owns this layer entirely. It includes the canonical household graph, cross-domain joins, the historical data warehouse, the scenario engine, the policy engine, the trust and explainability layer, and the pack model. HA has no visibility into this layer. It receives normalized inputs from Layer 3 and receives dispatched outputs from Layer 5. It does not participate in planning or policy logic, and the bridge does not expose platform internals to HA.

### Layer 5 — Action and approval layer

Platform outputs flow back to HA through this layer. The bridge translates platform action payloads into HA-native calls:

- service calls (turn on device, activate scene, set climate target, send notification)
- script or scene triggers
- notification payloads to HA notify services
- helper value writes (input_boolean, input_number, input_select)
- synthetic entity state updates via MQTT state topic or REST state POST
- maintenance task creation via HA to-do integrations
- recommended-action cards via persistent notifications or custom dashboard cards

Action safety model:

| Action class | Trigger | Approval |
|---|---|---|
| Recommendation | Platform output, no side effect | None required |
| Alert | Notification only, no device change | None required |
| Automated action | Device or service state change | Policy-level authorization |
| Approval-gated action | Device or service state change | Explicit operator approval in HA or platform UI |

Automated and approval-gated actions must be traceable to the policy or publication state that triggered them. The bridge records the action dispatch, the HA service call made, and the result. This is part of the trust and governance layer's audit contract.

### Layer 6 — External ecosystem federation

This layer handles selective outward exposure from the hub: Matter multi-admin for supported devices, notification channels (push, email, messaging integrations), voice surfaces (local HA voice pipelines, Siri via HomeKit, Google Assistant via Home Assistant), cloud products with legitimate household value, and partner apps or additional dashboards.

The principle is to federate capabilities outward through standards rather than building per-ecosystem connectors. Matter multi-admin is the preferred model for shared device access across consumer ecosystems. Vendor-specific federation is only justified when Matter is not available and the integration value is high enough to warrant the ongoing maintenance cost of a proprietary adapter.

## Synthetic entity model

Platform publications can be materialized as HA entities so they appear in dashboards, automations, and voice responses without requiring custom HA component code. The bridge publishes these as standard HA entity types with well-defined state values and attribute payloads.

| Publication type | HA entity type | Example |
|---|---|---|
| Budget state indicator | `sensor` | `sensor.monthly_budget_status` → on_track / warning / over |
| Cost forecast | `sensor` | `sensor.electricity_cost_forecast_today` |
| Tariff band | `binary_sensor` | `binary_sensor.peak_tariff_active` |
| Maintenance flag | `binary_sensor` | `binary_sensor.dishwasher_maintenance_due` |
| Policy state | `input_boolean` | `input_boolean.battery_discharge_policy_active` |
| Recommended action | `sensor` + attribute payload | `sensor.recommended_action_ev_charging` |
| Platform health | `sensor` | `sensor.homelab_analytics_freshness` |

MQTT discovery is the preferred mechanism for synthetic entities. The bridge publishes a discovery configuration payload to `homeassistant/<component>/<object_id>/config` and sends state updates to the matching state topic. HA picks up the entity without requiring any modification to the HA instance. When an entity is retired or the bridge is reset, the bridge sends a discovery payload with an empty config to deregister the entity.

State values for synthetic sensors should carry their publication freshness timestamp and source lineage in the entity attributes. A stale platform publication should cause the corresponding synthetic entity to become unavailable rather than holding a stale value, so HA automations and dashboards reflect the actual confidence of the underlying data.

## Resilience model

The bridge should fail gracefully in all directions.

**HA WebSocket disconnect**: reconnect with exponential backoff. On reconnection, replay missed state-change events from the HA history API for the gap period if the outage was short. For longer gaps, perform a full entity-state resync via REST before resuming the WebSocket subscription.

**Platform unavailability**: HA continues to operate normally without the bridge. Existing synthetic entity states go stale and should transition to unavailable rather than retaining stale values. No HA automation or user-facing function should depend on the bridge being available for safety-critical operation.

**Bridge restart**: on startup, re-subscribe to the HA state stream, re-sync the entity registry, and re-publish synthetic entity discovery configurations. The bridge should be stateless enough to restart cleanly without manual intervention.

**MQTT broker unavailability**: fall back to REST state writes for synthetic entity updates where the HA deployment accepts REST state ingestion. Log the fallback so operators can diagnose MQTT connectivity separately from bridge health.

**Platform-side**: bridge errors and feed staleness should surface as platform health indicators. Publications that depend on HA state feeds should carry staleness flags when the bridge has not delivered a fresh update within the expected interval. The `sensor.homelab_analytics_freshness` synthetic entity provides a visible signal in HA when the bridge connection is degraded.

## Relationship to platform layers

| Platform architectural layer | Integration hub role |
|---|---|
| Data platform architecture — source ingestion | Layer 1 (ingress) and Layer 3 (event bus) are the HA source connector |
| Data platform architecture — transformation | Layer 2 (normalization bridge) feeds into canonical transformation |
| Policy and automation layer (Stage 5) | Layer 5 (action and approval) is the dispatch path for policy actions |
| Multi-renderer delivery layer (Stage 6) | Layer 5 synthetic entities are the HA renderer adapter |
| Trust and governance layer (Stage 8) | Bridge events carry source, timestamp, and quality metadata into the lineage model |
