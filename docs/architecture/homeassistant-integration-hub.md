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
Approval-gated policy outputs are surfaced as explicit approval notifications so the operator can approve or dismiss the actuation path without losing lineage back to the originating policy result.
Phase 6 tracks those approval-gated outputs as concrete proposal records in the action layer so the approval state can be updated independently of the original policy verdict. When a proposal is approved or dismissed, the platform clears the pending HA notification and writes a resolution record into the action log. Approval proposals may also carry an optional HA service target in metadata, allowing the dispatcher to execute a real service call before clearing the gate and preserving the audit trail for both the actuation and the approval boundary.
One concrete pattern is a HA helper entity that represents an operator request, such as `input_boolean.hla_kitchen_light_request`; when that helper is on, the platform can emit an approval-gated proposal with a service target like `light.turn_on`.
The bridge also publishes approval queue state back into HA as synthetic sensors, such as a pending-approval count, so operators can see unresolved approval work in dashboards without opening the API.
The homelab and retro operations views also expose the pending approval proposals directly, with approve and dismiss controls that call the platform approval endpoints and return the operator to the same view with a status notice.
Proposal drafts are auditable records, not execution shortcuts: a draft stores its source kind, source key, and creator metadata before it can be approved or dismissed, and the approval write path is separately permission-gated from the read path.

### Layer 6 — External ecosystem federation

This layer handles selective outward exposure from the hub: Matter multi-admin for supported devices, notification channels (push, email, messaging integrations), voice surfaces (local HA voice pipelines, Siri via HomeKit, Google Assistant via Home Assistant), cloud products with legitimate household value, and partner apps or additional dashboards.

The principle is to federate capabilities outward through standards rather than building per-ecosystem connectors. Matter multi-admin is the preferred model for shared device access across consumer ecosystems. Vendor-specific federation is only justified when Matter is not available and the integration value is high enough to warrant the ongoing maintenance cost of a proprietary adapter.

## Synthetic entity model

Platform publications can be materialized as HA entities so they appear in dashboards, automations, and voice responses without requiring custom HA component code. The bridge publishes these as standard HA entity types with well-defined state values and attribute payloads.

| Publication type | HA entity type | Example |
|---|---|---|
| Budget state indicator | `sensor` | `sensor.monthly_budget_status` → on_track / warning / over |
| Cost forecast | `sensor` | `sensor.electricity_cost_forecast_today` |
| Tariff band | `sensor` | `sensor.homelab_analytics_peak_tariff_active` |
| Maintenance flag | `sensor` | `sensor.homelab_analytics_maintenance_due` |
| Maintenance pressure count | `sensor` | `sensor.homelab_analytics_maintenance_issue_count` |
| Contract renewal count | `sensor` | `sensor.homelab_analytics_contract_renewal_due_count` |
| Policy state | `input_boolean` | `input_boolean.battery_discharge_policy_active` |
| Recommended action | `sensor` + attribute payload | `sensor.recommended_action_ev_charging` |
| Platform health | `sensor` | `sensor.homelab_analytics_freshness` |
| Approval queue | `sensor` | `sensor.homelab_analytics_approval_pending_count` |

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
| Multi-renderer delivery layer (Stage 7) | Layer 5 synthetic entities are the HA renderer adapter |
| Trust and governance layer (Stage 9) | Bridge events carry source, timestamp, and quality metadata into the lineage model |

## Relationship to integration adapter layer

The HA integration hub is the reference implementation for the generic integration adapter model defined in Stage 6 of the platform roadmap. The six-layer hub architecture maps to three adapter contracts (ingest, publish, action) that future integration surfaces will implement independently.

This means HA-specific protocol choices — WebSocket subscription format, MQTT discovery envelope, REST service call schema — are implementation details of the HA adapter, not platform-wide assumptions. New adapters (Prometheus scrape, generic MQTT, Kubernetes API) implement the same adapter contracts with their own protocol logic.

In the codebase, API startup assembly now delegates the HA-specific runtime wiring to `apps/api/ha_startup.py`, keeping `apps/api/main.py` focused on orchestration and shared composition-root rules.

The shared container-backed service builders now live in `apps/runtime_support.py` so API and worker entrypoints use the same helper surface for account, transformation, reporting, registry, and lazy-runtime assembly.

The platform-facing HA health endpoints use typed status models for bridge and action surfaces so the adapter boundary stays explicit rather than leaking raw transport dictionaries into the API. That runtime snapshot is distinct from the static adapter manifest described in `docs/architecture/integration-adapters.md`.

Those typed status models share one health vocabulary: `enabled` for participation, `connected` for live transport, `last_*_at` for the newest successful sync or dispatch, and role-specific counters for reconnects, publishes, dispatches, and approval tracking. The field names vary by surface, but the reporting shape stays coherent across bridge, MQTT, and action endpoints.

See `docs/architecture/integration-adapters.md` for the Stage 6 adapter contract packet and the HA-as-reference mapping.
