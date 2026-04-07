# Adapter Governance

**Classification:** PLATFORM

## Overview

Adapter governance defines the safety and compatibility rules for extending the platform with external integrations. It establishes trust boundaries, structural validation requirements, and operator expectations for third-party and user-defined adapter packs. This framework prevents incompatible or unsafe adapters from being activated while preserving operator control over extension lifecycle.

## AdapterPack and TrustLevel

An `AdapterPack` bundles one or more adapters or renderers under a single pack_key with a declared trust level. The trust level indicates the degree of external verification and operator review required before activation.

| Trust Level | Verification | Operator Review | Use Case |
|---|---|---|---|
| `VERIFIED` | Platform-shipped, fully tested | None required | Home Assistant core integration, official adapters |
| `COMMUNITY` | Third-party, community vetted | Recommended before production | Contributed integrations, external plugins |
| `LOCAL` | User-defined, no external verification | Required before activation | Custom adapters, local integrations |

**Operator responsibilities by trust level:**
- **VERIFIED**: Assume safe. Activate and monitor for health.
- **COMMUNITY**: Review adapter source and permissions before activating in production. Monitor carefully.
- **LOCAL**: Thorough code review required. Only activate if you wrote it or fully trust the source.

## Compatibility Rules

The `check_compatibility()` function evaluates whether a pack meets platform requirements. It returns a `CompatibilityCheck` with three components:

- **`is_compatible`**: True if no blocking issues exist; False if at least one issue is present.
- **`issues`**: Blocking problems that prevent activation.
- **`warnings`**: Non-blocking concerns that should be addressed but do not prevent activation.

### Incompatibility Issues (Blocking)

- **Empty pack**: Pack contains no adapters and no renderers.
- **Version mismatch**: Pack requires a platform major version that differs from the running platform.

### Warnings (Non-Blocking)

- **Unknown platform version**: Pack declares a `requires_platform_version` but the running platform version cannot be determined. Version constraint cannot be validated.
- **LOCAL trust level**: Pack has no external verification. Operator review is strongly recommended.
- **COMMUNITY trust level**: Pack is third-party. Review before activating in production.

## Structural Validation

The `validate_adapter_pack()` function performs structural validation on an `AdapterPack`. It returns a list of error messages; an empty list means the pack is valid.

Validation rules:
- `pack_key` must be non-empty.
- `display_name` must be non-empty.
- `version` must be non-empty.
- Each adapter must have a non-empty `adapter_key`.
- Each renderer must have a non-empty `renderer_key`.
- No duplicate `adapter_key` values within the pack.
- No duplicate `renderer_key` values within the pack.

## Registry Lifecycle

The adapter registry manages the registration, activation, and lifecycle of adapter packs. The lifecycle has four distinct phases:

### 1. Registration

```python
registry.register(pack)  # Raises ValueError if pack_key already exists
```

A pack must be registered before it can be activated. Registration stores the pack metadata and marks it as inactive by default. The pack is persisted in the registry but not exposed to consumers (`active_only=True` queries).

### 2. Activation

```python
registry.activate(pack_key)  # Raises KeyError if pack not registered
```

After verification (compatibility check + operator approval), activate the pack. Activation marks the pack as ready for use. Only active packs are returned by `list_packs(active_only=True)` queries and exposed via the operator API surface.

### 3. Deactivation

```python
registry.deactivate(pack_key)  # Raises KeyError if pack not registered
```

Deactivate a pack to temporarily remove it from active use without deleting its metadata. The pack remains registered but is hidden from active queries and API endpoints.

### 4. Unregistration

```python
registry.unregister(pack_key)  # Raises KeyError if pack not registered
```

Remove a pack from the registry entirely. All metadata is deleted. Unregistration is final and irreversible.

**Key invariant**: Registration and activation are separate steps. A pack must be registered before activation, and only active packs are exposed to operators and external systems.

## Operator API Surface

The adapter API provides visibility and control over the registered and active adapter ecosystem.

| Endpoint | Method | Description |
|---|---|---|
| `/adapters/packs` | GET | List all registered packs with summary metadata (pack_key, display_name, version, trust_level, active state, adapter/renderer count). |
| `/adapters/packs/{pack_key}` | GET | Get detailed information about a specific pack including full adapter and renderer manifests. |
| `/adapters/packs/{pack_key}/enable` | POST | Activate a registered pack (mark as active). |
| `/adapters/packs/{pack_key}/disable` | POST | Deactivate a registered pack (mark as inactive). |
| `/adapters/packs/{pack_key}/health` | GET | Get health status and compatibility check results (is_compatible, issues, warnings). |
| `/adapters/packs/{pack_key}/config` | GET | Get configuration requirements (credential_requirements, adapter_count, renderer_count). |
| `/adapters/renderers` | GET | List all renderer manifests from registered packs. |
| `/adapters/contracts` | GET | Get contract vocabulary summary (available directions and trust levels). |

## Safety Boundaries

Adapters are subject to the following constraints to maintain platform integrity and data safety.

**Platform-layer state isolation**:
- Adapters must not hold application state beyond their worker reference. State is scoped to the worker instance; adapters are stateless facades.

**Manifest immutability**:
- Adapter and renderer manifests are frozen dataclasses. Once registered, manifests cannot be modified without unregistering and re-registering.

**Layer separation**:
- Adapters must not bypass the landing → transformation → reporting layer split. Ingest adapters deposit normalized payloads into the transformation layer; publish adapters read from the reporting layer only.

**Renderer read-only constraint**:
- Renderers must only read publication rows from the reporting store. Renderers must never write to any store or modify platform state.

## Adding a New Adapter Pack

To create and activate a new adapter pack, follow these steps:

### 1. Define Adapter Manifests

Create `AdapterManifest` instances for each adapter in your pack. Each manifest declares identity (adapter_key, display_name, version), capabilities (supported_directions, supported_entity_classes), and requirements (credential_requirements, health_check_contract).

```python
from packages.adapters.contracts import AdapterManifest, AdapterDirection

my_adapter_manifest = AdapterManifest(
    adapter_key="my_adapter",
    display_name="My Custom Adapter",
    version="1.0",
    supported_directions=(AdapterDirection.INGEST,),
    supported_entity_classes=("custom_entity",),
    credential_requirements=("api_key",),
    health_check_contract="connected=True when API session is active",
)
```

### 2. Define Renderer Manifests (if applicable)

Create `RendererManifest` instances for any renderers in your pack.

```python
from packages.adapters.contracts import RendererManifest

my_renderer_manifest = RendererManifest(
    renderer_key="my_renderer",
    display_name="My Custom Renderer",
    version="1.0",
    supported_formats=("csv", "json"),
)
```

### 3. Create the AdapterPack

Bundle the manifests into an `AdapterPack` with a trust_level appropriate to your pack's source and verification status.

```python
from packages.adapters.contracts import AdapterPack, TrustLevel

my_pack = AdapterPack(
    pack_key="my_pack",
    display_name="My Custom Pack",
    version="1.0",
    trust_level=TrustLevel.LOCAL,  # or COMMUNITY, VERIFIED
    adapters=(my_adapter_manifest,),
    renderers=(my_renderer_manifest,),
    description="A custom integration for my homelab.",
)
```

### 4. Validate Structural Integrity

Call `validate_adapter_pack()` to ensure the pack is well-formed.

```python
from packages.adapters.compatibility import validate_adapter_pack

errors = validate_adapter_pack(my_pack)
if errors:
    print(f"Validation errors: {errors}")
    return
```

### 5. Check Compatibility

Call `check_compatibility()` to assess platform compatibility and trust level warnings.

```python
from packages.adapters.compatibility import check_compatibility

compat = check_compatibility(my_pack, platform_version="1.5.0")
if not compat.is_compatible:
    print(f"Incompatible: {compat.issues}")
    return

if compat.warnings:
    print(f"Warnings: {compat.warnings}")
```

### 6. Register the Pack

Register the pack with the adapter registry.

```python
adapter_registry.register(my_pack)
```

### 7. Activate the Pack

After operator approval and confidence in the pack, activate it for use.

```python
adapter_registry.activate("my_pack")
```

### 8. Expose via API

Once active, the pack is automatically exposed via the operator API surface. Operators can query its metadata, health, and configuration via the `/adapters/packs/{pack_key}` endpoint.

## Related Documentation

- [Integration Adapters Architecture](./integration-adapters.md) — Detailed layer model and protocol specifications.
- [Platform Data Architecture](./data-platform-architecture.md) — Landing, transformation, and reporting layer design.
- [Operator Safety and Audit](./operator-safety-and-audit.md) — Deployment-time expectations and audit trails.
