# Knowledge Base — homelab-analytics
Generated: 2026-04-22T19:40:49Z

## Decisions

### packages/analytics/ resolved as finance-internal; moved to finance domain (Option 1)
Source: sprint: 52
Tags: analytics, stratum, finance

analytics/cashflow.py imported CanonicalTransaction from finance domain internals with no evidence of cross-domain intent. Option 1 (move to packages/domains/finance/pipelines/cashflow_analytics.py, delete scaffold) was chosen over Option 2 (promote to semantic engine). Callers updated: account_transaction_service, api/support, extensions.py (string reference), test files. Repository and architecture contract tests updated. General rule: when a scaffold package has exactly one file and that file imports only from one domain, place it in that domain.

---

### Promote shared types to platform/kernel when two packs both need them
Source: sprint: 51
Tags: platform, type-sharing, source-freshness, stratum

SourceFreshnessSummary was needed by both finance-staying result types (ScenarioResult etc.) and overview-moving result types (TariffShockResult etc.). Neither could own it without creating a new import violation. Solution: promote to packages/platform/source_freshness.py — both packs import from platform, which is the correct stratum for primitives used by multiple layers. General rule: when a type is needed by two packs at the same stratum and neither can own it without violation, promote to platform/kernel.

---

### Cross-domain scenario builders belong in overview, not a new semantic-engine package
Source: sprint: 51
Tags: scenarios, stratum, pack-isolation, overview

Finance scenario_service.py was importing from homelab and utilities sibling packs (violation). The cross-domain builders (tariff shock, homelab cost/benefit) moved to packages/domains/overview/ because overview is the designated cross-domain composition layer. A new packages/scenarios/ semantic-engine package was rejected — it would have required stratum assignment, architectural registration, and added complexity without benefit. Rule: if a scenario builder spans multiple domain packs, it belongs in overview, not in any single pack and not in a new engine package.

---

### Derive canonical HA bridge ids from bridge instance and stable registry identifiers
Source: track: identity-mapping, sprint: 47
Tags: ha-bridge, identity, landing-contracts

Registry, state, event, and statistics landing projections now emit explicit canonical entity/device/area target ids derived from bridge_instance_id plus the stable HA-side registry keys. State and event batches now require entity_registry_id so downstream mapping does not fall back to rename-prone entity_id values.

---

### Pin HA bridge ingest contracts with dedicated architecture docs and full OpenAPI checks
Source: track: docs-verification, sprint: 47
Tags: docs, ha-bridge, contract-tests

The repo now has an architecture page for the shipped /api/ingest/ha-bridge surface, indexed from docs/README and linked from the Home Assistant integration hub doc. Contract coverage was extended from spot-checking two endpoints to asserting request-body schemas for registry, states, events, statistics, and heartbeat so future surface drift is caught in targeted tests.

---

### Use dedicated /api/ingest/ha-bridge endpoints for landing-first HA bridge payloads
Source: track: landing-contracts, sprint: 47
Tags: ha-bridge, landing-contracts, api-surface

Kept legacy /api/ha/ingest for transformation-table state ingest while landing-first bridge payloads use dedicated registry, states, events, statistics, and heartbeat endpoints that preserve raw JSON and validate canonical CSV projections.

---

### Isolate HA bridge ingest with ha-bridge:ingest scope and route-local guardrails
Source: track: auth-guardrails, sprint: 47
Tags: auth, ha-bridge, api-guardrails

The HA bridge endpoints now require an exact service-token scope separate from generic ingest paths, reject unsupported schema_version values in the shared payload models, and apply a lightweight per-bridge/per-endpoint in-process rate limiter that returns 429 with Retry-After to absorb bridge retry storms without broadening auth on unrelated ingest surfaces.

---

### Policy detail reads re-evaluate for freshness instead of serving cached results
Source: track: tracing, sprint: 25
Tags: ha-policy, evaluator, api-design

The policy detail endpoint should re-evaluate on request rather than serve cached _last_results so the returned policy state is never stale. This duplicates the full evaluation cost of the list endpoint, but that tradeoff is acceptable while policy evaluation remains cheap. If it becomes a bottleneck, add an explicit get_by_id path with a cache-miss check rather than weakening freshness guarantees.

---

### Use dedicated upstream and downstream lineage endpoints
Source: track: lineage, sprint: 25
Tags: lineage, api-design, control-plane

Bidirectional lineage is exposed as two dedicated endpoints rather than a single mode-switch parameter. GET /control/lineage/downstream handles source-to-publication lookup and GET /control/lineage/upstream handles publication-to-source lookup, which keeps query shapes simple and orthogonal. The target_name filter on /control/source-lineage remains the raw-record access path.

---

### Adapter trust levels are the primary safety boundary; operator review scales with trust level
Source: track: verification, sprint: 23
Tags: adapter-governance, trust-model, safety

Adapter governance uses three trust levels as the primary safety boundary. VERIFIED (platform-shipped) adapters require no operator review before activation. COMMUNITY (third-party) adapters require recommended review before production use. LOCAL (user-defined) adapters require mandatory operator review before any activation. This ensures responsibility scales with the degree of external verification, and is the mechanism that prevents unsafe or unreviewed adapters from silently entering production.

---

### Use claim start/done-from-claim and kind-all for kctl checks in sprint workflow
Source: track: tooling-ops, sprint: 29
Tags: sprintctl, kctl, workflow, agent-skills

After upgrading sprintctl/kctl, runbook and skills were updated to use claim start for atomic activation, done-from-claim for ownership-bound completion, and kctl review/status kind-all checks for full durable+coordination visibility. This ensures agents see the full pipeline state rather than only the durable stream.

---

### Frontend gating automation is now part of blocking verify-fast CI
Source: track: tests, sprint: 26
Tags: frontend-automation, ci, verify-fast

The accept/retry gating UI automation is now enforced in the blocking verification path by adding web-ui-test and including it in verify-fast. This turns frontend gating checks from advisory to merge-gating coverage.

---

### Dry-run upload flow enforces explicit accept/retry gating before ingestion
Source: track: guided-onboarding, sprint: 26
Tags: guided-onboarding, dry-run, upload

Guided onboarding uploads now require an explicit dry-run acceptance step before ingest proceeds. The flow surfaces row count, date range, and issues, keeps upload disabled until acceptance, and supports retrying dry-run to re-lock the gate until re-accepted.

---

### Storybook Playwright automation covers guided upload accept/retry gate
Source: track: tests, sprint: 26
Tags: guided-onboarding, frontend-automation, dry-run

Dedicated frontend automation for upload gating is implemented with a Storybook MSW scenario and Playwright interaction test. The test verifies upload stays disabled before acceptance, becomes enabled after acceptance, and is disabled again after retry until accepted once more.

---

### Detect-source now exposes publication unlock preview
Source: track: guided-onboarding, sprint: 26
Tags: guided-onboarding, upload, publication-preview

Use transformation-package metadata during upload target detection to surface both direct and derived publication unlocks in the guided wizard before ingest. This keeps onboarding guidance aligned with reporting-layer outputs without changing ingest paths.

---

### Guided upload can infer contract target from file format and headers
Source: track: guided-onboarding, sprint: 26
Tags: guided-onboarding, upload, contract-detection

Guided onboarding now routes dropped uploads by detecting format and matching header columns against configured source mappings and built-in targets. The API returns confidence-scored candidates and the web wizard preselects upload path and contract target.

---

### Moved finance service builders out of platform runtime builder into apps/runtime_support.
Source: track: finding-corrections, sprint: 28
Tags: wp-13, boundary, composition

SubscriptionService and ContractPriceService constructors now live in app composition helpers; platform builder no longer imports those domain services.

---

### Relocated current-dimension contract instances into an explicit app composition module.
Source: track: finding-corrections, sprint: 28
Tags: wp-15, composition, contracts

Canonical module is now packages/pipelines/composition/current_dimension_contracts.py; consumers were rewired and old module kept as compatibility shim.

---

### External registry sync validation now receives publication/current-dimension registrations via injection.
Source: track: finding-corrections, sprint: 28
Tags: wp-14, boundary, external-registry

packages/shared/external_registry no longer imports household reporting/current-dimension modules; API and worker registry sync callers supply relations/contracts explicitly.

---

### Consolidated publication-contract route composition hooks into one app-composition input module.
Source: track: carryover, sprint: 28
Tags: wp-12, route-composition, extensions

Added packages/pipelines/composition/publication_contract_inputs.py and rewired assistant/contract/export/registry/worker/HA renderer paths to consume shared registrations + relation-map helper.

---

### Align sprintctl/kctl guidance with payload-based events and id-scoped lookup commands
Source: track: naming-docs, sprint: 27
Tags: sprintctl, kctl, docs, agent-skills

Updated runbooks and sprint skills so sprintctl event add uses --payload JSON and structured state queries include explicit --id/--item-id selectors after CLI surface changes.

---

### Inject builtin capability packs into external registry sync instead of importing domain manifests in shared layer
Source: track: boundary-cleanup, sprint: 27
Tags: architecture, layer-boundary, external-registry

Refactored packages/shared/external_registry.py to accept builtin_packs as an explicit dependency and updated API/worker call paths to pass container capability packs. This removes shared-layer imports of packages.domains.* and keeps duplicate publication-key validation behavior through composition-layer wiring.

---

### Adopt explicit doc concern tags (PLATFORM/APP/CROSS-CUTTING) and concern-oriented docs index
Source: track: naming-docs, sprint: 27
Tags: documentation, architecture-boundary, governance

Tagged the ADR set and key runbooks/product docs with a Classification marker and added a concern-oriented starting-point split in docs/README.md to keep kernel vs household-app ownership explicit during future edits.

---

### Rename misleading builtin household pipeline modules to household_* with compatibility shims
Source: track: naming-docs, sprint: 27
Tags: naming, architecture-boundary, compatibility

Moved builtin_packages/reporting/promotion_handlers/transformation_refresh modules to household_* names and rewired imports across runtime, platform, storage, and tests. Added thin builtin_* shim modules that re-export household_* symbols to avoid import breakage while clarifying ownership semantics.

---

### Complete WP-10 tagging coverage by adding classification tags to all architecture docs and enforce with architecture test
Source: track: naming-docs, sprint: 27
Tags: documentation, wp-10, quality-gate

Added **Classification:** PLATFORM markers to every docs/architecture/*.md file and added a test assertion in tests/test_architecture_contract.py so future architecture docs must include a classification marker.

---

### WP-1a finance pipeline split: moved finance transforms/models/services into packages/domains/finance/pipelines with compatibility shims
Source: track: pipeline-split, sprint: 27
Tags: wp-1a, architecture-boundary, refactor

Relocated account/subscription/budget/loan/contract/transaction/scenario finance pipeline modules from packages/pipelines into packages/domains/finance/pipelines, rewired imports repo-wide to the domain namespace, and left thin packages/pipelines shim modules for compatibility so platform stays domain-agnostic through shim imports while the seam settles.

---

### WP-1b utilities pipeline split: moved utility transforms/models/services into packages/domains/utilities/pipelines with compatibility shims
Source: track: pipeline-split, sprint: 27
Tags: wp-1b, architecture-boundary, refactor

Relocated utility models, bill/usage services, and transformation logic from packages/pipelines into packages/domains/utilities/pipelines, rewired imports to the domain namespace, and preserved thin shims at old packages/pipelines paths for compatibility during transition.

---

### WP-1d overview pipeline split: moved overview marts/transforms into packages/domains/overview/pipelines with compatibility shims
Source: track: pipeline-split, sprint: 27
Tags: wp-1d, architecture-boundary, refactor

Relocated overview_models and transformation_overview from packages/pipelines into packages/domains/overview/pipelines, rewired transformation/reporting imports to the domain namespace, and preserved thin shim modules at the legacy paths for compatibility while the seam migration continues.

---

### WP-1c homelab/HA pipeline split: moved HA/homelab/infrastructure pipelines into packages/domains/homelab/pipelines with compatibility shims
Source: track: pipeline-split, sprint: 27
Tags: wp-1c, architecture-boundary, refactor

Relocated homelab, home-automation, infrastructure, and HA integration pipeline modules from packages/pipelines into packages/domains/homelab/pipelines; rewired runtime/reporting/API imports to the domain namespace; kept thin shim modules at legacy paths for compatibility; and moved AdapterRuntimeStatus to packages/platform so domain modules no longer import packages.adapters directly.

---

### WP-1e classified remaining ambiguous pipeline files with explicit APP/JUSTIFIED-MIXED rationale
Source: track: pipeline-split, sprint: 27
Tags: wp-1e, architecture-boundary, documentation

Added docs/architecture/pipeline-ambiguity-classification.md covering asset_models, asset_register, asset_register_service, transformation_assets, and contracts.py with rationale for current placement, and added an architecture test guard to keep this classification coverage explicit.

---

### WP-7 added import-boundary enforcement tests for platform/shared layers
Source: track: enforcement, sprint: 27
Tags: wp-7, architecture-boundary, tests

Added architecture tests that enforce packages/shared has no direct domain imports and packages/platform avoids homelab/overview domain pipeline modules; also rewired shared/extensions account-transaction inbox helper to use the pipelines shim path so shared-to-domains boundary remains clean.

---

### WP-8 added minimal-kernel boot smoke test for zero-pack container path
Source: track: enforcement, sprint: 27
Tags: wp-8, architecture-boundary, smoke-test

Added ApiMain test coverage that builds the platform container with capability_packs=() and verifies FastAPI /health and /ready respond successfully via create_app(container), proving the narrow kernel boot path works without domain pack registration.

---

### WP-2 removed domain-typed fields from AppContainer and shifted domain-service wiring to app composition.
Source: track: container-cleanup, sprint: 27
Tags: wp-2, container-cleanup, composition

Container no longer owns finance-specific typed services or finance_pack; API and worker startup now build account/subscription/contract-price services explicitly from shared stores while preserving legacy create_app behavior.

---

### Moved household current-dimension contract instances out of platform module into app-owned pipeline module.
Source: track: boundary-cleanup, sprint: 27
Tags: wp-3, contracts, platform-boundary

packages/platform/current_dimension_contracts.py now exposes only the generic CurrentDimensionContractDefinition shape; publication_contract assembly reads instance metadata from packages/pipelines/household_current_dimension_contracts.py.

---

### Platform publication-contract builder now consumes injected publication and current-dimension registrations instead of importing household pipeline registrations directly.
Source: track: boundary-cleanup, sprint: 27
Tags: wp-5, platform-boundary, registration-injection

build_publication_relation_map/build_publication_contracts/build_publication_contract_catalog now require caller-provided relation and current-dimension metadata; API routes, export tooling, HA contract renderer, and external-registry validation pass the household registrations explicitly.

---

### Promoted generic source-freshness evaluator from finance domain path into platform module.
Source: track: boundary-cleanup, sprint: 27
Tags: wp-6, freshness, platform

Added packages/platform/source_freshness.py as canonical home for source freshness assessment logic and converted packages/domains/finance/freshness.py into a compatibility re-export shim; tests now target platform location.

---

### Scope Sprint K compare-set follow-up to pair-set lifecycle only
Source: track: stage-4, sprint: 5
Tags: stage-4, scenario, compare-set, lifecycle

The Sprint K compare-set follow-up stays on the current pair-based model. Scope is limited to label rename, archived-set visibility in the compare UI, and restore/unarchive flow. Do not introduce multi-scenario membership or a new homelab ROI model in this slice. Widening to a multi-scenario compare model requires a dedicated sprint with its own acceptance criteria.

---

### Store compare sets in backend persistence, not browser localStorage
Source: track: stage-3, sprint: 5
Tags: stage-4, scenario, comparison, persistence

The scenario compare-set slice stores compare pairs in the scenario backend so the workflow is reusable across sessions and browsers. This replaces an earlier browser-local localStorage approach and keeps the compare page aligned with the existing scenario storage and auth model. Backend persistence ensures compare sets survive browser refreshes, are subject to the same auth boundaries as scenarios, and can be retrieved by any authorized client.

---

### Keep first homelab comparison slice frontend-only
Source: track: stage-3, sprint: 5
Tags: stage-3, homelab, frontend, reporting

Existing /api/homelab/services and /api/homelab/workloads rows are sufficient for the first value-vs-cost decision surface. Add derived comparison metrics in the homelab page component instead of introducing a new reporting helper or mart. This limits blast radius for the slice and keeps backend boundaries clean until a richer join is clearly needed.

---

### Build first homelab value-loop slice from existing reporting marts
Source: track: stage-3, sprint: 5
Tags: stage-3, homelab, value-loop, reporting

The initial homelab value-loop surface is deliberately built from existing reporting-layer service-health and workload-cost routes. This keeps the sprint slice narrow and leaves a dedicated cross-domain cost/benefit mart for the next increment if the model needs a stronger join or a new heuristic. Do not introduce new mart queries or reporting helpers until the existing routes have proven insufficient for the value-loop use case.

---

### Normalize planning states to good/warning/needs-action
Source: track: stage-3, sprint: 5
Tags: stage-3, reporting, state-indicators

Implement the Stage 3 structured state indicator slice by exposing a normalized state field on existing budget variance, budget envelope, budget progress, and affordability ratio outputs. Keep the domain-specific raw status fields for backward compatibility, but let the dashboard and budgets page render the shared normalized state. This makes the state model consistent across planning surfaces without breaking existing consumers.

---

### Mirror generated frontend contracts when Node is unavailable
Source: track: stage-3, sprint: 5
Tags: frontend, generated, tooling

Node and npm were unavailable in the workspace, so new budget-envelope API and publication contracts were mirrored into the generated TypeScript stubs by hand to keep the frontend types aligned with the OpenAPI and publication JSON exports. This is an acceptable fallback when the code-gen toolchain is not available, but the mirrored stubs must be kept in sync with the OpenAPI spec until a re-generation pass can run.

---

### Use the existing publication contract model as the semantic retrieval source of truth
Source: track: stage-10, sprint: 16
Tags: stage-10, publication-index, retrieval, contracts

Sprint N item #87 will expose a read-only semantic index under /contracts rather than inventing a parallel publication registry. The index is derived from the existing publication and UI descriptor contracts so assistant surfaces can retrieve publication metadata, renderer hints, and field semantics without bypassing the contract layer or landing/transformation internals.

---

### Add a read-only assistant answer route grounded in publication-backed reporting methods
Source: track: stage-10, sprint: 16
Tags: stage-10, assistant-surface, retrieval, reporting

Sprint N item #89 will expose a single /api/assistant/answer entrypoint that resolves finance, utilities, and operations questions from the semantic publication layer and reporting service. Responses will include explicit publication-index and report-path pointers so the assistant stays explainable, read-first, and proposal-only.

---

### Sprint M starts with runtime-boundary cleanup and adapter honesty
Source: track: stage-5, sprint: 15
Tags: runtime-boundary, adapter-boundary, ha, composition-root

Sprint L closed with a strong profile/onboarding/configuration lesson set. Sprint M should start by making API and worker startup honest about the shared runtime container, then extract the Stage 6 adapter boundary from the proven HA implementation.

---

### Shared runtime helper preserves worker kwargs while API owns postgres override
Source: track: stage-5, sprint: 15
Tags: runtime-boundary, helper-contract, reporting-mode

apps/runtime_support.py centralizes the shared builder logic, but it preserves the worker/control-plane keyword contract for transformation service construction. apps/api/main.py layers the postgres-specific ReportingAccessMode.PUBLISHED choice on top so API callers retain published reporting behavior while worker callers continue to use the shared warehouse default.

---

### Sprint M advances to Stage 6 adapter packet
Source: track: stage-6, sprint: 15
Tags: stage-6, adapter-boundary, ha-reference

With runtime-boundary cleanup closed, Sprint M moved to the adapter contract boundary work: codifying AdapterManifest, separating ingest/publish/action expectations, and using the HA integration as the reference mapping for the generic adapter layer.

---

### Stage 6 health packet uses one shared runtime-health vocabulary
Source: track: stage-6, sprint: 15
Tags: stage-6, health-model, typed-status, reporting

The adapter packet and HA hub docs now describe health/reporting as a shared vocabulary rather than three separate one-off payloads: enabled for participation, connected for live transport, last_*_at for the newest successful sync/publish/dispatch, and role-specific counters for operational health. Bridge, MQTT, and action surfaces keep their own typed fields, but the reporting shape stays coherent across the API.

---

### Make onboarding demo-first and action-oriented
Source: track: stage-0, sprint: 14
Tags: operator-onboarding, demo-first, freshness, remediation

The onboarding packet now ties demo bundle validation, one-source-at-a-time import, freshness reminders, and failed-run remediation into one operator story across finance source contracts and freshness workflow docs.

---

### Start with deployment profiles and freshness stories
Source: track: stage-0, sprint: 14
Tags: runtime-profiles, freshness, operator-onboarding, configuration

The first Sprint L packet focuses on the three blessed deployment profiles and the matching freshness workflow so docs, runtime defaults, and operator remediation guidance stay aligned across demo/dev, single-user homelab, and shared OIDC deployments.

---

### Use a concrete example bundle entrypoint for onboarding
Source: track: stage-0, sprint: 14
Tags: operator-onboarding, demo-first, examples, indexing

The demo-first onboarding path now has a single example-bundle README, explicit ordering for the finance source examples, and top-level docs index entries so operators can find the disposable validation flow without hunting across files.

---

### Separate supported defaults from override surfaces
Source: track: stage-9, sprint: 14
Tags: configuration, defaults, overrides, operability

The configuration runbook now groups blessed defaults by surface and labels legacy aliases, break-glass admin, trusted proxy, machine JWT, extensions, and secrets as compatibility or power-user override paths.

---

### Sprint J starts with Stage 1 carryover cleanup as the first active item
Source: sprint: 13
Tags: stage-1, dim_household_member, semantic-contracts, planning

The next sprint was seeded around the remaining Stage 1 carryover: `dim_household_member` cleanup, explicit reporting/publication follow-up, and the semantic-contract guidance that keeps future Stage 1 extensions out of vague backlog labels.

---

### Stage 1 carryover cleanup now stops at dim_household_member and publication semantics
Source: track: stage-1, sprint: 13
Tags: stage-1, dim_household_member, publication-semantics, roadmap

The remaining Stage 1 cleanup was narrowed to the single unfinished dimension plus the publication-semantic path. Infrastructure foundations are already landed and should stay out of the carryover backlog.

---

### Semantic-contract guidance is now explicit in tracked docs
Source: track: stage-1, sprint: 13
Tags: semantic-contracts, stage-1, publication, shared-dimensions

The Stage 1 contract cleanup now calls out shared-dimension promotion timing, explicit reporting/publication follow-up, and the remaining `dim_household_member` gap so future Stage 1 extensions stay out of vague backlog labels.

---

### Sprint K duplicate packets remain archival
Source: sprint: 12
Tags: sprint-k, backlog-cleanup, sprintctl, knowledge

Sprint #12 is complete, the older Sprint K packets remain archival noise in closed sprint records, and the live backlog should move to Sprint J rather than reusing the duplicate packets.

---

### Normalize duplicate Sprint K packets into the delivered record
Source: track: stage-3, sprint: 11
Tags: sprint-k, backlog-cleanup, sprintctl, documentation

Sprint K is delivered in sprint #12, so the older duplicate Sprint K records remain archival noise instead of open work. The active duplicate items were normalized to done, and the pending duplicate packets stay as historical placeholders in closed sprints because sprintctl does not allow pending -> done transitions directly. Keep duplicate Sprint K packets out of future backlog selection unless a dedicated cleanup sprint is created to reconcile sprint history.

---

### Keep homelab ROI decisions on a reporting-backed mart
Source: track: stage-4, sprint: 12
Tags: homelab, reporting, roi, decision-surface

The homelab ROI decision loop should live on a reporting-backed mart and be consumed through the reporting service contract instead of being recomputed in the app surface. This keeps the operator UI aligned with the reporting-layer boundary and gives the ROI cue a stable contract in both warehouse and published-reporting setups.

---

### Keep the homelab compare workflow anchored on the operator surface
Source: track: stage-4, sprint: 12
Tags: homelab, scenarios, compare, operator-surface

After a homelab cost/benefit scenario is created, the operator surface should keep the comparison loop reachable without forcing a separate list-first workflow. Inline summary rows, a direct compare CTA, automatic partner selection when possible, and compare-set saving should stay attached to the homelab flow so operators can move from scenario creation to pairwise evaluation with minimal navigation.

---

### Keep API startup wiring thin behind a shared HA startup helper
Source: track: stage-5, sprint: 9
Tags: api, composition-root, ha-startup

API startup assembly now delegates HA-specific runtime wiring to a private helper so the composition root stays thin and the shared startup path remains centralized.

---

### Type HA bridge and action status endpoints with explicit response models
Source: track: stage-6, sprint: 9
Tags: api, openapi, status-model

The HA bridge and action status endpoints now use explicit Pydantic response models, keeping OpenAPI and runtime payloads aligned while preserving the existing JSON behavior.

---

### Extract shared HA runtime status snapshots for policy and MQTT wiring
Source: track: stage-6, sprint: 9
Tags: api, ha-startup, status-model

Policy and MQTT startup closures now reuse shared bridge and approval status snapshot helpers so the runtime status shape stays consistent across consumers.

---

### Keep AdapterManifest separate from typed runtime-status snapshots
Source: track: stage-6, sprint: 9
Tags: architecture, stage-6, adapter-boundary

Adapter manifests stay static while runtime status snapshots stay separate and typed; HA health endpoints should project transport state into API-facing models instead of leaking raw dictionaries.

---

### Codify legacy auth-mode retirement policy in requirements and tests
Source: sprint: 8
Tags: auth, migration, requirements, tests

Capture the warning and error windows plus the strict guard contract in requirements and auth configuration tests before any further runtime cleanup work.

---

### Remove stale authMode fallback from the web login page
Source: sprint: 8
Tags: auth, frontend, identity-mode, web

The login page now keys entirely off canonical identity mode and no longer accepts a legacy authMode branch for generic OIDC error rendering. This keeps the frontend contract aligned with the migrated runtime posture.

---

### Remove the generic OIDC fallback branch from the web login page
Source: sprint: 8
Tags: auth, frontend, oidc, identity-mode

The login page now treats explicit OIDC error cases only and no longer performs a generic auth-mode-based fallback for unknown errors. That keeps the frontend aligned with the canonical identity-mode contract and avoids carrying legacy auth-mode semantics into the UI.

---

### Remove legacy auth-mode-only create_app bootstrap support
Source: sprint: 8
Tags: auth, api, bootstrap, identity-mode

Direct API app construction now requires explicit identity_mode when a non-disabled auth mode is intended. This keeps the remaining compatibility boundary at settings ingestion and avoids keeping auth-mode-only bootstrap paths alive in app construction.

---

### Stop special-casing legacy auth_mode in web runtime env propagation
Source: sprint: 8
Tags: auth, web, identity-mode, cleanup

The web entrypoint no longer strips HOMELAB_ANALYTICS_AUTH_MODE from the child environment. The runtime contract now only sets HOMELAB_ANALYTICS_IDENTITY_MODE explicitly and leaves unrelated inherited env keys untouched, keeping legacy compatibility behavior confined to configuration ingestion boundaries.

---

### Tighten break-glass validation to identity-mode wording
Source: sprint: 8
Tags: auth, validation, identity-mode, cleanup

The auth configuration error for break-glass outside local_single_user now references HOMELAB_ANALYTICS_IDENTITY_MODE only. This keeps the user-facing contract aligned with the canonical identity-mode path and removes a remaining legacy auth-mode mention from runtime validation messaging.

---

### Canonicalize web auth env propagation
Source: track: stage-9, sprint: 8
Tags: auth, web, identity-mode, runtime-contract

Web workloads now strip legacy HOMELAB_ANALYTICS_AUTH_MODE before launch and propagate only HOMELAB_ANALYTICS_IDENTITY_MODE into the Next.js runtime so the frontend contract stays on the canonical identity-mode input.

---

### Align auth decision record with implemented machine JWT runtime
Source: track: stage-9, sprint: 8
Tags: auth, machine-jwt, docs, architecture

The architecture decision record now describes machine JWT federation as an implemented optional upstream bearer path that reuses the existing permission kernel, matching the runtime and test coverage already in the repository.

---

### Keep utility provider pulls on configured HTTP CSV landing
Source: track: stage-1, sprint: 4
Tags: utilities, ingestion, freshness

Utility-provider pulls should reuse the configured HTTP CSV landing path instead of introducing a provider-specific transport. Freshness policy belongs in source-freshness configuration so transport, authentication, and reminder logic stay decoupled.

---

### Model infrastructure metrics with SCD dimensions plus raw facts
Source: track: stage-1, sprint: 4
Tags: infrastructure, scd, duckdb

Infrastructure metrics should model nodes and devices as SCD-capable dimensions while retaining separate raw fact tables for cluster metrics and power consumption. Historical metadata changes belong in dimensions; measured evidence belongs in facts for later marts and reporting.

---

### Standardize release governance on main-only branches and versioned releases
Source: sprint: 4
Tags: release-policy, github, git, docs

Repository release governance uses main-only long-lived branch flow, annotated semantic-version tags, and GitHub Releases only for version tags. Sprint checkpoint tags remain internal markers and should not create public GitHub Releases.

---

### Publish current dimensions through reporting-layer registries
Source: track: stage-1, sprint: 4
Tags: home-automation, reporting, current-dimension, publication

App-facing current-dimension access should go through reporting-layer registries when a published current view exists. This preserves the landing/transformation/reporting split and avoids adding new landing-to-dashboard shortcuts for current-dimension reads.

---

### Treat balance snapshots as transformation facts
Source: track: stage-1, sprint: 4
Tags: fact_balance_snapshot, stage-1, transformation

Balance snapshots belong in the transformation layer as DuckDB-backed facts derived from balance evidence and repayment history. They should not remain vague carryover scope or be modeled as reporting-only shortcuts.

---

## Patterns

### Surface terminal command allowlist in the main control panel so admins can discover without entering the retro shell
Source: track: operator-tools, sprint: 34
Tags: frontend, terminal, control, discovery, admin-ux

Admin-facing command libraries are only useful if operators can find them without first knowing where to look. The terminal command allowlist (getTerminalCommands()) was already exposed via backend.ts and consumed in the retro shell. Adding it to the main /control page Promise.all (with .catch(() => []) for graceful degradation) and rendering a usage/description/mutating table gives admins a reference in their primary workflow context. Link to /retro/terminal for actual execution. Use .catch(() => []) on non-critical API calls within Promise.all to prevent degraded-endpoint failures from 500ing the whole admin page.

---

### Pass scenario row to is_stale_fn to avoid re-querying in comparison impl helpers
Source: sprint: 52
Tags: helpers, stale-check, impl-pattern

Comparison impl helpers (like _get_income_cashflow_comparison_impl) pass the scenario dict to is_stale_fn(store, scenario_id, scenario_row) so that callers with extra context (e.g. tariff utility_type from scenario["subject_id"]) can use it without a second get_scenario query. Callers that dont need scenario fields use lambda s, sid, _sc: .... Generalises to any impl helper where dispatch depends on a scenario field.

---

### RSA helper extraction direction: add to finance, import into overview
Source: sprint: 51
Tags: helpers, rsa, import-direction, finance, overview

The 4 RSA helpers (_insert_dim_scenario, _build_assumptions_summary, _get_scenario_baseline_run_id, _project_cashflow_rows) were defined in scenario_service.py and imported into scenario_service_overview.py. This direction is correct: overview already imports from finance, so adding helpers to finance and importing them in overview is valid. The reverse (overview exporting to finance) would create a circular import since finance is a lower stratum. General rule: shared helpers between finance and overview should live in finance and be imported by overview.

---

### Expose finance helpers to overview by renaming _ to public, not duplicating
Source: sprint: 51
Tags: helpers, pack-boundary, naming

When a finance-internal helper (_prefixed) is needed by overview for cross-domain builders, rename it to public (remove underscore) rather than duplicating logic or creating a new public wrapper. The public name signals intentional shared API surface. Applied to _get_baseline_cashflow -> get_baseline_cashflow and _get_latest_transaction_run_id -> get_latest_transaction_run_id.

---

### Adapter pack registration and activation are decoupled; only active packs are operator-visible
Source: track: verification, sprint: 23
Tags: adapter-lifecycle, registry-design, operator-workflow

AdapterPack registration and activation are two separate lifecycle steps. Registration stores pack metadata and marks the pack inactive by default. Activation is a separate explicit step that marks the pack ready for use. Only active packs are returned by list_packs(active_only=True) and surfaced via the API. This design enables safe operator review workflows: register → inspect → check compatibility → activate when ready. It prevents newly registered packs from becoming immediately operator-visible before review.

---

### Use raw landing for JSON-backed internal connectors
Source: track: stage-1, sprint: 4
Tags: ingestion, landing, prometheus, home-assistant

Prometheus and Home Assistant API responses should land unchanged through raw-byte landing, while connector-specific validation can run against a projected tabular contract. This preserves immutable upstream evidence in landing and keeps normalization concerns out of the bronze payload.

---

## Lessons

### Completed page implementations need explicit nav integration — /onboarding was fully built but unreachable
Source: track: onboarding, sprint: 34
Tags: frontend, onboarding, nav, operator-ux

A page can be fully implemented — complete with wizard, checklist, and progressive disclosure — yet still be effectively unreachable if it is not added to the navigation. When closing operator-facing onboarding work, verify that all new or substantially updated pages are wired into navItemsForUser() at the appropriate role threshold. The /onboarding page was gated at operator level (hasRequiredRole(user, 'operator')) and needed to be added alongside Sources and Upload.

---

### Re-use ONBOARDING_SOURCES upload-path map at the run detail boundary for failed-run remediation
Source: track: remediation, sprint: 34
Tags: frontend, remediation, run-detail, operator-ux

When a run fails or is rejected, the run detail page needs a direct path back to the correct upload form. ONBOARDING_SOURCES already contains the dataset→uploadPath mapping used by /onboarding and /sources. Derive DATASET_UPLOAD_PATH from it at module scope in the run detail page and show 'Upload corrected file' when run.status is rejected or failed. Also add a fallback 'Source remediation' ghost button pointing to /sources for datasets without a known upload path. Button priority: if retry is also available (canRetry), demote 'Upload corrected file' to ghostButton to avoid competing primary actions.

---

### Single-file parallel dispatch produces no isolation benefit
Source: track: ui, sprint: 59
Tags: dispatch, frontend, worktree, coordination

Dispatching two agents to edit the same file in parallel worktrees does not produce actual isolation — both agents resolve the given absolute path to the same file in the main working tree and interleave writes. Parallel dispatch only pays for frontend work when agents own strictly separate files (e.g. separate component files per feature). Single-file changes should be serialised or handled by one agent. For multi-agent UI work: split by file boundary, not by section of the same file.

---

### SQLite + shared auth is a hard guardrail, not a warning
Source: track: guardrail, sprint: 58
Tags: storage, guardrails, postgres-first

When auth mode is oidc or proxy (shared deployment postures), using SQLite as the control-plane backend should be a hard ValueError, not a RuntimeWarning. A warning can be silently swallowed in production startup logs; a ValueError surfaces immediately. The generic postgres_dsn (shared with reporting) intentionally does not trigger automatic postgres inference for the control plane — operators must set HOMELAB_ANALYTICS_CONTROL_PLANE_DSN explicitly. Advisory warnings for this gap are appropriate; errors are not.

---

### Frontend tsc runs without .bin symlinks via direct node invocation
Source: sprint: 48
Tags: frontend, node_modules, typecheck, tsc, blocker-recovery

When apps/web/frontend/node_modules/.bin is absent (symlinks not created) but node_modules/typescript/bin/tsc exists, the TypeScript compiler can still run as: node ../node_modules/typescript/bin/tsc --noEmit from the frontend directory. The hoisted TypeScript package in apps/web/node_modules is also a fallback. This unblocks the typecheck gate without needing npm ci to complete. npm run typecheck will still fail since it needs the .bin symlink, but the compilation check can proceed.

---

### Key confidence dashboard domain grouping by publication_key
Source: track: dashboard, sprint: 25
Tags: control-plane, confidence-dashboard, bug-fix, domain-grouping

Confidence dashboard domain grouping must be keyed by publication_key rather than publication_definition_id when looking up snapshot metadata. The earlier mismatch silently collapsed all publications into the platform default, so grouping logic should use the same identifier family end-to-end and delete fallback code that appears to work only because the lookup is broken.

---

### Persist claim tokens to disk for sprint-item recovery
Source: track: coordination, sprint: 39
Tags: coordination, claims, workflow, recovery

Claim tokens must survive session resets. The orchestrating session should keep the token in memory during normal execution and persist it to .sprintctl/claims/claim-<item_id>.token as a crash-recovery path. Reattach flows should read the token file first, and subagents must never receive the claim token directly.

---

### Two-pass delivery: scaffold fields first, wire population in same sprint
Source: track: tracing, sprint: 31
Tags: sprint-discipline, scaffold-pattern, delivery-style

Observed across proof-grain-veil and forge-amber-lens: implementer adds model/field in a first pass commit, leaves the population wiring for a follow-up commit in the same sprint. This is a valid delivery style — it keeps commits atomic and reviewable — but it requires explicit reviewer awareness. When scoping sprint items, mark the second-pass wiring step as a named deliverable (not implied by the first), and during review check whether fields default to None before approving the scaffold commit as done.

---

### Update verification-tooling contract tests when verify-fast target list changes
Source: track: tests, sprint: 26
Tags: tests, workflow, verify-fast

Verification tooling tests assert the exact verify-fast target chain. Any Makefile verification-surface change must update tests/test_verification_tooling.py in the same change to keep CI signal aligned with intended policy.

---

### Contract changes require OpenAPI export and frontend codegen refresh
Source: track: guided-onboarding, sprint: 26
Tags: contracts, openapi, workflow

When ingest endpoints or route contracts change, contract-export and frontend codegen must be refreshed in the same change. verify-fast catches drift through contract-export-check and web codegen checks.

---

### Storybook JSX runtime may need explicit React import in client components
Source: track: tests, sprint: 26
Tags: storybook, frontend-tests, workflow

Client components that rely on Next.js runtime behavior can fail in Storybook/Vite with React-is-not-defined unless React is explicitly imported in JSX files. Add explicit React imports when introducing Storybook automation for such components.

---

### Upload preview must report canonical target coverage
Source: track: guided-onboarding, sprint: 26
Tags: guided-onboarding, mapping-preview, ux-correctness

For configured CSV detection, source-header overlap is not equivalent to canonical-field readiness. Preview surfaces must show canonical target coverage from mapping rules (including defaults) and treat source-header matches as separate evidence.

---

### API-level fixture tests harden source detection without UI e2e overhead
Source: track: tests, sprint: 26
Tags: tests, guided-onboarding, source-detection

Source-detection behavior is verified through API fixture tests (configured CSV + HA states JSON + negative cases), which provides durable regression coverage without requiring a new UI e2e harness.

---

### Claim proof handling must preserve claim_token for lifecycle operations
Source: track: guided-onboarding, sprint: 26
Tags: claims, coordination, handoff

Claim ownership in sprintctl is enforced by claim_id plus claim_token. If token persistence is lost, lifecycle operations (status updates, handoff, release) can block even when identity metadata matches; preserve token immediately after claim create.

---

### Require claim token or explicit handoff before mutating exclusively claimed items
Source: sprint: 5
Tags: sprintctl, claims, coordination

If a sprint item has an exclusive claim, do not normalize its status just because the actor label matches a familiar agent. Wait for the claim token, a valid handoff via sprintctl claim handoff, or claim expiry before mutating the item state. Actor label matching alone is insufficient proof of ownership and can result in two agents mutating the same item concurrently.

---

### Use repo toolchain for web verification, not host shell tools
Source: track: stage-3, sprint: 5
Tags: verification, tooling, frontend

The host shell does not expose node or pytest, but the repository bundles the Node runtime under .tooling and the Python environment under .venv. For frontend changes, prefer make verify-fast over ad hoc system checks so verification matches the repo contract. Running verification outside the repo toolchain risks false-green results when host tool versions differ from the project-pinned versions.

---

### Select next sprint work from live sprintctl state first
Source: sprint: 12
Tags: sprintctl, workflow, handoff, process

The sprint closeout exposed that duplicate historical packets and stale tracker entries are easy to confuse with active work; future sprint selection should start from live sprintctl state, then use docs and snapshots as supporting context.

---

### Require explicit claim proof for item transitions
Source: track: stage-9, sprint: 8
Tags: claims, coordination, ownership

An exclusive claim blocked the transition because no valid claim proof was supplied.

---

### Claimed sprint items require claim proof for status transitions
Source: track: stage-1, sprint: 4
Tags: sprintctl, claims, coordination

When a sprint item has an exclusive claim, matching actor or workspace metadata is not enough to mutate its status. Status transitions must carry the originating claim proof, including the claim id and claim token, or the operation should fail and be handed off explicitly.

---
