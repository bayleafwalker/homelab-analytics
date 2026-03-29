# Knowledge Base — homelab-analytics
Generated: 2026-03-29T11:02:53Z

## Decisions

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
