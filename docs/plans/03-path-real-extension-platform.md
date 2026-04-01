# Path 3 — Real Extension Platform

## One-line framing

**Prove that homelab-analytics is a true platform whose adapters, renderers, and packs can evolve beyond a single hard-coded household implementation.**

## Strategic intent

This path makes the platform credible by demonstrating that its abstraction layers are real.

The test is not whether the code _mentions_ extensibility. The test is whether:

- Home Assistant can be treated as one adapter among several,
- publications can drive multiple surfaces without bespoke glue everywhere,
- new packs or extension modules can be added under explicit contracts,
- the platform can grow without core-surgery for every new capability.

This is the path where the repo stops looking like a strong personal system and starts looking like a reusable operating platform.

## What weak / good / impressive look like

### Weak

- a few plugin hooks,
- more interfaces added to docs,
- one extra adapter implemented with lots of hidden special cases.

### Good

- explicit adapter contracts,
- renderer contracts tied to publication metadata,
- pack activation/discovery/governance rules,
- at least two distinct integrations that prove the abstraction is working.

### Genuinely impressive

- one core publication contract supports web, Home Assistant, export/report, and agent/tool consumption cleanly,
- adapters declare ingest/publish/action capability in a uniform way,
- packs can be added, validated, activated, and version-checked with minimal core changes,
- the platform feels intentionally extensible rather than merely tolerant of modification.

## Scope

### In scope

- formal adapter model for ingest/publish/action
- formal renderer model consuming publication contracts
- pack lifecycle, discovery, validation, compatibility, and activation
- at least two non-trivial reference implementations beyond the current core/default path
- extension governance docs and verification

### Explicit non-goals

- building a full public marketplace now
- supporting arbitrary ungoverned third-party code execution
- exploding the number of adapters before the contract is solid
- rewriting core domain logic for theoretical plugin purity

## Implementation shape

### 1. Adapter contract

Define adapters as explicit platform citizens.

An adapter should be able to declare:

- identity and version
- capability type(s): ingest, publish, action, observe
- required permissions/secrets/config
- supported datasets/publications/actions
- health signals
- retry and failure semantics
- compatibility with platform/pack versions

Suggested classes of adapter:

- **Ingest adapters** — bring data into landing/control-plane contexts
- **Publish adapters** — project publications to external systems
- **Action adapters** — turn approved proposals into real-world actions or external commands
- **Observation adapters** — subscribe or mirror external state/metadata

### 2. Renderer contract

Treat the web surface as a renderer, not the definition of the platform.

A renderer should consume publication metadata plus optional UI descriptors and be able to answer:

- what surface it supports,
- what publication shapes it can render,
- what filter/sort/interaction patterns it supports,
- how trust/freshness metadata is shown,
- how navigation grouping is derived.

Reference renderers could include:

- web app renderer
- Home Assistant entity/card renderer
- export renderer (CSV/PDF/report bundle)
- assistant retrieval/summary renderer

### 3. Pack lifecycle and governance

Formalize the lifecycle for domain and extension packs.

A pack should support:

- discovery
- validation
- compatibility check
- activation/deactivation
- dependency declaration
- migration/version compatibility
- trust/governance metadata

This is where the platform earns the right to load external or future capability packs without becoming haunted.

### 4. Reference implementations

Do not stop at framework declarations. Build proof.

A genuinely useful reference set might be:

- **Home Assistant adapter** as bi-directional ingest/publish/action surface
- **Homelab telemetry adapter** for Prometheus/Kubernetes or infrastructure summary
- **Report/export renderer** for PDF/CSV/report packs
- **Assistant retrieval renderer** for grounded answers from publication contracts

You do not need all of these to full depth. But at least two distinct paths should clearly prove the contracts are real.

### 5. Extension operator experience

If extension is real, operators need a manageable control model.

Ship an extension/admin surface that can answer:

- what packs and adapters are installed,
- which are healthy,
- which publications/surfaces they activate,
- which require secrets or config,
- what compatibility warnings exist,
- what changed after enable/disable/version change.

## Workstreams

### Workstream A — contract formalization

Deliver:

- adapter manifest/schema
- renderer contract/schema
- pack lifecycle and compatibility spec
- trust/governance fields for extensions

### Workstream B — runtime support

Deliver:

- discovery/registration path for adapters and packs
- activation/deactivation behavior
- health and compatibility evaluation
- contract exposure through API/control-plane metadata

### Workstream C — reference implementations

Deliver:

- strengthen Home Assistant as a reference adapter
- add one non-HA adapter or renderer proving generality
- add one output/publish renderer beyond web

### Workstream D — extension operator surface

Deliver:

- installed extensions/packs view
- health and config state
- compatibility warnings
- enable/disable lifecycle actions where appropriate

### Workstream E — verification and governance

Deliver:

- contract tests for adapter/renderer manifests
- integration tests for registration and activation
- docs for extension boundaries and safety expectations

## Deliverables

A credible implementation in this path should ship the following:

1. **Adapter contract** for ingest/publish/action behavior
2. **Renderer contract** proving web is one surface among several
3. **Pack lifecycle/governance model**
4. **At least two reference implementations** that prove the abstractions are real
5. **Extension operator/admin surface**
6. **Compatibility and health verification** for loaded extensions

## Acceptance criteria

### Minimum bar

- adapters and renderers have explicit contracts
- one additional non-default path works under those contracts
- pack registration/compatibility is visible and testable

### Strong bar

- Home Assistant no longer feels special-cased in the architecture
- one publication can be consumed by multiple surfaces with limited bespoke glue
- extension health/configuration is inspectable by operators

### Impressive bar

- external growth of the platform feels plausible without core surgery
- pack and adapter boundaries hold under real usage
- the architecture starts to look productizable beyond one household without pretending to be a full marketplace yet

## Verification plan

### Automated

- manifest validation tests for adapters/renderers/packs
- compatibility tests for versioned activation
- integration tests covering registration and health behavior
- tests proving one publication contract supports multiple renderers/surfaces

### Manual/demo

Demonstrate all of the following:

1. activate core pack set
2. enable Home Assistant or equivalent reference adapter
3. enable one additional adapter or renderer
4. observe new surfaces/publications available through common contracts
5. view extension health and compatibility state
6. disable or break one extension and verify graceful behavior

## Risks

- building a plugin system before the core contracts are stable
- mistaking “many hooks” for “good extension architecture”
- accidental framework vanity: lots of abstractions, little practical leverage
- special-casing Home Assistant so heavily that the claimed platform model becomes fiction

## Anti-patterns to avoid

- extension APIs that bypass the publication/contract model
- secret per-adapter side channels and bespoke runtime logic everywhere
- extension loading without explicit compatibility and health states
- marketplace-style language before governance and safety are mature

## Stop conditions

Stop this path when the following are true:

- at least two distinct reference implementations clearly validate the adapter/renderer/pack model
- operators can inspect extension state and understand impact
- the platform can grow outward without every new capability forcing architectural exceptions

## Why this path matters

This is the strategic path.

If done well, it proves that the repo’s platform claims are not just elegant framing around one increasingly large personal system. It proves the abstractions are real enough to support new surfaces, new domains, and future externalized capability without constant surgery.

