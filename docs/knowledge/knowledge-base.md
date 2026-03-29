# Knowledge Base — homelab-analytics
Generated: 2026-03-29T17:15:19Z

## Decisions

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

### Use raw landing for JSON-backed internal connectors
Source: track: stage-1, sprint: 4
Tags: ingestion, landing, prometheus, home-assistant

Prometheus and Home Assistant API responses should land unchanged through raw-byte landing, while connector-specific validation can run against a projected tabular contract. This preserves immutable upstream evidence in landing and keeps normalization concerns out of the bronze payload.

---

## Lessons

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
