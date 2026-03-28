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
| Layer 2 - Entity normalization bridge | `IngestAdapter.normalize()` |
| Layer 3 - Event and history bus | `IngestAdapter.connect()` and `IngestAdapter.stream()` |
| Layer 4 - Semantic and planning core | Platform-side logic, not an adapter concern |
| Layer 5 - Action and approval layer | `ActionAdapter.validate()` and `ActionAdapter.dispatch()` |
| Layer 6 - External ecosystem federation | `PublishAdapter.publish()` and outward delivery adapters |

The HA-specific protocol details remain HA-specific:

- WebSocket subscription format
- REST service-call payloads
- MQTT discovery envelopes
- HA helper semantics

Those details are implementation choices of the HA adapter, not assumptions the platform should
make about every future integration.

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
