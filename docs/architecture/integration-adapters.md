# Integration Adapter Contracts

## Purpose

This document turns Stage 6 from roadmap text into an implementation-ready contract packet.
It defines the generic adapter model that the proven Home Assistant integration can be mapped
onto without making HA-specific protocol choices part of the platform core.

## Design goals

- Keep Home Assistant as the reference adapter and primary integration surface.
- Separate generic lifecycle contracts from protocol-specific transport details.
- Normalize source state into canonical platform concepts before it reaches the core model.
- Make publication and action paths explicit rather than implicit side effects of ingest.
- Expose adapter health, credentials, and supported capabilities as first-class contract data.

## Adapter model

The platform recognizes three adapter directions. A concrete integration may implement one or
more directions, but the contract shape stays the same.

### `AdapterManifest`

`AdapterManifest` is the registration record for an adapter package or module. It should declare:

- `adapter_key`: stable identifier for registration and diagnostics
- `display_name`: operator-facing name
- `version`: adapter contract or package version
- `supported_directions`: one or more of `ingest`, `publish`, `action`
- `supported_entity_classes`: the canonical entity classes the adapter can read or produce
- `credential_requirements`: required secrets, tokens, or external auth references
- `health_check_contract`: how liveness, freshness, and degradation are reported
- `lifecycle`: startup, reconnect, checkpoint, and teardown expectations
- `target_capabilities`: any adapter-specific capabilities that downstream code may rely on

The manifest is a contract surface, not a runtime convenience object. It should be sufficient
to validate whether an adapter can be activated before any live connection is opened.
It should not carry live handles, counters, or last-seen timestamps; those belong in runtime
status snapshots.

### Runtime status

Runtime status is separate from the manifest. The manifest answers "can this adapter be
activated?" The runtime status snapshot answers "what is the adapter doing right now?" and
should stay typed so API consumers do not need to interpret ad hoc dictionaries.

At minimum, a shared runtime status shape should distinguish:

- activation state: whether the adapter was enabled or left dormant by configuration
- connection state: whether the live transport is currently attached
- freshness state: when the adapter last synchronized successfully
- operational counters: reconnects, dispatches, or other adapter-specific health counts

Adapters may expose extra fields for their own operational domain, but the snapshot should stay
stable enough for the UI, API, and operators to reason about health the same way across adapter
types.

### Health and reporting model

One coherent health model should be reused across adapter-facing runtime endpoints:

- `enabled`: whether the subsystem is configured and participating
- `connected`: whether the live transport or dispatch loop is attached
- `last_*_at`: the most recent successful sync, publish, or dispatch timestamp
- `*_count`: operational counters such as reconnects, publishes, dispatches, or errors

The concrete field names stay role-specific, but the vocabulary stays consistent. A bridge
status surface, a publisher status surface, and an action status surface should all read like
variations on the same typed runtime snapshot rather than unrelated ad hoc payloads.

### Lifecycle expectations

All adapter directions follow the same high-level lifecycle:

1. Load or discover the manifest.
2. Validate declared capabilities and credential requirements.
3. Activate the adapter and open the live transport only after validation succeeds.
4. Run the direction-specific loop: ingest, publish, or action dispatch.
5. Update a typed runtime status snapshot during operation.
6. Tear down the adapter independently so one failing integration does not destabilize the rest.

Direction-specific expectations:

- ingest adapters may persist checkpoint or cursor state when the source supports it
- publish adapters may need to re-emit discovery or registration state after reconnect
- action adapters should surface approval gates, dispatch results, and durable result state

### `IngestAdapter`

`IngestAdapter` handles state coming into the platform from an external system.

Required lifecycle responsibilities:

- `connect()`
- `stream()` or `poll()`
- `normalize()`
- `disconnect()`

The ingest adapter is responsible for:

- translating source-specific objects into canonical platform entities or events
- resolving entity identity and naming instability
- attaching quality, confidence, and freshness metadata
- preserving checkpoint or cursor state when the source supports it

The ingest contract does not allow raw source semantics to leak into the core model. Any
source-specific protocol details stay inside the adapter implementation.

### `PublishAdapter`

`PublishAdapter` handles platform state flowing outward to another system.

Required lifecycle responsibilities:

- `connect()`
- `format()`
- `publish()`
- `disconnect()`

The publish adapter is responsible for:

- mapping canonical platform state to the target system's publication shape
- carrying freshness and provenance metadata where the target supports it
- making publication failures explicit rather than silently dropping updates

### `ActionAdapter`

`ActionAdapter` handles command dispatch from platform policy or operator intent to an external
system.

Required lifecycle responsibilities:

- `validate()`
- `dispatch()`
- `report_result()`
- `disconnect()` when the target requires an explicit teardown

The action adapter is responsible for:

- checking whether an action is supported before dispatch
- surfacing approval or safety gates where the target requires them
- returning a durable result that can be audited later

## Lifecycle and registration

Adapter activation should follow the same sequence across all integration surfaces:

1. Load built-in adapters first.
2. Load configured external adapters after built-ins.
3. Validate each manifest before opening a live connection.
4. Resolve credentials through references, not embedded secrets.
5. Expose one shared health/status shape so the UI and API can reason about adapters the same way.
6. Tear down adapters independently so one broken integration does not take down the rest.

This packet intentionally keeps the lifecycle generic. Individual adapters can add their own
state machine details, but they must still fit the shared activation and health model.

## Home Assistant as reference adapter

The Home Assistant integration hub is the reference implementation for these contracts. Its
existing six-layer architecture maps to the adapter model as follows:

| HA hub layer | Adapter contract role |
|---|---|
| Layer 1 - Device and ecosystem ingress | Source systems feeding the ingest adapter |
| Layer 2 - Entity normalization bridge | `IngestAdapter.normalize()` and canonical entity mapping |
| Layer 3 - Event and history bus | `IngestAdapter.connect()`, `IngestAdapter.stream()`, and checkpoint recovery |
| Layer 4 - Semantic and planning core | Platform-side logic, not an adapter concern |
| Layer 5 - Action and approval layer | `ActionAdapter.validate()`, `ActionAdapter.dispatch()`, and approval gates |
| Layer 6 - External ecosystem federation | `PublishAdapter.publish()` and outward delivery adapters |

The HA-specific protocol details remain HA-specific:

- WebSocket subscription format
- REST service-call payloads
- MQTT discovery envelopes
- HA helper semantics

Those details are implementation choices of the HA adapter, not assumptions the platform should
make about every future integration.

The reference mapping is intentionally narrow: it shows how the proven HA implementation fits
the generic contracts, but it does not promote HA transport details into platform-wide APIs.

## Candidate integration surfaces

This packet is broad enough to cover the next wave of adapters without committing to building
them immediately.

| Surface | Likely direction(s) | Notes |
|---|---|---|
| Prometheus or remote-read monitoring | Ingest | High-volume state feeds and infrastructure telemetry |
| Kubernetes API | Ingest, action | Read cluster state and dispatch scaling or maintenance actions |
| WireGuard or Tailscale | Ingest, action | Peer health plus lifecycle or policy updates |
| Generic MQTT | Ingest, publish | Topic subscription and publication without HA discovery semantics |
| Notification services | Action | Delivery of alerts or operator requests to email or messaging targets |
| Direct device protocols | Ingest, publish, action | Adapter-specific protocol handling for non-HA device stacks |

## What this packet does not do

- It does not implement a registry or runtime loader.
- It does not build any new external adapters beyond HA.
- It does not replace the Stage 5 HA integration hub.
- It does not redefine the canonical household model or reporting layer.

The next implementation step for a concrete adapter is to define its manifest, its source or
target contract shape, and its health reporting behavior against these generic interfaces.
