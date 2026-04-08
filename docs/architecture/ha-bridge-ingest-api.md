# HA Bridge Ingest API

**Classification:** PLATFORM

## Purpose

This document defines the platform-side ingest surface used by the Home Assistant bridge add-on. It is narrower than the full Home Assistant integration hub in [`homeassistant-integration-hub.md`](homeassistant-integration-hub.md): this page covers only the inbound landing API, payload schemas, auth boundary, identity mapping targets, and request guardrails currently implemented under `/api/ingest/ha-bridge/*`.

The design goal is to preserve raw HA bridge payloads unchanged in landing while also producing a validated canonical CSV projection that downstream transformation and reporting work can consume without reinterpreting the raw JSON envelope.

## Implemented endpoint surface

All implemented HA bridge ingest endpoints are `POST` routes under `/api/ingest/ha-bridge/`:

| Endpoint | Purpose | Canonical dataset |
|---|---|---|
| `/api/ingest/ha-bridge/registry` | Entity, device, and area registry snapshots | `ha_bridge_registry_snapshot` |
| `/api/ingest/ha-bridge/states` | Bulk state snapshots and startup/backfill batches | `ha_bridge_states` |
| `/api/ingest/ha-bridge/events` | Micro-batched state-change events | `ha_bridge_events` |
| `/api/ingest/ha-bridge/statistics` | Long-term statistics batches | `ha_bridge_statistics` |
| `/api/ingest/ha-bridge/heartbeat` | Bridge runtime heartbeat and queue health | `ha_bridge_heartbeat` |

Each request lands two artifacts:

- Raw request bytes are persisted unchanged in landing storage.
- A canonical CSV projection is generated and validated against a typed dataset contract before the run is recorded as landed.

## Auth boundary

The HA bridge ingest surface is intentionally separated from generic ingest writes.

- Required machine scope: `ha-bridge:ingest`
- Route role requirement: operator
- Canonical permission requirement: `ingest.write`

The route policy is exact-match on scope. A token with `ha-bridge:ingest` can write to `/api/ingest/ha-bridge/*`, but it does not gain access to generic `/ingest` routes or the legacy `/api/ha/ingest` path, which continue to require `ingest:write`.

## Schema versioning

All payload models currently require:

- `schema_version = "1.0"`
- `bridge_instance_id` as a non-empty string

Unsupported HA bridge schema versions are rejected with HTTP `422`. The current implementation accepts only the exact supported version rather than a compatibility range.

## Identity and canonical mapping

The bridge payloads contain both rename-prone display identifiers and stable HA-side registry identifiers. The platform uses the stable registry identifiers as the canonical mapping source.

| Payload field | Stability | Current use |
|---|---|---|
| `entity_registry_id` | Stable | Primary canonical entity mapping input |
| `device_id` | Stable enough for current registry/device payloads | Canonical device mapping input |
| `area_id` | Stable | Canonical area mapping input |
| `entity_id` | Rename-prone | Display and lookup attribute only |

The canonical landing projection emits explicit target columns:

- `canonical_entity_id`
- `canonical_device_id`
- `canonical_area_id`

These are namespaced as:

- `ha-entity:<bridge_instance_id>:<entity_registry_id>`
- `ha-device:<bridge_instance_id>:<device_id>`
- `ha-area:<bridge_instance_id>:<area_id>`

This keeps canonical targets stable across HA entity renames while also avoiding collisions across multiple bridge installations.

For state and event payloads, `entity_registry_id` is required. The platform does not fall back to `entity_id` for canonical mapping because `entity_id` can drift when the HA operator renames an entity.

## Contract shape by category

### Registry

Registry snapshots carry entity, device, and area rows in one payload and land into the `ha_bridge_registry_snapshot` contract with a `record_type` discriminator. The canonical projection includes raw HA fields plus canonical target columns for entity, device, and area rows.

### States

State batches land into `ha_bridge_states` and require:

- `captured_at`
- `bridge_instance_id`
- `schema_version`
- `batch_source`
- per-row `entity_id`
- per-row `entity_registry_id`
- derived `canonical_entity_id`

Attributes are preserved as filtered JSON in `attributes_json`.

### Events

Event batches land into `ha_bridge_events` and require:

- `event_type`
- `event_fired_at`
- `entity_id`
- `entity_registry_id`
- derived `canonical_entity_id`

### Statistics

Statistics batches land into `ha_bridge_statistics` and require:

- `entity_registry_id`
- derived `canonical_entity_id`
- `statistic_id`
- `unit`
- bucket timestamps

`entity_id` may be present for display purposes but is not the canonical mapping key.

### Heartbeat

Heartbeat payloads land into `ha_bridge_heartbeat` and report bridge health, queue pressure, and delivery timestamps. They do not participate in canonical entity/device/area mapping.

## Request guardrails

The route layer applies a lightweight in-process rate limiter per:

- endpoint path
- `bridge_instance_id`
- client host

Current defaults:

- 12 requests
- 60 second window

When the limiter is exceeded, the API returns HTTP `429` with a `Retry-After` header. This guardrail is intended to absorb bridge retry storms without broadening the failure domain to unrelated ingest routes.

## Verification expectations

The HA bridge ingest foundation is pinned by:

- OpenAPI tests for the typed request-body schemas on the public API routes
- auth policy tests for `ha-bridge:ingest`
- landing-contract tests for the canonical CSV projections
- architecture contract tests for route registration and doc indexing

Changes to payload shape, auth scope, schema-version semantics, or canonical target columns should update this doc and the matching contract tests in the same change.
