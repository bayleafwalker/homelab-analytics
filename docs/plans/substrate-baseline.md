# Substrate Baseline: Platform Kernel and Household App Realignment

**Status:** Proposed
**Owner:** Juha
**Classification:** CROSS-CUTTING
**Date:** 2026-03-30

---

## 1. Purpose

This document assesses the current state of homelab-analytics as two things sharing one repo:

1. A reusable self-hostable data platform substrate (kernel)
2. A first-party household app / flagship capability built on top of that substrate

It defines the boundary between them, identifies where that boundary leaks, and produces a concrete plan to make the repo operate as "platform kernel + first-party household app" while staying in one repo.

This is not a framework rewrite proposal. It is a seam-definition and boundary-enforcement plan. The goal is to design for extraction without extracting.

---

## 2. Framing

homelab-analytics exists because there is no open, self-hostable, long-term-reliable data platform for homelab users that plays the role Databricks or Snowflake play in the cloud: a general substrate for ingesting, modeling, storing, and serving many personal or household domains under local control.

The repository should therefore be judged primarily as:

- a self-hostable platform substrate for personal/household/homelab domains
- plus a first-party household application built over that substrate

The repository should not primarily drift into:

- a better budgeting app
- a prettier dashboard suite
- a generic Home Assistant add-on
- a pile of disconnected ETL jobs
- a fake-generic "framework" invented for hypothetical future consumers

---

## 3. Executive summary

The repo is already approximately 60% of the way to being a kernel with a sewn-in flagship app. The ADRs, capability pack model, publication contract system, and `packages/platform/` structure all show clear platform intent. The capability pack registration model is real and working: four domain packs boot through manifest-driven registration. The 5-layer architecture from the platform ADR is partially realized.

The current biggest architectural problem is that `packages/pipelines/` is a 19,200-line monolith containing both the platform's generic transformation/promotion/reporting engine and all household domain logic (finance transforms, utility transforms, HA integration, scenario engine, budget models, loan models). This single flat package is the main reason the kernel/app seam is blurry. The platform runtime (`packages/platform/runtime/builder.py` and `container.py`) directly imports 11 modules from `packages/pipelines/`, making it impossible to boot the platform without the household pipeline code present.

The recommended strategic direction is to treat `packages/pipelines/` as the primary surgical target. Split it into platform-generic pipeline infrastructure (stays in `packages/pipelines/` or moves to `packages/platform/pipelines/`) and domain-specific pipeline logic (moves into `packages/domains/`). This is the single change that makes kernel vs app actually enforceable. Everything else is secondary.

The next most important move is to extract the approximately 35 domain-specific pipeline files from `packages/pipelines/` into their respective `packages/domains/` directories, then fix the import boundary so `packages/platform/` never reaches into domain code.

---

## 4. Current-state separation assessment

### 4.1 Already substrate-like

| Area | Key files/packages | Notes |
|---|---|---|
| Capability pack types and registry | `packages/platform/capability_types.py`, `packages/platform/capability_registry.py` | Clean generic contracts, no domain vocabulary |
| Auth subsystem | `packages/platform/auth/` (14 files, ~2200 LOC) | Fully generic: OIDC, session, JWT, proxy, RBAC, audit |
| Storage layer | `packages/storage/` (~13,300 LOC) | Control plane, blob, run metadata, ingestion config: all generic |
| Shared infrastructure | `packages/shared/` (~2200 LOC) | Settings, extensions, function registry, logging, metrics: generic |
| Landing/ingestion primitives | `control_plane.py`, `landing_service.py`, `ingestion_catalog.py` | Source-agnostic ingestion infrastructure |
| Publication field semantics | `PublicationFieldDefinition`, `CapabilityPack.validate()` | Domain-agnostic semantic typing system |
| Extension/plugin loading | `ExtensionRegistry`, `load_extension_modules`, pipeline registries | Generic plugin loading, module scanning |
| Database migrations (mostly) | `migrations/postgres/0001_initial_schema.sql` | Schema is mostly domain-agnostic: source_systems, dataset_contracts, etc. |
| Architecture tests | `tests/test_architecture_contract.py` | Import boundary enforcement already exists |

### 4.2 Clearly household app logic

| Area | Key files | Notes |
|---|---|---|
| Domain manifests | `packages/domains/{finance,utilities,overview,homelab}/manifest.py` | Correct location, clean structure |
| Domain source definitions | `packages/domains/*/sources/*.py` | Well-encapsulated source contracts |
| Finance source contracts | `packages/domains/finance/contracts/*.py` | OP CSV, Revolut, credit registry: properly in domains |
| Household-specific transforms | `transformation_transactions.py`, `transformation_budgets.py`, `transformation_loans.py`, `transformation_utilities.py`, `transformation_homelab.py`, etc. (~12 files) | Wrong location: in `packages/pipelines/` not `packages/domains/` |
| Household domain models | `transaction_models.py`, `budget_models.py`, `loan_models.py`, `utility_models.py`, `homelab_models.py`, etc. (~15 files) | Wrong location: in `packages/pipelines/` |
| Household services | `account_transaction_service.py`, `budget_service.py`, `loan_service.py`, `utility_bill_service.py`, `scenario_service.py`, etc. | Wrong location: in `packages/pipelines/` |
| HA integration | `ha_bridge.py`, `ha_mqtt_publisher.py`, `ha_action_dispatcher.py`, `ha_policy.py`, etc. (8 files) | Wrong location: in `packages/pipelines/` |
| Frontend/web shell | `apps/web/` | Household-specific screens: budgets, loans, costs |
| Category rules/seeds | `category_rules.py`, `category_seed.py` | Finance-specific, wrong location |

### 4.3 Mixed / ambiguous / leaky

| Area | Problem | Severity |
|---|---|---|
| `packages/pipelines/` (entire package) | ~85 files mixing platform engine code with domain transforms/models/services | High |
| `packages/platform/runtime/builder.py` | Platform composition root directly imports `AccountTransactionService`, `SubscriptionService`, `ContractPriceService` and 8 other pipeline modules | High |
| `packages/platform/runtime/container.py` | `AppContainer` has hard-coded fields for `service` (AccountTransactionService), `subscription_service`, `contract_price_service`, `finance_pack` | High |
| `packages/platform/current_dimension_contracts.py` | Platform file defines household-specific dimensions: `dim_account`, `dim_counterparty`, `dim_contract`, `dim_meter`, `dim_loan`, `dim_asset` | High |
| `packages/platform/publication_contracts.py` | Platform file imports `builtin_reporting` from pipelines | Medium |
| `packages/shared/external_registry.py` | Shared utility imports all 4 domain pack manifests directly | Medium |
| `builtin_packages.py` | Defines finance-specific publication specs (cashflow, counterparty) as "builtin" | Medium |
| `builtin_promotion_handlers.py`, `builtin_reporting.py` | "Builtin" handlers contain household-specific mart names and transform logic | Medium |
| API route registration in `apps/api/app.py` | `create_app()` hard-wires `register_homelab_routes`, `register_category_routes`, `register_scenario_routes`, `register_ha_routes` | Medium |

### 4.4 Existing boundaries that support the split

1. `packages/domains/` already exists with 4 packs. The manifest pattern works. It just needs the actual domain logic (currently in `pipelines/`) moved into it.
2. `packages/platform/capability_types.py` is a clean, domain-free contract. Domain packs already import from it.
3. Architecture test infrastructure exists in `test_architecture_contract.py`. It uses AST-based import checking. Extending it is straightforward.
4. `build_container()` already accepts `capability_packs` as a parameter. The seam exists; it is just violated by the container also hard-coding domain services.
5. `apps/api/main.py` already explicitly lists which packs to boot (`FINANCE_PACK, UTILITIES_PACK, OVERVIEW_PACK, HOMELAB_PACK`). The composition point is visible.

### 4.5 Where naming or documentation hides the seam

- The README describes the system as a "household operating platform" without distinguishing kernel from app.
- Docs directory structure is flat: no `docs/platform/` vs `docs/apps/household/` split.
- ADRs are not tagged as PLATFORM / APP / CROSS-CUTTING.
- "Builtin" prefix in pipeline code (`builtin_packages.py`, `builtin_promotion_handlers.py`, `builtin_reporting.py`) disguises household-specific content as platform infrastructure.
- The 11-stage roadmap mixes platform capabilities (Stages 6-9) with household product (Stages 2-5) without labeling which is which.

### 4.6 Runtime composition assessment

The runtime composition partially supports the split but has significant violations:

- **Good:** Both API and worker share `build_container()`. Capability packs are passed in explicitly.
- **Bad:** `build_container()` constructs `AccountTransactionService`, `SubscriptionService`, and `ContractPriceService` directly. These are household services, not platform concerns.
- **Bad:** `AppContainer` has typed fields for household-specific services instead of a generic service registry.
- **Bad:** `create_app()` in `apps/api/app.py` takes 37 parameters, many household-specific (HA bridge, HA MQTT, scenario service).

---

## 5. Boundary leak report

### Leak 1: `packages/platform/runtime/` imports from `packages/pipelines/` (19 imports)

`builder.py` imports 11 pipeline modules. `container.py` imports 8 pipeline modules. These include household-specific services (`AccountTransactionService`, `SubscriptionService`, `ContractPriceService`).

The platform composition root cannot be tested, imported, or understood without all household pipeline code present. A second domain app cannot boot without the finance pipeline.

**Severity:** High

**Affected files:** `packages/platform/runtime/builder.py`, `packages/platform/runtime/container.py`

**Smallest effective fix:** Split `AppContainer` into a generic `PlatformContainer` (holds only platform registries, stores, settings) and a `HouseholdAppContainer` that extends it with domain-specific services. Move domain service construction out of `build_container()` into the app entrypoints or a household-specific builder.

### Leak 2: `packages/platform/current_dimension_contracts.py` contains household dimensions

This platform file defines `dim_account`, `dim_counterparty`, `dim_contract`, `dim_meter`, `dim_loan`, `dim_asset` with household-specific field semantics ("merchant or counterparty name", "ISO currency code associated with the account").

These are finance/utilities domain concepts coded into the platform. A homelab-only or IoT-only deployment would ship meaningless dimension contracts.

**Severity:** High

**Affected files:** `packages/platform/current_dimension_contracts.py`

**Smallest effective fix:** Move to `packages/domains/finance/` and `packages/domains/utilities/` respectively, registered via the capability pack manifest. Extend `CapabilityPack` to include `current_dimension_contracts` if needed.

### Leak 3: `packages/platform/publication_contracts.py` imports from `packages/pipelines/builtin_reporting`

Platform publication contract builder imports `PUBLICATION_RELATIONS` and `CURRENT_DIMENSION_RELATIONS` from `packages/pipelines/builtin_reporting`.

Violates the layer direction rule (platform must not import from pipelines). The "builtin" reporting contains household-specific mart definitions.

**Severity:** Medium

**Affected files:** `packages/platform/publication_contracts.py`, `packages/pipelines/builtin_reporting.py`

**Smallest effective fix:** Invert the dependency. Have capability packs provide their publication relations via manifest, and have the platform contract builder accept them as parameters rather than importing them.

### Leak 4: `packages/shared/external_registry.py` imports all 4 domain manifests

The shared external registry module directly imports `FINANCE_PACK`, `UTILITIES_PACK`, `OVERVIEW_PACK`, `HOMELAB_PACK`.

The shared layer (which should be below domains) depends on domain-specific manifests. Adding or removing a domain requires editing a platform-level file.

**Severity:** Medium

**Affected files:** `packages/shared/external_registry.py`

**Smallest effective fix:** Accept capability packs as a parameter instead of importing them. The caller (which already knows which packs to load) passes them in.

### Leak 5: `packages/pipelines/` is an unseparated mix of platform and domain code

Approximately 85 Python files, approximately 19,200 LOC in a single flat package. Approximately 35 files are household-domain-specific (transforms, models, services for finance, utilities, homelab, HA, scenarios, budgets, loans). Approximately 20 files are platform-generic (promotion, pipeline catalog, transformation service, reporting service, CSV validation, extension registries). The rest are ambiguous.

Cannot enforce import boundaries within a single package. Cannot test platform pipeline logic without household code. Cannot build a second domain app without shipping all household pipeline files.

**Severity:** High

**Affected files:** All of `packages/pipelines/`

**Smallest effective fix:** Move domain-specific files into `packages/domains/{finance,utilities,homelab,overview}/`. Keep platform-generic pipeline files in place (or move to `packages/platform/pipelines/`). This is the single highest-leverage structural change.

### Leak 6: `AppContainer` has household-specific typed fields

`AppContainer` includes `service: AccountTransactionService`, `subscription_service`, `contract_price_service`, `finance_pack`. The container comments even say "transitional: will move into finance domain capability pack."

The platform container is shaped like the household app. Adding a new domain requires editing the platform container definition.

**Severity:** Medium

**Affected files:** `packages/platform/runtime/container.py`

**Smallest effective fix:** Move domain-specific services behind a `domain_services: dict[str, Any]` or a per-pack service accessor, or move them into a household-specific container that wraps the platform container (as the worker's `WorkerRuntime` already does).

### Leak 7: `builtin_packages.py` embeds household publication specs as "builtin"

`BUILTIN_TRANSFORMATION_PACKAGE_SPECS` defines specs for "account transactions", "subscriptions", "contract prices", "utility bills", "utility usage" as "built-in."

Naming domain-specific content "builtin" makes it look like platform infrastructure, discouraging future separation.

**Severity:** Low

**Affected files:** `packages/pipelines/builtin_packages.py`, `builtin_promotion_handlers.py`, `builtin_reporting.py`

**Smallest effective fix:** Rename to `household_packages.py` or move these registrations into the domain pack manifests. The "builtin" prefix should only describe platform-generic behavior.

### Leak 8: API `create_app()` takes 37 parameters including HA-specific objects

`apps/api/app.py` `create_app()` accepts `ha_bridge`, `ha_mqtt_publisher`, `ha_policy_evaluator`, `ha_action_dispatcher`, `ha_action_proposal_registry` as direct parameters.

The platform's HTTP surface requires household-specific integration objects. Cannot build a minimal platform API without HA parameters.

**Severity:** Low (functional, but architecturally noisy)

**Affected files:** `apps/api/app.py`

**Smallest effective fix:** Move HA route registration into a domain pack's API extension hook, or group HA objects into a single optional integration config.

---

## 6. Promotion test for app-to-platform candidates

### 6.1 Current dimension contracts (`dim_account`, `dim_counterparty`, etc.)

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | No. `dim_account` and `dim_counterparty` are finance-specific. `dim_meter` is utilities-specific. |
| Can be described without household terminology? | No. "account", "counterparty", "loan" are inherently household/finance. |
| Reduces future duplication? | Not for non-household domains. |
| Can be tested independently? | No. The contract values reference finance semantics. |

**Verdict: Stay app-local.** Move to `packages/domains/`. The mechanism for declaring current-dimension contracts is platform; the instances are app.

### 6.2 Scenario engine (`scenario_service.py`, `scenario_models.py`)

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | Maybe. "What-if" modeling is potentially generic. But the current implementation is tightly coupled to loan, income, and expense scenarios. |
| Can be described without household terminology? | Partially. The engine structure is generic, but all scenario types are household-specific. |
| Reduces future duplication? | Not yet proven. |
| Can be tested independently? | Not currently. Tests use household fixtures exclusively. |

**Verdict: Stay app-local for now.** Revisit if a second domain (e.g., homelab capacity planning) would use the same scenario engine.

### 6.3 Promotion/transformation/reporting pipeline engine

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | Yes. Any domain needs source promotion, transformation scheduling, and report publication. |
| Can be described without household terminology? | Yes. `promote_source_asset_run`, `TransformationService`, `ReportingService` are domain-agnostic. |
| Reduces future duplication? | Yes. Every new domain would need this. |
| Can be tested independently? | Yes with cleanup. The engine code itself is generic, but `builtin_*` files bake in household content. |

**Verdict: Promote to platform.** The engine is genuinely generic. The "builtin" registrations that reference household content should be separated.

### 6.4 HA integration bridge/MQTT/action dispatcher

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | No. HA integration is specific to the household/homelab domain. |
| Can be described without household terminology? | The bridge pattern is somewhat generic (WebSocket state sync), but the implementation references HA entities, MQTT topics, and household policies. |
| Reduces future duplication? | No. |
| Can be tested independently? | Not meaningfully. |

**Verdict: Stay app-local.** The adapter contract shape (from the integration-adapters ADR) is platform material; the HA implementation is app.

### 6.5 CSV validation / configured ingestion

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | Yes. Any domain using CSV sources needs validation, schema checking, and column mapping. |
| Can be described without household terminology? | Yes. |
| Reduces future duplication? | Yes. |
| Can be tested independently? | Yes. |

**Verdict: Already platform.** Keep in place; just ensure it does not import household modules.

### 6.6 Source freshness evaluation (`packages/domains/finance/freshness.py`)

| Test | Result |
|---|---|
| Would 2+ non-household apps need this? | Yes. Any domain with recurring ingestion sources needs freshness tracking. |
| Can be described without household terminology? | Yes. The logic operates on Protocol types. |
| Reduces future duplication? | Yes. |
| Can be tested independently? | Yes. |

**Verdict: Promote to platform.** Currently in `packages/domains/finance/` but is completely generic. Move to `packages/platform/` or `packages/shared/`.

---

## 7. Boundary enforcement plan

### E-1: AST-based import boundary test (extend existing)

**What it enforces:** `packages/platform/` must not import from `packages/domains/` or domain-classified `packages/pipelines/` files. `packages/shared/` must not import from `packages/domains/`.

**How hard:** Easy. `test_architecture_contract.py` already has the `_import_names()` helper. Add 2 new test functions.

**Why worth it now:** This is the single cheapest guardrail that prevents re-introduction of the leaks identified above.

### E-2: Pack-free boot smoke test

**What it enforces:** Platform container can be constructed and serve `/health` without any capability packs.

**How hard:** Medium. Requires container cleanup first (Section 9: WP-2).

**Why worth it now:** Proves the kernel is actually separable. Worth adding right after container cleanup.

### E-3: Domain vocabulary lint for platform package

**What it enforces:** Configurable list of household-specific terms (`account_transaction`, `subscription`, `budget`, `loan`, `tariff`, `counterparty`, `merchant`, `cashflow`, `utility_bill`, `affordability`) must not appear as identifiers in `packages/platform/`.

**How hard:** Easy. Simple grep/AST scan in CI.

**Why worth it now:** Catches future leaks at the naming level, which is where leaks start.

### E-4: Forbidden import mapping in CI

**What it enforces:** Layered import rules: platform can import from shared and storage only. Domains can import from platform. Domains cannot import from other domains unless explicitly declared.

**How hard:** Medium. Needs a small config file defining allowed import directions and an AST walker.

**Why worth it later:** Adds the most comprehensive layer protection but requires the pipelines split first.

### E-5: ADR/doc classification tag requirement

**What it enforces:** Every new doc in `docs/decisions/`, `docs/architecture/`, and `docs/product/` must include a `Classification: PLATFORM | APP | CROSS-CUTTING` header.

**How hard:** Easy. Add to doc templates and review checklist.

**Why worth it now:** Zero-cost prevention of future documentation drift.

### E-6: Contribution workflow classification rule

**What it enforces:** PR descriptions must declare whether the change is platform, app, or cross-cutting. Sprint items must be tagged.

**How hard:** Easy. Add to PR template.

**Why worth it now:** Makes the seam visible in the daily workflow.

---

## 8. Prioritized backlog

### 8.1 Platform / Kernel

#### PK-1: Split `packages/pipelines/` into platform-generic and domain-specific halves

- **Type:** boundary clarification
- **Why it exists:** `packages/pipelines/` is the main boundary violation: 85 files mixing platform engine code with household domain logic.
- **Problem being solved:** Cannot enforce import boundaries, test platform pipeline logic independently, or boot the system without household code.
- **Why this bucket:** The pipeline engine (transformation service, promotion, reporting service, pipeline catalog, registries) is platform infrastructure. The domain transforms, models, and services are app code.
- **Dependencies:** None. This is the foundational move.
- **Acceptance criteria:** (1) Platform pipeline files have zero imports from domain-specific pipeline files. (2) `packages/platform/` has no imports from domain modules. (3) Architecture test enforces this boundary.
- **Validation:** AST-based import boundary test. Boot test with empty capability pack list.
- **Rollback:** File moves are fully reversible via git.

#### PK-2: Clean `AppContainer` of household-specific typed fields

- **Type:** composition/registration seam
- **Why it exists:** Container has `service: AccountTransactionService`, `subscription_service`, `contract_price_service`, `finance_pack` as typed fields.
- **Problem being solved:** Platform container is household-shaped, preventing clean domain swapping.
- **Why this bucket:** Container definition is platform infrastructure.
- **Dependencies:** PK-1 (moving domain services out of pipelines).
- **Acceptance criteria:** `AppContainer` contains only platform-generic fields. Domain services accessed through capability pack service accessors or a domain-specific container wrapper.
- **Validation:** `AppContainer` can be instantiated with zero domain services for a smoke test.
- **Rollback:** Keep old accessor properties as deprecated shims during transition.

#### PK-3: Move `current_dimension_contracts.py` out of platform

- **Type:** boundary clarification
- **Why it exists:** Household-specific dimension definitions (account, counterparty, loan, etc.) live in `packages/platform/`.
- **Problem being solved:** Platform code embeds household vocabulary.
- **Why this bucket:** The contract shape is platform; the contract instances are domain.
- **Dependencies:** PK-1 (need domain packages to receive this code).
- **Acceptance criteria:** `packages/platform/` contains no household-specific dimension names. Domain packs register their dimension contracts through the manifest.
- **Validation:** Grep for household nouns in platform package returns zero hits.

#### PK-4: Invert `publication_contracts.py` dependency on `builtin_reporting`

- **Type:** dependency rule enforcement
- **Why it exists:** Platform publication contract builder imports from `packages/pipelines/builtin_reporting`.
- **Problem being solved:** Platform depends on pipeline internals.
- **Why this bucket:** Dependency direction violation.
- **Dependencies:** PK-1.
- **Acceptance criteria:** `packages/platform/publication_contracts.py` has zero imports from `packages/pipelines/`.
- **Validation:** Architecture import test.

#### PK-5: Remove domain manifest imports from `packages/shared/external_registry.py`

- **Type:** dependency rule enforcement
- **Why it exists:** Shared utility directly imports all 4 domain pack manifests.
- **Problem being solved:** Shared layer depends on domain layer.
- **Dependencies:** None.
- **Acceptance criteria:** `packages/shared/` has zero imports from `packages/domains/`.
- **Validation:** Architecture import test.

#### PK-6: Promote source freshness evaluation to platform

- **Type:** boundary clarification
- **Why it exists:** `packages/domains/finance/freshness.py` contains completely generic freshness evaluation logic operating on Protocol types. It is misplaced in the finance domain.
- **Problem being solved:** Platform-generic logic lives in a domain package, forcing other domains to import from finance or duplicate.
- **Why this bucket:** Freshness evaluation passes all four promotion tests.
- **Dependencies:** None.
- **Acceptance criteria:** Freshness evaluation logic lives in `packages/platform/` or `packages/shared/`. Finance domain imports from platform. Other domains can use freshness without importing finance.
- **Validation:** All freshness tests pass from new location.

### 8.2 App / Household

#### AH-1: Receive domain transforms/models/services from `packages/pipelines/`

- **Type:** boundary clarification
- **Why it exists:** Counterpart to PK-1. The household domain logic needs a home.
- **Problem being solved:** Domain-specific pipeline code needs to live in `packages/domains/`.
- **Why this bucket:** This is household app code being relocated.
- **Dependencies:** PK-1 (coordinated move).
- **Acceptance criteria:** Each domain pack directory contains its own transforms, models, and services. Domain manifest imports are internal to the domain package.
- **Validation:** Domain packs can be loaded/unloaded independently. Tests pass.

#### AH-2: Move "builtin" household publication specs into domain manifests

- **Type:** composition/registration seam
- **Why it exists:** `builtin_packages.py`, `builtin_promotion_handlers.py`, `builtin_reporting.py` contain household-specific content named "builtin."
- **Problem being solved:** Household content disguised as platform builtins.
- **Why this bucket:** The publication specs and promotion handlers belong to the domain packs that define them.
- **Dependencies:** PK-1 and AH-1.
- **Acceptance criteria:** No household-specific publication keys in files named "builtin_*". Domain packs provide their own publication-to-transform mappings.
- **Validation:** Rename "builtin_*" to "default_*" or move content into domain packs. All tests pass.

#### AH-3: Move HA route registration to domain pack API extension

- **Type:** app capability work
- **Why it exists:** `create_app()` hard-wires HA routes and takes 5 HA-specific parameters.
- **Problem being solved:** API surface assumes HA integration presence.
- **Why this bucket:** HA integration is household/homelab-specific.
- **Dependencies:** PK-2 (container cleanup). Low priority.
- **Acceptance criteria:** HA routes are registered via the homelab domain pack's API extension hook. `create_app()` does not name HA objects.
- **Validation:** API boots without HA parameters. HA routes appear when homelab pack is loaded.

### 8.3 Cross-cutting separation work

#### XC-1: Add import boundary enforcement test: platform to domains

- **Type:** dependency rule enforcement
- **Why it exists:** No automated check prevents `packages/platform/` from importing `packages/domains/` or domain-specific `packages/pipelines/` code.
- **Problem being solved:** Future drift will re-introduce boundary violations after cleanup.
- **Why this bucket:** Enforcement mechanism, not platform or app logic.
- **Dependencies:** PK-1 (needs to know which pipeline files are platform vs domain).
- **Acceptance criteria:** CI test fails if `packages/platform/` imports from `packages/domains/` or domain-specific pipeline modules.
- **Validation:** Intentionally add a violating import, confirm test fails, revert.

#### XC-2: Add import boundary enforcement test: shared to domains

- **Type:** dependency rule enforcement
- **Why it exists:** `packages/shared/` currently imports domain manifests.
- **Problem being solved:** Same as XC-1 for the shared layer.
- **Dependencies:** PK-5.
- **Acceptance criteria:** CI test fails if `packages/shared/` imports from `packages/domains/`.

#### XC-3: Add pack-free boot smoke test

- **Type:** testability improvement
- **Why it exists:** No test verifies that the platform can boot with zero domain packs.
- **Problem being solved:** Proves the kernel is actually separable.
- **Dependencies:** PK-1 and PK-2.
- **Acceptance criteria:** Test constructs an `AppContainer` with `capability_packs=()`, starts a minimal FastAPI app, hits `/health` and `/ready`. No domain code imported.
- **Validation:** Test passes in CI.

#### XC-4: Tag ADRs and design docs as PLATFORM / APP / CROSS-CUTTING

- **Type:** docs/process clarification
- **Why it exists:** Docs do not distinguish platform decisions from household app decisions.
- **Problem being solved:** Contributors and agents cannot quickly classify proposed work.
- **Dependencies:** None.
- **Acceptance criteria:** Every doc in `docs/decisions/` and `docs/architecture/` has a classification tag. New doc template includes the tag field.

#### XC-5: Create contributor decision guide

- **Type:** docs/process clarification
- **Why it exists:** No documented rules for classifying new work.
- **Problem being solved:** Prevents future drift without automated enforcement.
- **Dependencies:** XC-4.
- **Acceptance criteria:** Single-page decision tree in `docs/architecture/` that agents and humans can follow to answer "is this platform, app, or cross-cutting?"

### 8.4 Deferred / not yet justified

#### D-1: Formal capability pack API extension protocol

Domain packs currently cannot contribute API routes through the manifest. Routes are hardcoded in `app.py`. Only 4 domain packs exist; hardcoded registration is manageable. Build this when a 5th pack would make the pattern painful.

#### D-2: Separate deployable kernel image

Could ship a minimal platform image without household code. Single user, single deployment. No proven demand.

#### D-3: Domain pack test isolation (per-pack CI)

Could test each domain pack independently. All tests run fast enough (~1074 tests). Split when test suite exceeds approximately 5 minutes or when domain teams emerge.

#### D-4: Generic transformation domain-pack registration protocol

The transformation domain registry uses `build_builtin_transformation_domain_registry()` which hardcodes household domain loaders. Only needed after PK-1 demonstrates the value. Build when adding a second non-household domain.

---

## 9. Sprint-ready work packages

### Group 1: Immediate foundation work

#### WP-1: Split `packages/pipelines/` into platform and domain halves

- **Type:** platform + app (coordinated)
- **Goal:** Establish the fundamental code boundary between kernel and household app
- **Exact scope:** Move approximately 35 domain-specific files from `packages/pipelines/` into `packages/domains/{finance,utilities,homelab,overview}/pipelines/`. Keep approximately 20 platform-generic files in `packages/pipelines/`. Update all imports.
- **Files affected:** Approximately 35 files moving, approximately 50 files with import updates, all test files
- **Validation:** All 1074+ tests pass. AST import scan confirms zero platform-to-domain pipeline imports.
- **Rollback:** Single git revert.
- **ADR required:** No. This implements the existing ADR's layer model.
- **Dependencies:** None.

Domain-specific files to move (approximate classification):

**To `packages/domains/finance/pipelines/`:**
- `account_transaction_service.py`, `account_transaction_inbox.py`, `account_transactions.py`
- `transaction_models.py`, `subscription_models.py`, `subscription_service.py`, `subscriptions.py`
- `budget_models.py`, `budget_service.py`, `budgets.py`
- `loan_models.py`, `loan_service.py`, `amortization.py`
- `balance_models.py`, `contract_price_models.py`, `contract_price_service.py`, `contract_prices.py`
- `category_rules.py`, `category_seed.py`
- `scenario_models.py`, `scenario_service.py`
- `bootstrap_account_transaction_watch.py`
- `transformation_transactions.py`, `transformation_subscriptions.py`
- `transformation_budgets.py`, `transformation_loans.py`, `transformation_balances.py`
- `transformation_contract_prices.py`

**To `packages/domains/utilities/pipelines/`:**
- `utility_models.py`, `utility_bill_service.py`, `utility_bills.py`
- `utility_usage.py`, `utility_usage_service.py`
- `transformation_utilities.py`

**To `packages/domains/homelab/pipelines/`:**
- `homelab_models.py`, `transformation_homelab.py`
- `ha_bridge.py`, `ha_models.py`, `ha_mqtt_models.py`, `ha_mqtt_publisher.py`
- `ha_action_dispatcher.py`, `ha_action_proposals.py`, `ha_policy.py`
- `ha_service.py`, `ha_contract_renderer.py`
- `home_automation_models.py`, `transformation_home_automation.py`
- `infrastructure_models.py`, `transformation_infrastructure.py`

**To `packages/domains/overview/pipelines/`:**
- `overview_models.py`, `transformation_overview.py`
- `household_models.py`, `transformation_household.py`

**Remain in `packages/pipelines/` (platform-generic):**
- `promotion.py`, `promotion_registry.py`, `promotion_types.py`
- `transformation_service.py`, `transformation_domain_registry.py`, `transformation_refresh_registry.py`
- `lazy_transformation_service.py`
- `reporting_service.py`
- `pipeline_catalog.py`, `extension_registries.py`
- `csv_validation.py`, `file_format.py`
- `configured_csv_ingestion.py`, `configured_ingestion_definition.py`
- `config_preflight.py`
- `normalization.py`, `identity_strategy.py`
- `reconciliation.py`
- `run_context.py`
- `internal_platform_ingestion.py`

**Ambiguous (decide during implementation):**
- `builtin_packages.py`, `builtin_promotion_handlers.py`, `builtin_reporting.py` — contain household content behind "builtin" naming. Move household content to domains; keep platform-generic registration framework in place.
- `builtin_transformation_refresh.py` — similar pattern.
- `transformation_assets.py` — may be generic or domain-specific depending on contents.
- `contracts.py` — may be generic or domain-specific depending on contents.
- `asset_models.py`, `asset_register.py`, `asset_register_service.py` — may belong to a future "assets" domain or to finance.

#### WP-2: Clean `AppContainer` of household-specific fields

- **Type:** platform
- **Goal:** Platform container contains only generic platform fields
- **Exact scope:** Remove `service`, `subscription_service`, `contract_price_service`, `finance_pack` from `AppContainer`. Add generic `domain_services` accessor or move to household-specific container extension. Update callers.
- **Files affected:** `container.py`, `builder.py`, `app.py`, `runtime.py`, `runtime_support.py`, test helpers
- **Validation:** All tests pass. `AppContainer` can be instantiated with empty `capability_packs`.
- **Rollback:** Restore old typed fields.
- **ADR required:** No.
- **Dependencies:** WP-1.

### Group 2: Boundary clarification work

#### WP-3: Move `current_dimension_contracts.py` to domain packages

- **Type:** cross-cutting
- **Goal:** Remove household vocabulary from platform package
- **Exact scope:** Move dimension contract definitions to respective domain packages. Keep the `CurrentDimensionContractDefinition` dataclass in platform (it is the generic shape). Move the instances (`dim_account`, `dim_counterparty`, etc.) to domains.
- **Files affected:** `packages/platform/current_dimension_contracts.py`, domain manifests, `publication_contracts.py`
- **Validation:** All tests pass. Grep for household nouns in platform returns zero.
- **Rollback:** Move files back.
- **ADR required:** No.
- **Dependencies:** WP-1.

#### WP-4: Fix `shared/external_registry.py` domain imports

- **Type:** cross-cutting
- **Goal:** Shared layer has no imports from domain layer
- **Exact scope:** Change `external_registry.py` to accept capability packs as parameters instead of importing them. Update callers.
- **Files affected:** `packages/shared/external_registry.py`, callers in `apps/`
- **Validation:** All tests pass. Import boundary test confirms shared-to-domains is clean.
- **Rollback:** Restore imports.
- **ADR required:** No.
- **Dependencies:** None.

#### WP-5: Fix `publication_contracts.py` pipeline dependency

- **Type:** platform
- **Goal:** Platform publication contract builder does not import from pipelines
- **Exact scope:** Change `publication_contracts.py` to accept publication relations as parameters (injected by capability packs) instead of importing `builtin_reporting`.
- **Files affected:** `packages/platform/publication_contracts.py`, `builtin_reporting.py`, callers
- **Validation:** All tests pass. Platform has no pipeline imports.
- **Rollback:** Restore import.
- **ADR required:** No.
- **Dependencies:** WP-1.

#### WP-6: Promote source freshness evaluation to platform

- **Type:** platform
- **Goal:** Generic freshness evaluation is available to all domains without importing from finance
- **Exact scope:** Move `evaluate_source_freshness` and associated types from `packages/domains/finance/freshness.py` to `packages/platform/` or `packages/shared/`. Update finance domain to import from new location.
- **Files affected:** `packages/domains/finance/freshness.py`, new platform/shared location, test files
- **Validation:** All freshness tests pass from new location. Finance domain imports from platform.
- **Rollback:** Move back to finance.
- **ADR required:** No.
- **Dependencies:** None.

### Group 3: Boundary enforcement work

#### WP-7: Add import boundary enforcement tests

- **Type:** boundary-enforcement
- **Goal:** CI fails on future boundary violations
- **Exact scope:** Add 3 test functions to `test_architecture_contract.py`: (1) platform-to-domains forbidden, (2) platform-to-domain-pipelines forbidden, (3) shared-to-domains forbidden. Add vocabulary lint for platform package.
- **Files affected:** `tests/test_architecture_contract.py`
- **Validation:** Tests pass on clean state. Intentionally violating import causes failure.
- **Rollback:** Remove tests.
- **ADR required:** No.
- **Dependencies:** WP-1 through WP-5.

#### WP-8: Add pack-free boot smoke test

- **Type:** boundary-enforcement
- **Goal:** Prove the platform can boot without household code
- **Exact scope:** Test that constructs `AppContainer` with `capability_packs=()`, creates a FastAPI app, hits `/health` and `/ready`.
- **Files affected:** New test in `tests/`
- **Validation:** Test passes in CI.
- **Rollback:** Remove test.
- **ADR required:** No.
- **Dependencies:** WP-2.

### Group 4: Low-risk refactors

#### WP-9: Rename `builtin_*` pipeline files to clarify household ownership

- **Type:** cross-cutting
- **Goal:** Stop disguising household content as platform builtins
- **Exact scope:** Rename `builtin_packages.py` to `household_packages.py`, `builtin_promotion_handlers.py` to `household_promotion_handlers.py`, `builtin_reporting.py` to `household_reporting.py`. Update imports.
- **Files affected:** 3 files renamed, approximately 20 import updates
- **Validation:** All tests pass.
- **Rollback:** Rename back.
- **ADR required:** No.
- **Dependencies:** After WP-1 (or combined with WP-1).

### Group 5: Docs/process updates

#### WP-10: Add classification tags to ADRs and architecture docs

- **Type:** docs
- **Goal:** Every decision/architecture doc declares PLATFORM / APP / CROSS-CUTTING
- **Exact scope:** Add `**Classification:**` line to all docs in `decisions/` and `architecture/`.
- **Files affected:** Approximately 15 docs
- **Validation:** Grep confirms all docs have the tag.
- **Rollback:** Remove tags (harmless addition).
- **ADR required:** No.
- **Dependencies:** None.

#### WP-11: Create platform identity doc and contributor decision guide

- **Type:** docs
- **Goal:** Contributors and agents can answer "is this platform or app work?"
- **Exact scope:** Create `docs/platform/README.md` and `docs/platform/decision-guide.md`.
- **Files affected:** 2 new files, update `docs/README.md` index
- **Validation:** Review by a human unfamiliar with the boundary; they should be able to classify 5 example changes correctly.
- **Rollback:** Delete files.
- **ADR required:** No.
- **Dependencies:** WP-10 (tags provide context).

### Group 6: Later extraction-readiness work

#### WP-12: Domain pack API route extension hook

- **Type:** platform
- **Goal:** Domain packs can contribute API routes without editing `app.py`
- **Exact scope:** Add optional `register_api_routes(app, container)` callback to `CapabilityPack`. Have `create_app()` iterate over loaded packs. Move homelab/HA routes to homelab pack.
- **Files affected:** `capability_types.py`, `app.py`, `homelab/manifest.py`, `ha_routes.py`
- **Validation:** All tests pass. HA routes only appear when homelab pack is loaded.
- **Rollback:** Revert to hardcoded registration.
- **ADR required:** Maybe. Small enough to skip.
- **Dependencies:** WP-1, WP-2.

---

## 10. Execution plan

### Recommended first 5 work packages

1. **WP-1** — Split `packages/pipelines/` (the foundational move)
2. **WP-4** — Fix `shared/external_registry.py` domain imports (quick, independent)
3. **WP-2** — Clean `AppContainer` (enabled by WP-1)
4. **WP-7** — Add import boundary tests (locks the boundary)
5. **WP-10** — Add classification tags to docs (quick, independent)

### Execution order

```text
WP-4 (independent, quick)       ──┐
WP-6 (independent, quick)       ──┤
WP-10 (independent, quick)      ──┼── can start in parallel
WP-1 (foundational, largest)    ──┘
                                  │
WP-2 (needs WP-1)               ──┤
WP-3 (needs WP-1)               ──┤── after WP-1
WP-5 (needs WP-1)               ──┤
WP-9 (needs WP-1 or combined)   ──┘
                                  │
WP-7 (needs WP-1 through WP-5)  ──┤── after boundary cleanup
WP-8 (needs WP-2)               ──┘
                                  │
WP-11 (needs WP-10)             ──── after tags
WP-12 (needs WP-1, WP-2)       ──── later
```

### What not to combine into one sprint

- WP-1 should not share a sprint with WP-12. WP-1 is a large mechanical refactor; WP-12 introduces new protocol design. Mixing them risks scope creep.
- WP-7 should not precede WP-1. Enforcement tests added before the boundary is clean will just fail and be ignored.
- WP-11 should not precede WP-10. The decision guide references the classification tags.

---

## 11. Roadmap

### Near-term: Seam definition and boundary enforcement

**Objective:** Make the kernel/app boundary real in code and enforceable in CI.

**Why it matters:** Without this, every future sprint will continue mixing platform and household concerns. The ADR's 5-layer architecture will remain aspirational.

**Expected architectural outcomes:**

- `packages/platform/` has zero imports from domain code
- `packages/domains/` contains all household-specific transforms, models, and services
- Import boundary tests fail on violations
- Pack-free boot test passes

**Major workstreams:**

1. Split `packages/pipelines/` (PK-1 + AH-1)
2. Clean `AppContainer` (PK-2)
3. Move current-dimension contracts (PK-3)
4. Fix `publication_contracts.py` dependency (PK-4)
5. Fix `shared/external_registry.py` dependency (PK-5)
6. Promote source freshness to platform (PK-6)
7. Add import boundary tests (XC-1, XC-2)
8. Add pack-free boot test (XC-3)

**Risks:**

- Large file move (35+ files) can break import paths across tests. Mitigation: do it in one PR with thorough test run.
- Intermediate states where some domain code is moved but not all. Mitigation: move all domain pipeline files in a single batch per domain.

**Stop condition:** All import boundary tests pass. Platform package has zero household-term identifiers.

### Mid-term: Runtime, packaging, testing, and workflow separation

**Objective:** Make the kernel and app testable, documentable, and operable independently.

**Why it matters:** Boundary enforcement prevents drift, but actual independence requires the runtime to compose correctly without assuming the household app.

**Expected architectural outcomes:**

- Domain packs contribute their own API routes through an extension mechanism
- `create_app()` parameter list is reduced to platform-generic parameters
- Domain-specific pipeline registrations move into domain pack manifests
- Docs are reorganized into `docs/platform/` and `docs/apps/household/`
- Test fixtures are split into platform-generic and domain-specific sets

**Major workstreams:**

1. Domain pack API route extension protocol (D-1 promoted if needed)
2. Move "builtin" household registrations into domain packs (AH-2)
3. Documentation restructure (see Section 12)
4. Test fixture separation
5. HA integration encapsulation (AH-3)

**Risks:**

- API route extension protocol could become over-engineered. Mitigation: start with a simple `register_routes(app, container)` hook on `CapabilityPack`.
- Documentation refactor is large surface area. Mitigation: do it incrementally, starting with classification tags.

**Stop condition:** A new domain pack can be added by: (1) creating a manifest, (2) providing transforms/models/services within its package, (3) registering via the entrypoint. No platform files need editing.

### Later: Extraction-readiness and templateability

**Objective:** If evidence warrants it, make the kernel extractable into a separate repo/package.

**Why it matters:** Only matters if a second deployment target or community consumer appears.

**Expected architectural outcomes:**

- Kernel is a pip-installable package with its own `pyproject.toml`
- Household app is a template/example that depends on the kernel package
- CI can test kernel in isolation

**Major workstreams:**

1. Kernel packaging with its own `pyproject.toml`
2. Household app as a template project
3. Kernel documentation as standalone docs

**Risks:**

- Premature extraction wastes effort. Mitigation: only start when there is a real second consumer.
- Version coordination between kernel and app. Mitigation: monorepo until forced to split.

**Stop condition:** Do not start this until: (1) a second non-household domain app is actively developed on the kernel, or (2) an external contributor wants to use the kernel without the household app, or (3) the monorepo's CI/packaging overhead becomes a real bottleneck.

### What should remain shared for now

- Single `pyproject.toml` and single repo
- Single CI pipeline
- Single deployment image
- Shared test infrastructure

### What must be separated conceptually but can still live in one repo

- Import boundaries (enforced by tests)
- Documentation classification
- Sprint/backlog classification

### What should only be extracted later if evidence appears

- Separate pip packages
- Separate repos
- Separate deployment images

### Proof points that the split is becoming real

- Pack-free boot test passes
- A non-household domain pack can be loaded and tested
- Platform docs are usable without reading household docs
- New domain pack requires zero edits to platform code

---

## 12. Documentation realignment plan

### 12.1 Documentation gap assessment

| Gap | Severity |
|---|---|
| No `docs/platform/` directory: platform architecture is mixed into household docs | High |
| No explicit kernel identity document | High |
| ADRs have no classification tags | Medium |
| README presents everything as one product, not kernel + app | Medium |
| No contributor decision guide for platform vs app classification | Medium |
| Agent guidance docs do not distinguish platform vs app work | Low |
| Sprint docs do not classify work by layer | Low |

### 12.2 Target doc structure

```text
docs/
  platform/
    README.md                              "What is the kernel?"
    architecture.md                        Platform architecture (extracted from data-platform-architecture.md)
    capability-pack-contract.md            Pack registration, validation, lifecycle
    publication-contract.md                Publication semantics, field roles, rendering
    ingestion-contract.md                  Source, landing, evidence model
    storage-contract.md                    Control plane, blob, warehouse expectations
    extension-model.md                     Extension loading, function registry
    decision-guide.md                      "Is this platform work?" decision tree
  apps/
    household/
      README.md                            "What is the household app?"
      domains.md                           Finance, utilities, homelab, overview
      ha-integration.md                    HA bridge, MQTT, action dispatcher
      scenarios.md                         Scenario engine, what-if modeling
      product-scope.md                     Household Operating Picture (moved from product/)
  architecture/                            Existing, add classification tags
  decisions/                               Existing, add classification tags
  product/                                 Existing, becomes household-focused
  ...
```

### 12.3 Per-document update plan

| Document | Action | Classification |
|---|---|---|
| `architecture/data-platform-architecture.md` | Split: generic pipeline architecture to `docs/platform/architecture.md`; household-specific sections to `docs/apps/household/` | CROSS-CUTTING |
| `architecture/finance-ingestion-model.md` | Move to `docs/apps/household/` | APP |
| `architecture/publication-contracts.md` | Move to `docs/platform/publication-contract.md` | PLATFORM |
| `architecture/semantic-contracts.md` | Tag CROSS-CUTTING; reference both platform and household | CROSS-CUTTING |
| `architecture/homeassistant-integration-hub.md` | Move to `docs/apps/household/ha-integration.md` | APP |
| `architecture/integration-adapters.md` | Tag PLATFORM (adapter contract shape is generic) | PLATFORM |
| `architecture/simulation-engine.md` | Move to `docs/apps/household/scenarios.md` | APP |
| `architecture/agent-surfaces.md` | Tag APP (agent retrieval is household-specific for now) | APP |
| `decisions/household-platform-adr-and-refactor-blueprint.md` | Tag PLATFORM | PLATFORM |
| `decisions/household-operating-platform-direction.md` | Tag CROSS-CUTTING | CROSS-CUTTING |
| `decisions/operational-database-support-model.md` | Tag PLATFORM | PLATFORM |
| `product/core-household-operating-picture.md` | Tag APP | APP |
| `product/initial-capability-packs-and-publications.md` | Tag APP | APP |
| `README.md` | Rewrite to distinguish kernel from household app | CROSS-CUTTING |

### 12.4 Recommended first docs to update (in order)

1. Add classification tags to all existing ADRs (WP-10)
2. Create `docs/platform/README.md`: "What is the kernel?" in 1 page
3. Create `docs/platform/decision-guide.md`: the contributor/agent decision tree
4. Update root `README.md`: add a "Kernel vs Household App" section
5. Create `docs/apps/household/README.md`: "What is the household app?" in 1 page

### 12.5 Where docs currently overstate generality

- `data-platform-architecture.md` lists `dim_counterparty`, `fact_transaction`, `fact_subscription_charge` etc. as "recommended transformation outputs." These are household-specific outputs presented as universal recommendations.
- `publication-contracts.md` describes the publication system using household examples (cashflow, subscriptions) without noting these are app-level, not platform-level.
- The 11-stage roadmap mixes platform stages (6, 7, 8, 9) with household stages (2, 3, 4, 5) without labeling which is which.

### 12.6 Where docs hard-wire household assumptions

- `finance-ingestion-model.md` is in `docs/architecture/` but is entirely finance-domain-specific.
- `homeassistant-integration-hub.md` is in `docs/architecture/` but is HA-specific.
- `simulation-engine.md` is in `docs/architecture/` but describes household-specific scenario types.
- The product docs directory conflates platform product direction with household app direction.

---

## 13. Do-not-do-yet list

1. **Premature repo splitting.** The monorepo is the right shape. The kernel does not have a second consumer. Splitting now would double CI/release/versioning overhead for zero benefit.

2. **Broad framework extraction.** Do not extract a `homelab-platform-core` pip package. There is no second project that would install it.

3. **Fake-generic API rewrites.** Do not replace typed domain routes (`/api/reports/cashflow`) with a vague `/api/publications/{key}/data` generic query layer. The typed routes are better for the household app's actual users.

4. **Ontology-heavy rewrites.** Do not build a formal household ontology, dimension registry, or semantic catalog. The current typed dimension models work. The complexity is not worth it until 10+ domains exist.

5. **Heavyweight orchestration additions.** Do not add Airflow, Dagster, Prefect, or a distributed task queue. The worker CLI dispatch is adequate for the current scale.

6. **Replacing typed app surfaces with generic query layers.** The household app's publications have specific field semantics, UI descriptors, and rendering hints. Flattening these into `SELECT * FROM publication WHERE key = ?` would lose the product value.

7. **Using household use cases as sole proof of kernel generality.** "It works for finance and utilities" does not prove the kernel is general. Those are both part of the same household app. Generality is only proven when a non-household domain can boot on the kernel.

8. **Capability pack marketplace infrastructure.** No pack registry, no pack versioning protocol, no pack compatibility matrix. The four first-party packs do not need marketplace logistics.

9. **Multiple deployment images.** Do not build separate kernel/app Docker images. One image with pack selection at boot time is sufficient.

10. **Distributed system primitives.** Do not add message queues, event sourcing, CQRS, or saga orchestration. The single-process FastAPI + worker CLI model works.

---

## 14. Boundary rules

These rules should guide all future work and be enforced through the mechanisms in Section 7.

1. Platform/kernel concerns must be understandable without household vocabulary.
2. Household/app concerns must not be promoted into platform unless at least two plausible non-household apps/domains would need them.
3. Cross-cutting items must be called out explicitly rather than quietly smuggled into platform.
4. Avoid rewriting things into fake-generic abstractions unless repeated pain is clearly visible in code/docs/tests.
5. Prefer validating an explicit composition/registration seam over launching a broad "IoC rewrite."
6. Use household-specific terms appearing in platform code as a leak/smell test, not an absolute law.
7. Do not flatten useful typed app/publication surfaces into vague generic query APIs just to look more platform-like.
8. Prefer small, boring, enforceable changes over sweeping architecture reinvention.

---

## 15. Final recommendation

**Should the repo continue as one repo?** Yes. Unambiguously. There is no second consumer, no second deployment target, no team boundary that would benefit from repo separation. Stay monorepo.

**What should the kernel/app seam be called?** "Platform kernel" and "household app." Use these exact terms in docs, ADRs, PR classifications, and sprint items. The platform ADR already uses "platform core." Aligning to "platform kernel" is a trivial terminology update that makes the dual nature explicit.

**What is the single most important next refactoring move?** Split `packages/pipelines/` into platform-generic and domain-specific halves (WP-1). This single mechanical refactor:

- moves approximately 35 domain files into `packages/domains/`
- enables all downstream boundary enforcement
- makes the kernel independently testable
- converts the existing ADR's layer model from aspiration to reality
- is fully reversible and introduces no new abstractions

Everything else (container cleanup, doc restructure, enforcement tests) flows from this one move.

**What would count as evidence that future extraction is warranted?**

1. A second non-household domain app is actively developed on the kernel (e.g., a homelab infrastructure monitoring app that uses the ingestion/publication pipeline but not finance/utilities).
2. An external contributor or project wants to use the kernel without the household app.
3. The monorepo's CI time exceeds 10 minutes due to domain-pack test isolation failures.
4. A pack-free boot test passes and has been passing for 3+ sprints, demonstrating the kernel is genuinely independent.

Until at least one of these is true, extraction is premature optimization.

---

## Relationship to existing decisions

This plan extends the following accepted documents without replacing them:

- `docs/decisions/household-platform-adr-and-refactor-blueprint.md` — the 5-layer modular monolith and capability pack model. This plan identifies where the 5-layer model is not yet realized in code and produces the work packages to close the gap.
- `docs/decisions/household-operating-platform-direction.md` — the 11-stage roadmap. This plan adds classification (PLATFORM vs APP) to the stage model without changing stage content or ordering.
- `docs/architecture/data-platform-architecture.md` — the landing/transformation/reporting pipeline. This plan separates the generic pipeline engine from the household-specific transforms and models that flow through it.
