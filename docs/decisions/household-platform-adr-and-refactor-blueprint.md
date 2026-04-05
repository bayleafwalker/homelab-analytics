# ADR: Headless Platform Core, Domain Capability Packs, and Replaceable Presentation Adapters

**Classification:** CROSS-CUTTING
**Status:** Accepted
**Owner:** Juha
**Decision type:** Architecture / codebase restructuring
**Applies to:** API, worker, control-plane, workflows, publications, frontend/admin surfaces

---

## 1. Executive summary

This codebase should evolve into a **platform-first modular monolith** rather than a bundle of loosely separated app components that happen to live in one repository.

The target model is:

* **Platform core** owns execution, auth, lineage, storage, scheduling, extension loading, and publication lifecycle.
* **Domain/workflow modules** contribute ingest logic, rules, transforms, reports, insights, and optional UI metadata.
* **Presentation adapters** render platform capabilities through replaceable frontends and admin surfaces.

This is explicitly **not** a move to microservices or separate repositories at this stage.

The preferred path is:

* one repo
* one deployment story
* strong internal contracts
* explicit package boundaries
* architecture tests that prevent boundary drift
* future-friendly extension loading without prematurely building a plugin marketplace empire

The practical goal is to make the platform easier to extend for new domains such as finance, utilities, and homelab telemetry **without** continuing to concentrate orchestration, policy, routing, and domain behavior into a handful of hard-working files.

---

## 2. Problem statement

The current architecture has strong intent and good operational instincts, but extension pressure is accumulating in a few key files and service modules.

Symptoms:

* route modules are doing more than transport adaptation
* worker command handlers are becoming execution hubs instead of dispatch layers
* auth runtime is centralizing too many policy branches
* runtime construction is similar across API and worker, creating future drift risk
* domain growth currently tends to add new behavior into shared orchestration code rather than attaching it through a stable capability model

This produces three medium-term risks:

1. **Maintainability risk**
   New behavior keeps landing in the same obvious files.

2. **Extensibility risk**
   Adding new domains or replacing parts of platform logic is possible, but not cleanly enough.

3. **Product-shape confusion**
   The codebase risks acting like a single app with internal subsystems instead of a platform that hosts capabilities and renders them through different surfaces.

---

## 3. Architectural position

### 3.1 Chosen direction

Adopt a **modular monolith with hard internal contracts**.

Split the codebase conceptually and structurally into:

1. **Platform core**
2. **Application/use-case orchestration**
3. **Domain capability packs**
4. **Adapters**
5. **Apps / entrypoints**

### 3.2 Rejected direction for now

Do **not** split into separate repositories or independent services yet.

Reasons:

* release/versioning tax is too high for current scale
* local development becomes slower and more brittle
* interface design is still being discovered
* there is not yet enough evidence that service boundaries are stable enough to deserve process boundaries

### 3.3 Core principle

The platform should be **headless by design**.

That means:

* frontends are replaceable
* admin surfaces are replaceable
* workflows are attachable
* domains are modular
* publications are first-class outputs
* the backend does not assume one privileged UI shape

---

## 4. Decision drivers

This structure is chosen because the project is intended to support:

* multiple rendering engines for dashboard/admin surfaces
* external or registry-defined workflow/domain additions
* self-hosted operation with increasing but controlled extensibility
* strong lineage, auditability, and rerunnable pipelines
* platform ownership of lifecycle and control, without platform ownership of every domain implementation forever

This is a better fit than a “single app with subfolders” model.

---

## 5. Scope and non-goals

### In scope

* internal package restructuring
* clear runtime/container composition model
* capability registration model
* boundary enforcement
* migration path for current route/handler/service logic
* support for replaceable presentation adapters
* support for externally supplied capability definitions in limited form

### Not in scope right now

* service decomposition into separate deployables
* public plugin marketplace
* arbitrary third-party remote code execution as a feature
* guaranteed binary compatibility for external module authors
* complete UI framework abstraction layer

The goal is extensibility with control, not platform libertarianism.

---

## 6. Target architecture

## 6.1 Layer model

### Layer A — Platform core

Owns generic platform concerns only.

Responsibilities:

* identity and auth policy
* control-plane state and stores
* scheduling / dispatch / retries
* worker execution lifecycle
* audit / lineage / event log
* storage abstraction
* publication lifecycle
* extension loading and capability registration
* policy enforcement and shared configuration

What it must **not** own:

* finance-specific categorization logic
* utility tariff comparison logic
* homelab-specific metrics semantics
* UI rendering assumptions

### Layer B — Application/use-case layer

Owns orchestration of platform capabilities into concrete operations.

Responsibilities:

* command handlers that dispatch to use-cases
* API-triggered use-cases
* worker-triggered use-cases
* query/read-model orchestration
* request/result normalization across adapters

What it must **not** become:

* another place where domain-specific logic accumulates without contracts

### Layer C — Domain capability packs

Own domain semantics.

Examples:

* finance
* utilities
* homelab
* future forecasting/planning
* contracts/documents

Responsibilities:

* source definitions
* ingest mapping rules
* normalization rules
* transforms and reports
* publication definitions
* insights/anomaly checks
* optional UI descriptors

What they must **not** do:

* reach deeply into runtime construction
* patch platform behavior by side effect
* bypass publication, lineage, or permission contracts

### Layer D — Adapters

Translate external interaction into the application/platform model.

Examples:

* HTTP API
* worker adapter
* CLI
* future TUI
* frontend contract adapters

Responsibilities:

* parse input
* validate transport-layer structures
* call use-cases
* serialize output
* handle protocol concerns

What they must **not** do:

* contain business workflow logic
* become hidden dependency injection roots

### Layer E — Apps / entrypoints

Thin startup shells.

Examples:

* API app
* worker app
* admin-modern app
* admin-retro app

Responsibilities:

* bootstrap runtime/container
* register adapters
* start serving/executing

---

## 7. Package structure proposal

This is a suggested target structure, not a law of physics.

```text
apps/
  api/
    main.py
    bootstrap.py
  worker/
    main.py
    bootstrap.py
  admin_modern/
    ...
  admin_retro/
    ...

packages/
  platform/
    auth/
      policies.py
      credential_resolution.py
      csrf.py
      authorization.py
      audit_hooks.py
    runtime/
      container.py
      builder.py
      settings.py
      registries.py
    control_plane/
      stores/
      models/
      protocols/
      scheduling/
      dispatch/
      retries/
    storage/
      blobs/
      metadata/
      manifests/
    execution/
      worker_runtime.py
      job_runner.py
      heartbeats.py
      recovery.py
    publications/
      definitions.py
      publisher.py
      lineage.py
      retention.py
    extensions/
      loader.py
      manifests.py
      validation.py
      compatibility.py
    events/
      event_log.py
      domain_events.py
    policies/
      permission_model.py
      visibility.py

  application/
    commands/
      dispatch.py
      run_commands.py
      ingest_commands.py
    queries/
      publications.py
      runs.py
      sources.py
    use_cases/
      run_workflow.py
      ingest_asset.py
      publish_result.py
      retry_run.py
      reconcile_asset.py

  domains/
    finance/
      manifest.py
      sources/
      workflows/
      rules/
      reports/
      publications/
      insights/
      ui/
    utilities/
      manifest.py
      ...
    homelab/
      manifest.py
      ...

  adapters/
    api/
      routes/
      schemas/
      serializers/
      auth/
    worker/
      command_handlers/
      serializers/
    cli/
      commands/
      formatters/
    ui_contracts/
      descriptors.py
      navigation.py
      widgets.py

  tests/
    architecture/
    integration/
    domain/
    contracts/
```

---

## 8. Boundary rules

These should be enforced through architecture tests.

## 8.1 Import direction

Allowed dependency flow:

* `apps -> adapters -> application -> platform`
* `apps -> adapters -> application -> domains`
* `domains -> platform`
* `domains -> application` only if very narrowly justified, preferably avoided

Disallowed:

* `platform -> domains`
* `platform -> adapters`
* `platform -> apps`
* `domains -> adapters`
* `domains -> apps`
* frontend/admin packages directly reaching into worker/control-plane implementation internals

## 8.2 Ownership rules

* **Platform** owns how things run.
* **Domains** own what domain behavior exists.
* **Application** coordinates execution paths.
* **Adapters** translate protocols.
* **Apps** only bootstrap.

## 8.3 File pressure thresholds

These are not strict compile errors, but they should trigger review.

* route module > 250 LOC → split by subdomain or use-case family
* command handler module > 400–500 LOC → split by command family
* auth policy module > 250 LOC → extract policy evaluators
* composition root grows multiple conditional branches per domain → move to registry-driven loading

---

## 9. Runtime/container design

The API and worker should share the same container builder.

### 9.1 Target

```python
from dataclasses import dataclass

@dataclass
class AppContainer:
    settings: Settings
    event_log: EventLog
    blob_store: BlobStore
    control_plane_store: ControlPlaneStore
    run_metadata_store: RunMetadataStore
    publication_store: PublicationStore
    extension_loader: ExtensionLoader
    capability_registry: CapabilityRegistry
    workflow_registry: WorkflowRegistry
    publication_registry: PublicationRegistry
    use_cases: UseCaseRegistry
```

### 9.2 Rules

* API and worker both construct dependencies through the same runtime builder.
* Domain capability packs are loaded into registries during bootstrap.
* Entrypoints may select modes/features, but should not reconstruct dependency graphs independently.

### 9.3 Expected benefit

* reduces API/worker drift
* centralizes configuration and registry loading
* makes extension loading predictable
* allows future admin/CLI/TUI tools to share the same core container

---

## 10. Capability pack model

Each domain or external extension should attach through a manifest-driven registration model.

### 10.1 Capability pack shape

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class CapabilityPack:
    name: str
    version: str
    sources: list["SourceDefinition"] = field(default_factory=list)
    workflows: list["WorkflowDefinition"] = field(default_factory=list)
    publications: list["PublicationDefinition"] = field(default_factory=list)
    rulesets: list["RuleSetDefinition"] = field(default_factory=list)
    insights: list["InsightDefinition"] = field(default_factory=list)
    api_extensions: list["ApiExtension"] = field(default_factory=list)
    ui_descriptors: list["UiDescriptor"] = field(default_factory=list)
```

### 10.2 Rules

* registration is explicit
* no hidden mutation of global registries through scattered imports
* capability validation occurs during bootstrap
* incompatible packs fail early with clear errors

### 10.3 Versioning approach

Initial versioning can be simple:

* platform API contract version
* pack version
* min/max compatible platform versions

Do not overdesign semantic compatibility until there is real external pack usage.

---

## 11. Workflow contract

The workflow model must be shared between API-triggered and worker-triggered execution.

### 11.1 Workflow definition

```python
from dataclasses import dataclass
from typing import Protocol, Any

class WorkflowHandler(Protocol):
    def run(self, request: Any, context: "WorkflowContext") -> Any: ...

@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    command_name: str
    input_schema: type
    result_schema: type
    retry_policy: "RetryPolicy"
    idempotency_mode: str
    publication_keys: list[str]
    required_permissions: list[str]
    handler: WorkflowHandler
```

### 11.2 Expectations

Each workflow must declare:

* input contract
* output/result contract
* retry behavior
* idempotency expectation
* permissions
* publication side effects
* lineage requirements

### 11.3 Consequence

Worker command handlers become lightweight dispatchers. They should not become the place where workflow behavior accretes forever.

---

## 12. Publication contract

Publications are first-class outputs, not incidental report files.

### 12.1 Publication definition

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class PublicationDefinition:
    key: str
    schema_name: str
    description: str
    visibility: str
    retention_policy: str
    renderer_hints: dict[str, str]
    lineage_required: bool = True
```

### 12.2 Expectations

Every publication should have:

* key/name
* schema or structural contract
* lineage source
* retention behavior
* permission/visibility behavior
* optional renderer hints for UI layers

### 12.3 Why this matters

Multiple frontends become realistic only if they can discover and consume stable publication definitions instead of reverse-engineering implicit backend behavior.

---

## 13. UI descriptor contract

To support multiple rendering engines, domain packs may optionally contribute UI metadata.

### 13.1 UI descriptor shape

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class UiDescriptor:
    key: str
    title: str
    kind: str
    publication_keys: list[str] = field(default_factory=list)
    required_permissions: list[str] = field(default_factory=list)
    supported_renderers: list[str] = field(default_factory=list)
    default_filters: dict[str, str] = field(default_factory=dict)
    renderer_hints: dict[str, str] = field(default_factory=dict)
```

### 13.2 Use

This does **not** mean putting frontend code into backend modules.

It means exposing metadata such as:

* widget/navigation identity
* which publications power a view
* renderer compatibility
* default filters or grouping hints
* permission requirements

### 13.3 Outcome

A retro dashboard and a modern admin UI can render the same capability differently without the backend being hard-coded to one visual model.

---

## 14. Auth/policy refactor direction

The current auth runtime should be decomposed by policy concern.

### Split into at least:

* credential resolution
* session/csrf handling
* bearer/service-token handling
* scope/role authorization
* audit event emission
* auth metrics hooks

### Why

A dense, branch-heavy auth middleware becomes brittle quickly and is hard to reason about, test, and extend safely.

### Testing requirement

Authorization should be covered through table-driven policy tests, not only through endpoint-level indirect checks.

Example matrix dimensions:

* principal type
* auth mode
* scope set
* role set
* route requirement
* csrf required/not required
* expected allow/deny result

---

## 15. Extension and registry model

The platform should support **limited-scope external registry loading**, not a full marketplace.

### 15.1 First realistic version

Support a registry source that can describe/install capability packs from a trusted source such as:

* Git repo
* local package path
* curated internal index

### 15.2 Pack manifest should include

* pack name/version
* platform compatibility
* exported capabilities
* optional dependencies
* trust/source metadata

### 15.3 Guardrails

* explicit admin enable/disable
* compatibility checks at load time
* ability to isolate execution in workers where practical
* no silent auto-install/update of arbitrary remote code

### 15.4 Non-goal

Do not attempt to build a polished public marketplace, social ecosystem, or untrusted plugin platform in the first implementation.

---

## 16. Migration strategy

This should be done incrementally. Do not “big bang” the repo unless you enjoy inventing new curse words.

## Phase 0 — Freeze principles

Deliverables:

* this ADR accepted or amended
* package/boundary rules agreed
* architecture tests planned

## Phase 1 — Shared runtime/container

Target:

* extract shared runtime builder used by both API and worker

Deliverables:

* `platform.runtime.builder`
* `AppContainer`
* current registries/stores moved into shared composition root
* API and worker bootstrap both call same builder

Acceptance criteria:

* API and worker no longer manually rebuild overlapping dependency graphs separately
* smoke tests pass in both modes

## Phase 2 — Extract use-cases from transport/command hubs

Target files likely include:

* API route modules
* worker command handlers
* current transformation/reporting service hotspots

Deliverables:

* route handlers become thin adapters
* command handlers become dispatch shells
* use-case modules handle orchestration

Acceptance criteria:

* same use-case callable from API and worker paths where appropriate
* reduced branching in route and handler files

## Phase 3 — Introduce capability pack model for one pilot domain

Recommended pilot: **finance** or **utilities**

Deliverables:

* one domain manifest
* workflows registered through manifest
* publications declared explicitly
* optional UI descriptors declared

Acceptance criteria:

* pilot domain behavior loads through capability registration rather than scattered wiring
* publication discovery works from registry

## Phase 4 — Add architecture tests and contract tests

Deliverables:

* import boundary tests
* workflow contract tests
* publication contract tests
* auth policy matrix tests

Acceptance criteria:

* disallowed imports fail CI
* invalid/partial capability registration fails loudly

## Phase 5 — Move additional domains and optional registry loading

Deliverables:

* domain 2 and domain 3 migrated
* optional external registry source added in controlled form

Acceptance criteria:

* new domain can be attached without editing multiple central orchestration files
* extension install/load path is documented and testable

---

## 17. Suggested agent work order

This section is written specifically so an implementation agent can pick it up with minimal ambiguity.

### Task 1 — Create target package shells

Create the directory/package structure for:

* `packages/platform/runtime`
* `packages/application/use_cases`
* `packages/domains/<pilot_domain>`
* `packages/adapters/api`
* `packages/adapters/worker`

Do not move everything yet. Create the structure first.

### Task 2 — Build shared runtime builder

Extract overlapping API/worker dependency construction into:

* `platform.runtime.container`
* `platform.runtime.builder`

Keep behavior equivalent at first. This is a **structural refactor**, not a feature change.

### Task 3 — Move route logic to use-cases

Pick the most orchestration-heavy route family.

For each route:

* parse request in adapter
* call a use-case object/function
* serialize response in adapter

Do not leave business workflow spread across route modules.

### Task 4 — Move worker execution logic to use-cases/dispatch

Refactor large command handler modules so that:

* command parsing/selection remains in handler layer
* execution lives in `application.use_cases`
* domain-specific transforms are owned by pilot domain package where possible

### Task 5 — Introduce capability registration for pilot domain

Create:

* `domains/<pilot_domain>/manifest.py`
* workflow definitions
* publication definitions
* optional UI descriptors

Register the pilot domain during runtime bootstrap.

### Task 6 — Add tests that lock the boundaries

Add architecture tests for:

* forbidden imports
* pack validation
* workflow definition completeness
* publication definition completeness
* auth policy tables where refactor touches auth

---

## 18. Definition of done

This refactor is successful when the following are true:

1. API and worker bootstrap from the same runtime/container builder.
2. Route modules are transport adapters, not workflow hubs.
3. Worker command handlers are dispatchers, not giant orchestration containers.
4. At least one domain loads through an explicit capability manifest.
5. Publications are discoverable as defined outputs rather than implicit side effects.
6. Architecture tests prevent platform/domain/adapter boundary violations.
7. A second frontend/admin surface could reasonably consume platform capability metadata without backend redesign.

---

## 19. Acceptance checks for the implementation agent

The agent should verify these conditions before claiming success.

### Structural checks

* Can API and worker runtime be diffed at the container level without major divergence?
* Can a new workflow be added to a pilot domain without editing multiple unrelated core files?
* Can a publication be enumerated from registry metadata?
* Can a UI layer discover at least basic descriptor metadata for the pilot domain?

### Testing checks

* CI architecture tests fail on forbidden imports
* pilot domain registration fails fast if required definitions are omitted
* workflow contract tests catch missing retry/idempotency/publication declarations

### Maintainability checks

* target hotspot files have reduced responsibility
* moved logic has clearer ownership per layer
* bootstrap logic is easier to reason about than before

---

## 20. Risks and mitigation

### Risk: over-abstraction too early

Mitigation:

* pilot one domain first
* keep contracts simple
* do not invent five abstraction layers per concept

### Risk: registry model becomes a side quest

Mitigation:

* support only local/curated/trusted pack sources first
* no public marketplace work now

### Risk: false modularity

Meaning: packages look neat, but central files still know too much.

Mitigation:

* enforce architecture tests
* require new domains to register through manifests
* reject changes that add domain behavior directly into platform core without strong justification

### Risk: frontend abstraction becomes hand-wavey

Mitigation:

* require publication and UI descriptor metadata for pilot domain
* prove with at least one alternate rendering surface later

---

## 21. Recommended coding rules during migration

* Prefer plain Python dataclasses/protocols over premature framework machinery.
* Prefer explicit registries over import-time magical side effects.
* Prefer table-driven tests for policy matrices.
* Prefer additive refactors with preserved behavior before semantic changes.
* Avoid mixing “move code” and “change behavior” in the same PR unless very small and well-covered.

---

## 22. Explicit non-decisions

These are intentionally not locked down yet:

* exact plugin packaging format
* whether UI descriptors eventually become JSON schema or stay Python-native
* whether future external registries use Git only or support other package indexes
* whether modern/retro frontends live in same repo forever
* whether some domain workloads later earn service separation

Those should remain open until real usage pressure makes them concrete.

---

## 23. Short version for future contributors

This project is a **headless household analytics platform**, not a single privileged UI app.

* The **platform core** runs things.
* **Domains** define behavior.
* **Adapters** expose protocols.
* **Apps** only bootstrap entrypoints.
* **Publications** are first-class outputs.
* **Frontends** render capabilities; they do not define the platform.

When adding new functionality, ask:

1. Is this platform concern, domain concern, application orchestration, or adapter logic?
2. Can it be registered through a capability pack instead of wired into central files?
3. Does it produce or consume a first-class publication?
4. Would a second frontend still work if this change exists?

If the answer to #2 or #4 is “no” without a very good reason, the change probably belongs somewhere else.

---

## 24. Immediate next step recommendation

Start with **shared runtime/container extraction** and **one pilot domain capability pack**.

That gives the highest leverage and creates the skeleton the rest of the refactor can hang on.

Trying to do everything at once will only create a more neatly arranged mess.


## Key Gaps and Recommendations
Based on the current repo and best practices, here are the critical focus areas for the next steps:

* Enforce Internal Contracts: Best practices for Python monoliths emphasize using FastAPI routers or façade-style interfaces to maintain module independence. Your plan for "strong internal contracts" is vital here to prevent the "neatly arranged mess" you warned about.

* Infrastructure as a Domain: Since the current repo is 90% infrastructure, the first "Capability Pack" should likely be an Infrastructure/Inventory Domain. This would turn your Ansible/K8s logic into a platform-managed capability rather than just a sidecar folder.

* Unified Schema/Lineage: A headless data architecture requires well-defined schemas and a metadata catalog. As you build the "Platform Core," ensure it provides a first-class way for domains to register their data shapes (e.g., using Pydantic or JSON Schema) to maintain the proposed "lineage" feature.
