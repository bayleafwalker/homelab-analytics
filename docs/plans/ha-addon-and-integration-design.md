# Home Assistant Add-on and Integration Design Plan

## Purpose

This document is a high-level design plan for the two HA-facing components of the homelab-analytics integration hub. It is intended for later decomposition into architecture docs, implementation tasks, and packaging work.

References:

- HA product boundary: `docs/product/homeassistant-and-smart-home-hub.md`
- Integration hub architecture: `docs/architecture/homeassistant-integration-hub.md`
- Roadmap stage: `docs/plans/household-operating-platform-roadmap.md` — Stage 5 (policy, automation, and action engine)

---

## 1. Purpose and boundary

### Why add-on plus integration, not one package

A single HA package cannot cleanly express bidirectional responsibilities with different trust levels, different update patterns, and different failure modes.

The outbound bridge (HA → platform) has write-only access to the platform's ingest API. It runs as a persistent process, needs buffering when the platform is unavailable, and concerns itself with HA internals: entities, devices, areas, statistics, and event streams. This is infrastructure work. It is not domain-aware. It does not need to understand finance or asset models.

The inbound integration (platform → HA) has read-only access to platform publications and limited write access to action endpoints. It runs as a standard HA integration with a DataUpdateCoordinator, creates named entities, and surfaces platform outputs in a form HA understands. This is presentation work. It is domain-aware. It does not need to understand HA's internal data model.

Merging them creates a component that conflates push, pull, buffering, entity registration, diagnostics, and semantic modeling in one place. Keeping them separate gives each a single clear responsibility and lets them fail independently.

### What belongs in Home Assistant

- Device and protocol integration (Zigbee, Z-Wave, Matter, Thread, vendor cloud adapters)
- Real-time entity state, occupancy, house-mode modeling
- Automations, scripts, scenes, and local control logic
- Family dashboards and operational views
- Voice assistant pipelines
- Notification delivery to household members
- Energy monitoring and in-day visualization
- Actuating device commands in response to external triggers

### What belongs in homelab-analytics

- Canonical cross-domain household model (finance, utilities, assets, contracts, loans, homelab)
- Long-horizon history and publication-grade marts with explicit lineage
- Budget, variance, and planning state
- Scenario simulation and what-if modeling
- Policy evaluation and recommendation logic
- Trust, lineage, and confidence indicators across all domains
- Multi-surface publishing so the same semantic outputs reach HA, the web UI, API clients, and agent surfaces
- Pack ecosystem capabilities that extend the semantic and product layer

### Why the core intelligence stays in homelab-analytics

A Home Assistant add-on or integration runs inside the HA runtime, operates on HA entities, and is constrained to what HA's data model and APIs expose. HA does not model financial transactions, loan amortization, contract prices, cross-domain cost attribution, or subscription lifecycle. Its statistics layer retains operational telemetry at hourly granularity; it does not hold publication-grade marts with transformation lineage, planning targets, scenario assumptions, or confidence metadata.

Moving planning, simulation, or policy logic into a HA add-on would mean building a second data warehouse inside HA's storage model, duplicating canonical dimensions, and accepting HA's restart-safe storage constraints as the foundation for household financial state. That is the wrong trade-off. The platform exists because those capabilities require a different runtime, a different storage model, and a different lifecycle.

---

## 2. Target architecture

### Component diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      Home Assistant instance                      │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  HA Core                                                  │    │
│  │  entities / devices / areas / automations / dashboards /  │    │
│  │  voice / energy / notifications                           │    │
│  └─────────────────────┬────────────────────▲───────────────┘    │
│                         │ REST / WebSocket /  │ entity state /     │
│                         │ Supervisor API      │ service calls /    │
│                         │                     │ events             │
│  ┌──────────────────────▼──────┐   ┌──────────┴──────────────┐   │
│  │  HA add-on                  │   │  HA integration          │   │
│  │  outbound bridge            │   │  inbound semantic surface│   │
│  │                             │   │                          │   │
│  │  - entity/device/area meta  │   │  - sensor entities       │   │
│  │  - filtered state export    │   │  - binary sensor entities│   │
│  │  - statistics export        │   │  - select entities       │   │
│  │  - event stream             │   │  - number entities       │   │
│  │  - retry/buffer queue       │   │  - button entities       │   │
│  │  - backfill trigger         │   │  - diagnostics platform  │   │
│  │  - diagnostics / health UI  │   │  - config / options flow │   │
│  └─────────────┬───────────────┘   └──────────┬──────────────┘   │
│                │                               │                   │
└────────────────┼───────────────────────────────┼───────────────────┘
                 │                               │
                 │ push (HTTP batch)             │ poll (HTTP) /
                 │ POST /api/ingest/ha-bridge/*  │ webhook (push alerts)
                 │                               │ GET /api/publications/ha/*
                 │                               │ POST /api/actions/*
                 ▼                               │
┌──────────────────────────────────────────────────────────────────┐
│                      homelab-analytics                            │
│                                                                    │
│  ┌──────────────────┐  ┌───────────────────┐  ┌───────────────┐ │
│  │  Ingest API      │  │  Canonical model   │  │  Publication  │ │
│  │  HA bridge       ├─►│  + planning        ├─►│  API          │ │
│  │  endpoint        │  │  + simulation      │  │  HA renderer  │ │
│  │                  │  │  + policy engine   │  │  endpoint     │ │
│  │  entity metadata │  │  + trust/lineage   │  │               │ │
│  │  states          │  │                    │  │  + Action API │ │
│  │  events          │  │  finance           │  │               │ │
│  │  statistics      │  │  utilities         │  │               │ │
│  └──────────────────┘  │  assets / loans    │  └───────────────┘ │
│                         │  homelab           │                    │
│                         └───────────────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### Data flows

| Flow | Direction | Transport | Content |
|---|---|---|---|
| Entity metadata export | Add-on → platform | HTTP POST (batch) | Device/entity/area registry snapshots |
| State export | Add-on → platform | HTTP POST (batch) | Filtered current and historical entity states |
| Statistics export | Add-on → platform | HTTP POST (batch) | Long-term hourly aggregates for metered entities |
| Event stream | Add-on → platform | HTTP POST (micro-batch) | Filtered state-change events |
| Publication poll | Integration → platform | HTTP GET | Domain publication data, freshness metadata |
| Alert push | Platform → integration | HTTP webhook | High-priority alerts and approval-needed events |
| Action dispatch | Integration → platform | HTTP POST | Approve, dismiss, refresh, scenario trigger, etc. |

### Control and action flows

When the platform evaluates a policy and produces a recommended action:

1. Platform publishes the recommendation to the HA renderer publication endpoint
2. Integration polls and surfaces it as a sensor entity with an attribute payload
3. For approval-needed actions, platform also fires a webhook to the integration
4. Integration creates or updates a persistent notification or an approval-needed binary sensor
5. Operator approves in HA (via button entity or service call)
6. Integration dispatches the approval action to the platform action API
7. Platform records the approval, dispatches the actuation instruction back via the HA service call API
8. For device-level actuation, the platform calls HA's REST API directly using a scoped service token held on the platform side

---

## 3. Add-on design

### Implementation form

The outbound bridge should be implemented as a **Home Assistant add-on** distributed via a custom add-on repository. This gives it:

- Supervisor-managed lifecycle (auto-start, watchdog, restart on crash)
- Access to the Supervisor API and a managed long-lived access token for HA API calls
- An ingress-hosted configuration and diagnostics UI
- Log access through the HA Supervisor UI
- Clean distribution and update path for homelab operators

For installations that do not run the Supervisor (HA Container, HA Core), a standalone Docker image with the same codebase and a manually provided long-lived access token should be available as a fallback. The functional code should be identical; only the entrypoint and token acquisition differ.

### Core responsibilities

- Maintain a continuous WebSocket subscription to HA state-change events and entity registry updates
- Export filtered entity, device, and area metadata to the platform on registry changes and on a configurable periodic schedule
- Export filtered current state on startup and after reconnection
- Micro-batch and push filtered state-change events to the platform ingest API
- Export long-term statistics for selected metered entities on a configurable schedule (default: daily)
- Buffer failed deliveries locally and replay them when the platform becomes available
- Expose a configuration and diagnostics surface through the add-on ingress UI
- Report bridge health status to the platform as a heartbeat so the platform's freshness indicators reflect bridge connectivity

### HA API usage

| API | Purpose |
|---|---|
| WebSocket — subscribe_events(state_changed) | Primary real-time event stream |
| WebSocket — config/entity_registry/list | Full entity registry snapshot on startup and on change |
| WebSocket — config/device_registry/list | Device registry snapshot |
| WebSocket — config/area_registry/list | Area registry snapshot |
| WebSocket — recorder/statistics_during_period | Long-term statistics export |
| REST GET /api/states | Bulk state snapshot on startup or backfill |
| REST GET /api/history/period/{timestamp} | Historical state backfill for a time range |
| Supervisor API /addons/self/info | Add-on metadata and health reporting |
| Supervisor API /addons/self/options | Configuration access |

The add-on should use the Supervisor-provided `SUPERVISOR_TOKEN` and the internal `homeassistant` hostname for all HA API calls. It should not require an operator-supplied HA access token in supervised deployments.

### Data export model

The bridge exports data in three categories with different frequencies and purposes:

**Registry snapshots** (startup, on registry change, periodic — configurable, default: every 6 hours):
- Entity registry: `entity_id`, `unique_id`, `entity_registry_id`, `device_id`, `area_id`, `platform`, `domain`, `device_class`, `unit_of_measurement`, `state_class`, `disabled_by`, labels
- Device registry: `device_registry_id`, `name`, `manufacturer`, `model`, `area_id`, `integration`, `entry_type`
- Area registry: `area_id`, `name`, `floor_id`

Registry snapshots are how the platform maintains its canonical ID map. The `entity_registry_id` and `device_registry_id` are the stable HA-side identifiers the platform should use for canonical mapping — not `entity_id`, which changes on rename.

**State and event export** (continuous, micro-batched, configurable flush interval — default: 30 seconds):
- State payload: `entity_id`, `entity_registry_id`, `state`, `attributes` (filtered), `last_changed`, `last_updated`
- Only entities matching the active filter rules are included
- Attribute exports are trimmed: only attributes in the configured allowlist are forwarded, not full attribute dicts

**Statistics export** (scheduled, configurable — default: daily at 02:00):
- Long-term hourly statistics for entities with `state_class` of `measurement`, `total`, or `total_increasing`
- Filtered to metered entities (energy, power, gas, water, monetary classes)
- Payload: `entity_registry_id`, `statistic_id`, `unit`, `mean`/`sum`/`min`/`max` per hourly bucket
- Supports selective backfill: operator can trigger a backfill for a specified date range through the add-on UI

### Filtering and mapping model

The bridge must not export all HA entities. A typical HA instance has hundreds to thousands of entities; most are irrelevant to the platform's canonical model.

Filtering is configured through the add-on options and should support:

**Include rules (additive, evaluated in order):**
- `domain_classes`: list of HA entity domains to include (e.g., `sensor`, `binary_sensor`, `climate`, `cover`, `switch`)
- `device_classes`: list of HA device classes to include (e.g., `energy`, `power`, `temperature`, `humidity`, `battery`, `motion`, `door`)
- `areas`: list of area IDs or names to include all entities assigned to those areas
- `labels`: list of HA entity labels; entities bearing any listed label are included
- `entity_ids`: explicit list of entity IDs to include regardless of other rules

**Exclude rules (take precedence over includes):**
- `excluded_entity_ids`: entities to never export regardless of other rules
- `excluded_domains`: domains to never export (e.g., `automation`, `script`, `input_button`)
- `excluded_labels`: entities with these labels are excluded

**Attribute filtering:**
- Global attribute allowlist; attributes not in the list are stripped before transmission
- Default allowlist: `unit_of_measurement`, `device_class`, `state_class`, `friendly_name`, `attribution`

**Statistics export rules** are a separate filter subset:
- Default: export statistics only for entities with `device_class` in `energy`, `gas`, `water`, `monetary`
- Explicit include/exclude overrides follow the same pattern as state export

The filter model must be versioned and recorded on the platform side so the platform knows what it is and is not receiving. This is part of the source metadata the platform uses for coverage and confidence indicators.

### Buffering and retry model

The bridge maintains a local SQLite buffer within the add-on's data directory (persisted across restarts):

- All outbound payloads are written to the buffer before transmission
- On successful delivery the buffer entry is deleted
- On delivery failure the entry remains and is retried with exponential backoff (initial: 10s, max: 5 minutes)
- The buffer has a configurable maximum age (default: 24 hours) and maximum size (default: 100 MB); oldest entries are dropped first when limits are reached
- On platform reconnection, buffered entries are replayed in chronological order before new events are forwarded
- The bridge emits a bridge health entity update to the platform after each successful delivery so the platform's freshness indicators reflect actual delivery cadence

Backfill is separate from the retry queue:
- Operator triggers a backfill from the add-on UI, specifying a date range
- Bridge fetches historical states and statistics from HA's history API for that range
- Backfill payloads are tagged with `source: backfill` and the original timestamp so the platform can distinguish backfill from live ingestion

### Health and diagnostics model

The add-on exposes a minimal ingress UI with:
- Bridge connection status (connected / disconnected / buffering)
- Platform delivery status (last successful delivery timestamp)
- Buffer depth (events queued, oldest queued timestamp)
- Active filter summary (entity counts by domain/class after filtering)
- Recent delivery errors with detail
- Backfill trigger with date range input

The add-on also publishes a heartbeat to the platform ingest API on a configurable interval (default: every 5 minutes) containing bridge version, HA version, entity count in scope, last delivery timestamp, and buffer depth. The platform uses this to compute the `sensor.homelab_analytics_bridge_freshness` synthetic entity that the integration exposes in HA.

### Failure and degraded-mode behavior

| Failure condition | Add-on behavior |
|---|---|
| Platform API unavailable | Queue to local buffer, continue HA event subscription, retry with backoff |
| HA WebSocket disconnected | Pause event export, reconnect with backoff, resync state on reconnect |
| Buffer full | Drop oldest events, log warning, emit health alert in diagnostics UI |
| HA API error on history fetch | Log error, skip that fetch cycle, do not block event export |
| Add-on process crash | Supervisor restarts it; on startup, resync entity registry and replay buffer |

The add-on must never block or delay HA's own operation. It is purely a read-and-forward consumer of HA data.

---

## 4. Integration design

### Entity model

The integration creates entities grouped into HA "devices" where each device represents a platform semantic domain or category. This keeps the entity list navigable and makes the platform's output structure visible in HA's device registry.

**Device grouping:**

| HA device name | Platform scope | Example entities |
|---|---|---|
| homelab-analytics: Finance | Finance domain publications | `sensor.hla_monthly_budget_status`, `binary_sensor.hla_budget_alert`, `sensor.hla_monthly_spend_vs_budget` |
| homelab-analytics: Utilities | Utilities domain publications | `binary_sensor.hla_peak_tariff_active`, `sensor.hla_electricity_cost_forecast_today`, `binary_sensor.hla_contract_renewal_due` |
| homelab-analytics: Assets | Asset and maintenance publications | `binary_sensor.hla_dishwasher_maintenance_due`, `sensor.hla_asset_maintenance_count` |
| homelab-analytics: Operations | Policy, recommendations, approvals | `sensor.hla_recommended_action`, `binary_sensor.hla_approval_needed`, `select.hla_policy_mode` |
| homelab-analytics: Platform | Bridge health, freshness, connectivity | `sensor.hla_bridge_freshness`, `binary_sensor.hla_platform_connected`, `sensor.hla_publication_staleness` |

Each device shares:
- `manufacturer`: homelab-analytics
- `model`: the domain name (Finance, Utilities, etc.)
- `sw_version`: platform version from the health endpoint
- `configuration_url`: the platform web UI URL

**Entity classes and purposes:**

| Entity type | Purpose | Examples |
|---|---|---|
| `sensor` | Numeric or state-string publications | Budget status (on_track / warning / over), cost forecasts, maintenance counts |
| `binary_sensor` | Boolean flags | Peak tariff active, maintenance due, contract renewal due, approval needed, budget breached |
| `select` | Enumerated operational modes | Policy mode preset, active scenario |
| `number` | Writable thresholds (if platform supports operator overrides) | Budget envelope override, notification threshold |
| `button` | Trigger platform actions without returning state | Refresh platform data, dismiss alert, trigger scenario evaluation, mark maintenance complete |
| `event` | Point-in-time notifications for automations | New recommendation available, alert fired, approval resolved |

Entity explosion control:
- The integration only creates entities for publication types that are available on the connected platform instance
- Each device group can be independently enabled or disabled in the integration options flow
- Some entity types are disabled by default and must be explicitly enabled (e.g., `number` threshold overrides, `event` entities)
- Entity names follow a consistent prefix (`hla_`) and use HA-friendly suffixes that match HA sensor naming conventions

### Update model

**Polling (primary)**: The integration uses HA's `DataUpdateCoordinator` for all publication data. Update intervals are categorized by how time-sensitive the data is:

| Category | Default interval | Examples |
|---|---|---|
| Real-time operational | 5 minutes | Tariff band state, bridge freshness |
| Daily operational | 30 minutes | Budget status, cost forecasts, maintenance flags |
| Planning/projection | 6 hours | Scenario outputs, loan projections, cost model |
| Platform health | 60 seconds | Connectivity, publication staleness, bridge heartbeat |

Each update coordinator fetches its own publication category endpoint. This prevents a slow planning publication from blocking the operational sensor update.

**Webhook push (supplementary for urgent events)**: The integration registers a webhook endpoint in HA's webhook component during setup. The platform is configured with this webhook URL and fires it for:
- Approval-needed actions (time-sensitive)
- High-priority alerts (budget breach above threshold, critical maintenance due)

The webhook handler updates the relevant entity state immediately without waiting for the next poll cycle. This avoids requiring very short poll intervals for event-driven scenarios.

**Stale data handling**: If a coordinator update fails, all entities managed by that coordinator transition to `unavailable` rather than retaining the last known state. Stale values in household planning or policy contexts are misleading; unavailable is honest.

### Service and action model

The integration registers HA services under the `homelab_analytics` domain:

| Service | Parameters | Effect |
|---|---|---|
| `homelab_analytics.refresh` | `domain` (optional) | Triggers an immediate publication refresh for one or all domains |
| `homelab_analytics.approve_action` | `action_id` | Approves a pending recommended action |
| `homelab_analytics.dismiss_alert` | `alert_id`, `snooze_hours` (optional) | Dismisses or snoozes a platform alert |
| `homelab_analytics.trigger_scenario` | `scenario_id` | Triggers evaluation of a saved scenario |
| `homelab_analytics.mark_maintenance_complete` | `asset_id` | Records a maintenance completion event on the platform |
| `homelab_analytics.set_policy_mode` | `mode` | Sets the active policy mode preset |

Services dispatch to the platform action API using the integration's scoped service token. The platform validates the action and returns a result. Services should surface errors as HA persistent notifications if the platform rejects or cannot process the action.

Button entities map to parameterless services (refresh, dismiss active alert, etc.) so operators can trigger them from dashboards without writing automations.

### Availability and diagnostics

The integration registers a `DiagnosticsCoordinator` that polls the platform health endpoint separately from publication data. Platform unavailability transitions the entire integration to `unavailable` state cleanly.

The integration provides an HA diagnostics page (accessible from the integration settings page) that exposes:
- Platform URL and version
- Last successful poll timestamps per coordinator
- Entity counts per device group
- Active webhook URL and last webhook receipt timestamp
- Recent coordinator errors with detail
- Configured poll interval overrides

### Config and options flow

**Config flow (initial setup)**:
1. Operator enters the platform base URL
2. Integration fetches `/api/platform/health` to verify connectivity
3. Operator enters or pastes a scoped service token (read + action scope)
4. Integration verifies token against `/api/publications/ha/` endpoint
5. Integration discovers available publication domains and presents a domain enable/disable selection
6. Setup complete; entities are registered

**Options flow (post-setup)**:
- Enable/disable per-domain entity groups
- Override poll intervals per category (advanced)
- Configure webhook URL if platform cannot reach HA automatically
- Add/remove publication subscriptions as the platform adds capabilities

The options flow must not require re-entering the service token unless the operator explicitly wants to rotate it.

### Grouping and organization in HA

Beyond device grouping, the integration should:
- Use consistent entity naming conventions so entities from different device groups sort together in the HA entity list
- Suggest an HA area assignment of "Platform" or "homelab-analytics" during setup so entities are spatially organized
- Provide a pre-built Lovelace card definition (via a repository-hosted dashboard YAML) for each device group so operators can quickly add a standard household-operating-picture view to their HA dashboard without manual entity configuration

---

## 5. Contract between components and platform

### Authentication and authorization

Two separate scoped service tokens are expected from the platform:

| Component | Token scope | Access |
|---|---|---|
| Add-on | `ha-bridge:ingest` | Write-only: ingest API endpoints only |
| Integration | `ha-bridge:read`, `ha-bridge:action` | Read: publication API; write: action API endpoints only |

The add-on token cannot read publication data. The integration token cannot write to ingest endpoints. This is the minimum privilege split: if the integration's read token is exposed, it cannot poison the platform's ingest pipeline.

Token rotation should be supported without requiring an add-on or integration reinstall. The add-on options and integration options flows should both have a "rotate token" path.

### Platform API surface expectations

**Ingest API (consumed by add-on):**

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/ingest/ha-bridge/registry` | POST | Entity, device, area registry snapshots |
| `/api/ingest/ha-bridge/states` | POST | Bulk state export (startup, backfill) |
| `/api/ingest/ha-bridge/events` | POST | Micro-batched state change events |
| `/api/ingest/ha-bridge/statistics` | POST | Long-term statistics batches |
| `/api/ingest/ha-bridge/heartbeat` | POST | Bridge health heartbeat |
| `/api/ingest/ha-bridge/config` | GET | Active bridge configuration (filter rules, export schedule) |

**Publication API (consumed by integration):**

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/publications/ha/` | GET | List available HA-facing publications with metadata |
| `/api/publications/ha/{publication_key}` | GET | Fetch publication data and freshness metadata |
| `/api/platform/health` | GET | Platform health, version, and readiness |
| `/api/actions/` | GET | List available action types |
| `/api/actions/{action_key}` | POST | Dispatch an action |

All endpoints require the relevant scoped token in the `Authorization: Bearer` header. The platform should return HTTP 503 with a `Retry-After` header when a publication is temporarily unavailable, rather than 200 with stale data.

### Payload categories and schema expectations

All inbound payloads (add-on → platform) should carry:
- `schema_version`: the add-on's payload schema version
- `bridge_instance_id`: stable identifier for this add-on installation
- `ha_instance_uuid`: the HA instance UUID (from `homeassistant` entity or Supervisor)
- `sent_at`: ISO timestamp

All outbound payloads (platform → integration) should carry:
- `schema_version`: the platform's publication schema version
- `publication_key`: the stable publication identifier
- `computed_at`: when the publication was last computed
- `data_through`: the latest source timestamp included in this publication
- `freshness_state`: `fresh` / `stale` / `partial` — the platform's own assessment
- `confidence`: optional float indicating the platform's coverage/quality assessment

The integration should not interpret a `stale` or `partial` freshness state as an error. It should surface it in entity attributes and in diagnostics but not mark entities unavailable unless the platform returns a non-2xx status.

### Identity and mapping model

The platform must maintain a stable mapping between HA-side identifiers and platform canonical identifiers:

| HA identifier | Stability | Use |
|---|---|---|
| `entity_registry_id` | Stable (UUID) | Primary canonical key on the platform side |
| `device_registry_id` | Stable (UUID) | Maps to platform asset or device record |
| `unique_id` | Stable within integration | Secondary key; may be absent for some integrations |
| `entity_id` | Unstable (changes on rename) | Display and lookup only; never use as canonical key |

The bridge always sends all four identifiers in the registry payload. The platform uses `entity_registry_id` as the primary key and stores `entity_id` as a display attribute that can drift.

When the platform's entity bridge layer detects that `entity_id` has changed for a known `entity_registry_id`, it updates the display mapping but does not create a new canonical record. This handles the common case of HA entity renames.

### Versioning and compatibility

- Both components should declare a `bridge_schema_version` in every payload
- The platform ingest API should accept payloads within a supported version range and reject payloads from incompatible add-on versions with HTTP 422 and a clear error body
- The platform publication API should include its own schema version in the response; the integration should log a warning but continue operating if it encounters a schema version it does not recognize
- Breaking schema changes on either side require a coordinated version bump with at least one version of backward compatibility overlap

---

## 6. Security and trust model

### Token handling

- Tokens are generated by the platform and scoped to the minimum required access
- The add-on stores its token in the Supervisor-managed add-on options (encrypted at rest by the Supervisor on HA OS)
- The integration stores its token in the HA config entry (HA's config storage, not in `configuration.yaml`)
- Neither component should log token values; structured logs should redact or omit them
- Tokens should support rotation without service interruption: the platform should accept both the old and new token for a short overlap window after rotation

### Least-privilege expectations

- The add-on's ingest token should not be able to read any platform publication data or trigger platform actions
- The integration's read+action token should not be able to write to the platform's source or control plane; it can only read publications and dispatch pre-defined action types
- Platform action endpoints should validate that the requested action type is permitted for the integration token scope
- The add-on should request only the HA API permissions it needs: state read, entity registry read, statistics read; it should not request admin or configuration write permissions

### Local network assumptions

Both components assume the platform is reachable within the local network. Neither requires cloud relay or external connectivity. The integration should support HTTPS with self-signed certificates (operator-configurable certificate verification) for homelab deployments where certificates are issued by a local CA.

The add-on should never expose HA state or the platform token to external networks. Its outbound connections go only to the configured platform URL.

### Failure isolation

- Add-on failures do not affect HA's operation. HA continues automating, controlling devices, and serving the dashboard normally.
- Integration failures surface as `unavailable` entities, not as HA-wide errors. Automations depending on integration entities should be designed to handle `unavailable` gracefully (e.g., `state != 'on'` rather than `state == 'off'`).
- A compromised integration token cannot affect ingest; a compromised add-on token cannot affect platform publications or actions.
- The platform should rate-limit ingest from the bridge to prevent a misconfigured add-on from flooding the ingest API.

### Stale and partial data handling

- If a publication's `freshness_state` is `stale`, the integration should mark entity attributes with a `data_stale: true` attribute and note the `data_through` timestamp. It should not mark entities unavailable.
- If a publication's `freshness_state` is `partial` (missing source coverage), entity attributes should note which source categories are missing. The platform's confidence indicator should be surfaced as an attribute.
- If the platform cannot compute a publication at all (returns non-2xx), all entities in that coordinator become `unavailable`. The diagnostics page should show the failure detail.

---

## 7. Non-goals and boundaries

### What should explicitly remain outside HA

- Canonical cross-domain household model: finance, utilities, assets, loans, homelab telemetry are modeled in the platform, not in HA
- Budget targets, variance computation, and planning state
- Scenario simulation and what-if results
- Policy evaluation and recommendation logic
- Long-horizon history and publication-grade marts
- Trust, lineage, and confidence metadata
- Pack ecosystem and extension loading

### What should not be implemented in the add-on

- Semantic entity modeling: the add-on is a transport bridge, not a transformation layer
- Policy evaluation: the add-on does not evaluate rules or generate recommendations
- Canonical ID assignment: the platform assigns canonical IDs; the add-on forwards stable HA identifiers
- Dashboard or card rendering: the add-on does not produce HA entities or UI artifacts; that is the integration's responsibility
- Direct actuation: the add-on does not call HA service APIs to control devices; that is reserved for the platform acting through the integration's action API or through a separate scoped actuation token

### What should not be implemented in the integration

- Transformation of raw HA state into platform canonical concepts: that belongs in the platform's normalization bridge layer
- Storage of household history: the integration is stateless between poll cycles
- Policy evaluation: the integration surfaces what the platform has decided; it does not compute recommendations
- Write-back of arbitrary HA states: the integration dispatches only pre-defined action types; it does not expose a generic HA service call proxy to the platform
- Backfill or historical data management: that is the add-on's responsibility

---

## 8. Documentation outputs to create afterward

### Architecture documents

- `docs/architecture/ha-bridge-ingest-api.md` — platform-side ingest API design: endpoint contracts, payload schemas, identity resolution, rate limiting, and schema versioning
- `docs/architecture/ha-publication-renderer.md` — platform-side publication API for HA consumption: endpoint contracts, payload schemas, freshness metadata, and action API design
- `docs/architecture/ha-addon-internals.md` — add-on component internals: WebSocket subscription model, filter evaluation, buffer design, backfill protocol, and Supervisor integration
- `docs/architecture/ha-integration-internals.md` — integration component internals: coordinator structure, entity lifecycle, webhook handler, service registration, and config/options flow

### Plan and product documents

- `docs/plans/ha-addon-packaging.md` — add-on repository structure, Supervisor manifest, ingress configuration, distribution model, and update path
- `docs/plans/ha-integration-packaging.md` — custom integration directory structure, HACS manifest, config flow implementation plan, and entity registration lifecycle

### README and onboarding additions

The project README should gain a section explaining how the two HA components relate to the platform and to each other, pointing to the design plan and the two existing boundary docs. The HA integration's own README (in its repository) should include:

- Why the integration does not store or compute household data itself
- How to obtain a scoped service token from the platform
- What entity groups are created and how to enable/disable them
- How to configure the webhook for push notifications
- Degraded-mode behavior: what unavailable entities mean and what to check

### Roadmap additions

When Stage 5 work begins in `docs/plans/household-operating-platform-roadmap.md`, the HA integration hub section should reference this design plan and the two packaging plans as the implementation input. The Stage 5 "Key deliverables" list should be updated to name:

- Platform ingest API for HA bridge (endpoint contracts, auth, schema versioning)
- Platform publication API for HA renderer (endpoint contracts, freshness metadata, action API)
- Add-on: initial release covering registry export, state/event export, buffer/retry, and diagnostics UI
- Integration: initial release covering Finance and Utilities device groups, platform health entities, and core service actions
- Filter model documentation and operator configuration guide
