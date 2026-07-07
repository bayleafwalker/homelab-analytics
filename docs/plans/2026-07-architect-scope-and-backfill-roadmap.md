# Solutions-Architect Scope, Use Cases, and Backfill Roadmap — July 2026

**Date:** 2026-07-07
**Classification:** ARCHITECTURE — CROSS-CUTTING
**Status:** Backlog dispatch source. Every sprint proposed here is registered in remote `sprintctl` with `kind=backlog`.

## 1. Purpose

Take a full pass over homelab-analytics as a solutions architect: name the target application shape, name the supported use cases, name the architectural functionalities still required to reach that shape, and turn each remaining architectural gap into a backlog sprint with entry/exit criteria. The follow-on implementation session plan is `docs/plans/2026-07-implementation-session-plan.md`.

This document does not restate the 11-stage roadmap (`docs/plans/household-operating-platform-roadmap.md`). It compares intent to code as of 2026-07-07 and closes the delta.

## 2. Application shape

homelab-analytics is a self-hosted **household operating platform**. Its shape is fixed as:

- Modular monolith with four stability strata: **kernel**, **semantic engine**, **product packs**, **surfaces**.
- Bronze/silver/gold data flow through explicit `landing/`, `transformation/`, `reporting/` layers with SCD-2 dimensions and publication-backed marts.
- Four built-in capability packs — finance, utilities, homelab, overview — with an extension model for external packs.
- Postgres canonical for control-plane + published reporting; DuckDB for worker/local analytical warehouse; SQLite for local bootstrap.
- Auth-in-app authorization sitting behind OIDC, service tokens, and a narrow local break-glass mode.
- Home Assistant as a first-class integration partner (edge runtime, action surface, delivery surface), not a substitute.

Nothing in the application shape changes with this plan. The gaps below are inside this shape.

## 3. Supported use cases (target scope)

The application must support these operator loops end-to-end. Where a loop is not yet supported end-to-end, the relevant sprint appears in §6.

| # | Use case | Primary surfaces | End-to-end status |
|---|---|---|---|
| U1 | Ingest a personal finance source (bank CSV, credit card PDF, loan registry) and see monthly cashflow, budgets, loans | worker CLI, `/reports`, `/budgets`, `/loans` | Shipped |
| U2 | Ingest utility bills and tariffs and see cost, usage-vs-billing, renewal candidates | worker CLI, `/reports/utility` | Shipped |
| U3 | See a unified household cost model + affordability ratios + recurring-cost baseline | `/reports/costs`, overview | Shipped |
| U4 | Run finance/utility/homelab scenarios (loan what-if, income change, expense shock, tariff shock, homelab cost/benefit) and compare saved sets | `/scenarios`, saved compares | Shipped |
| U5 | Author a policy without editing Python, have it evaluate against published state, and see the result as an HA synthetic entity | `/control/policies`, HA MQTT | Shipped (Stage 5 acceptance verified in code) |
| U6 | Approve or dismiss an HA-gated action from either HA or the web app | `/homelab`, HA notification | Shipped |
| U7 | Ingest cluster and home-automation state and reason about uptime, cluster utilization, infra cost, climate, automation reliability, device battery | worker CLI, `/reports/homelab` | Partial — dimensions/facts exist; 10 planned marts missing (§5.6) |
| U8 | Discover and consume publications from a non-web renderer (HA card, PDF export, agent tool) without knowing internal schemas | renderer registry, MCP tools | Partial — renderer router + semantic hints exist; formal external index does not |
| U9 | Install a third-party pack, verify compatibility with the running platform, activate it, upgrade it, roll it back on failure | pack registry, admin UI | Not shipped — manifest + lifecycle missing |
| U10 | Trace a published figure back to its source runs, transformations, and assumptions | lineage graph API + UI | Partial — lineage edges recorded; graph traversal + UI missing |
| U11 | See a single confidence view across all publications (freshness, completeness, verdict) | confidence dashboard | Partial — model exists; dashboard does not |
| U12 | Back up the platform to portable storage and restore it on a new host without loss | backup CLI + docs | Not shipped |
| U13 | Ask an assistant a household question grounded in publications, receive an answer with lineage, and receive a proposed action that requires approval | agent tool surface | Not shipped |
| U14 | Deploy the platform to the `appservice` Kubernetes cluster with OIDC and Postgres | Helm chart, cluster runbook | Not shipped — chart exists; live deployment does not |
| U15 | Observe the platform's own health and error budget as an operator, not just its outputs | self-observability dashboard | Partial — Prometheus metrics exist; no self-SLO dashboard |

## 4. Architectural functionalities still required

Grouped by capability area. Each item maps to at least one sprint in §6.

### 4.1 Integration adapter maturation (Stage 6)
- Credential-requirement declaration to concrete secret-resolver abstraction (not per-adapter env parsing).
- Multi-adapter entity correlation and deduplication contract, so the same physical device seen through HA and directly via MQTT resolves to one canonical entity.
- Second concrete `IngestAdapter` beyond the HA reference (Prometheus federation is the highest-value candidate; already implements the Renderer contract, needs the ingest side).

### 4.2 Semantic delivery layer (Stage 7)
- Formal external semantic publication index — publications expose semantic role, unit, grain, aggregation, filterability, sortability to any renderer without reading internal schemas.
- Content negotiation via Accept-header for renderer selection, including a version handshake for breaking schema changes.

### 4.3 Pack ecosystem (Stage 8)
- Unified `PackManifest` covering domain, reporting, and automation packs (today only `AdapterPack` exists for adapter/renderer bundles).
- Compatibility verification against `requires_platform_version` and declared dependencies.
- Pack lifecycle: install → activate → upgrade → deactivate → rollback, with a pre-upgrade contract check.
- Pack contract testing harness so a pack advertising `publication_relations` is verified against its declared schema at load time.

### 4.4 Trust, lineage, and governance (Stage 9)
- Lineage graph query API traversing source runs → landing rows → transformations → published relations, plus a viewer.
- Operator confidence dashboard aggregating freshness, completeness, and verdict across every publication.
- Decision lineage for planning and simulation — every projection points at the assumptions that produced it.
- Backup, restore, and portability CLI + runbook, covering control-plane Postgres, DuckDB warehouse, blob storage, and secrets model.

### 4.5 Agentic surface (Stage 10)
- LLM-shaped semantic index over publications (descriptions, schemas, examples) built from Stage 7 metadata.
- MCP tool definitions covering read (retrieval), scenario proposal, and policy proposal.
- Action-proposal workflow generalized beyond the HA-specific approval queue.

### 4.6 Domain mart backfill
Ten planned marts from `docs/plans/additional-data-domains.md` remain unimplemented. Their absence blocks U7 and weakens U4 for cross-domain scenarios.

Missing: `mart_energy_daily`, `mart_infra_cost`, `mart_uptime_summary`, `mart_cluster_utilization`, `mart_asset_value`, `mart_depreciation_schedule`, `mart_climate_summary`, `mart_automation_reliability`, `mart_device_battery`, `mart_subscription_changes`, `mart_debt_overview` (partially covered by `mart_loan_overview` but not aggregated across debt types).

### 4.7 Operations
- First real deployment to the `appservice` cluster following `docs/notes/appservice-cluster-integration-notes.md`.
- Platform self-observability: SLOs, error budget, self-metrics dashboard alongside product metrics.

## 5. What is explicitly **not** in scope

Scoped out per prior refinements (`docs/plans/2026-06-backlog-refinement-dispatch.md` §4) and reaffirmed here:

- Home Assistant add-on repository split.
- Public marketplace / registry activation with rollback of externally hosted packs (kept to local + Git discovery for now).
- Generic cross-backend query abstraction beyond the existing Postgres/DuckDB/SQLite split.
- Multi-tenant / multi-household mode. `local_single_user` and OIDC single-household remain the deployment shapes.

Adding any of these later requires a new architect pass and its own dispatch plan.

## 6. Backlog sprints (registered in remote `sprintctl`)

Each sprint is created with `--kind backlog` and 2–4 items. Sprint IDs are assigned at registration time and appended below by the operator after registration.

| # | Sprint ID | Codename | Focus | Uses | Depends on |
|---|---|---|---|---|---|
| B1 | #389 | `veil-secret-loom` | Stage 6 — credential abstraction + multi-adapter correlation contract | U8 pre-req | — |
| B2 | #390 | `prom-ingest-second` | Stage 6 — second concrete `IngestAdapter` (Prometheus federation) | U7 partial, U8 | B1 |
| B3 | #391 | `render-semantic-atlas` | Stage 7 — external semantic publication index + Accept-header content negotiation | U8, U13 | — |
| B4 | #392 | `pack-manifest-forge` | Stage 8 — unified `PackManifest`, compatibility verification, contract test harness | U9 | B3 |
| B5 | #393 | `pack-lifecycle-loom` | Stage 8 — install/activate/upgrade/deactivate/rollback with pre-upgrade check | U9 | B4 |
| B6 | #394 | `lineage-graph-lantern` | Stage 9 — lineage graph traversal API + viewer | U10 | — |
| B7 | #395 | `confidence-canvas-glow` | Stage 9 — operator confidence dashboard + decision lineage for scenarios | U11 | B6 |
| B8 | #396 | `portability-anchor` | Stage 9 — backup, restore, portability CLI + runbook | U12 | — |
| B9 | #397 | `agent-surface-mcp` | Stage 10 — LLM semantic index + MCP tools + generalized action proposal | U13 | B3, B6 |
| B10 | #398 | `domain-marts-fillout` | Backfill — 10 missing marts across infra, home-automation, assets, subscriptions | U7 | — |
| B11 | #399 | `appservice-first-deploy` | Ops — first live deployment to `appservice` cluster | U14 | — |
| B12 | #400 | `self-observ-canvas` | Ops — self-SLOs, error budget, self-metrics dashboard | U15 | B11 |

Sprint items and acceptance contracts are recorded in remote `sprintctl` at registration and mirrored briefly in §7.

## 7. Sprint items (as registered)

Format: `sprint codename — track — item title — acceptance`.

### B1 `veil-secret-loom`
- `credentials` — Extract credential-requirement resolution into a `SecretResolver` protocol under `packages/platform/adapter_secrets/` with env, file, and control-plane secret backends. Acceptance: HA + Prometheus + export renderer all resolve credentials through the resolver; direct `os.environ` reads under `packages/adapters/` are removed.
- `correlation` — Define `EntityCorrelationContract` in `packages/adapters/contracts.py` (canonical entity key + adapter-scoped alias table) and add a correlation registry with a deterministic tie-breaker on `TrustLevel`. Acceptance: two adapters can register the same physical device and reads through either surface the same canonical entity id.

### B2 `prom-ingest-second`
- `ingest` — Implement `PrometheusIngestAdapter` (federation or remote-read) implementing `IngestAdapter` protocol, landing infra cluster metrics into `fact_cluster_metric`. Acceptance: adapter passes the standard adapter contract test suite; a config-driven ingest binding produces `fact_cluster_metric` rows in a smoke test.
- `wiring` — Register the adapter in the extension registry and expose a health snapshot through `/api/adapters/*/status` using the shared runtime snapshot pattern. Acceptance: status route returns typed health for the Prometheus adapter with the same shape as the HA adapters.

### B3 `render-semantic-atlas`
- `index` — Publish a `/api/semantic-index` endpoint returning each publication's semantic role, unit, grain, aggregation, filterability, sortability. Acceptance: an external consumer can list publications and their semantic hints without reading internal schemas.
- `negotiation` — Accept-header negotiation in `RendererRouter` with an explicit `X-Publication-Version` handshake; unknown versions return 406. Acceptance: renderers can advertise supported versions and the router picks a compatible pair or refuses.

### B4 `pack-manifest-forge`
- `manifest` — Introduce `PackManifest` covering domain, reporting, automation, and adapter packs; move `AdapterPack` to a specialization. Acceptance: existing HA reference bundle loads under the new manifest without behavior change.
- `compat` — Implement `PackCompatibilityChecker` verifying `requires_platform_version`, declared dependencies, and `publication_relations` schemas. Acceptance: a broken pack fails at load with a typed diagnostic; a good pack loads.
- `contracts` — Contract-test harness under `tests/pack_contracts/` reused by CI. Acceptance: harness runs against every in-repo pack and against a synthetic external pack fixture.

### B5 `pack-lifecycle-loom`
- `lifecycle` — Extend `AdapterRegistry` (or a new `PackRegistry`) with install, activate, upgrade, deactivate, rollback. Acceptance: a state machine test proves every transition and blocks illegal ones.
- `preupgrade` — Pre-upgrade contract check running the B4 harness before switching the active pack version. Acceptance: an incompatible upgrade is rejected without touching the active version.

### B6 `lineage-graph-lantern`
- `graph` — Build a lineage graph query API traversing `SourceLineageRecord` and `PublicationAuditRecord` from source run to publication. Acceptance: `/api/lineage/publication/{key}` returns the full transitive graph with typed edges.
- `viewer` — Minimal lineage viewer inside the existing web shell. Acceptance: from a publication tile, an operator can open the lineage graph and reach the source run.

### B7 `confidence-canvas-glow`
- `dashboard` — Operator confidence dashboard reading `PublicationConfidenceIndex`. Acceptance: every publication is listed with its freshness state, completeness, and verdict; filters cover verdict and staleness.
- `decision-lineage` — Persist scenario assumption → projection edges so every projection can name its assumptions. Acceptance: opening a scenario output surfaces the assumption set that produced it.

### B8 `portability-anchor`
- `backup` — `homelab-analytics-worker backup` producing a manifest + control-plane Postgres dump + DuckDB warehouse snapshot + blob storage archive. Acceptance: a smoke test round-trips the sample dataset through backup and restore on a clean fixture directory.
- `runbook` — `docs/runbooks/backup-and-restore.md` covering shared-Postgres, single-user Compose, and demo/dev. Acceptance: runbook checklist is executable end-to-end and referenced from the operations runbook.

### B9 `agent-surface-mcp`
- `index` — LLM-shaped semantic index derived from B3, including descriptions, column glossary, and sample values with row-count bounds. Acceptance: index passes a schema validation test and is served under a stable endpoint.
- `mcp` — MCP tool definitions covering publication retrieval, scenario proposal, and policy proposal; tools call the existing endpoints. Acceptance: a local MCP client can list tools, retrieve a publication summary, and propose a scenario against a stub agent runner.
- `proposals` — Generalize the HA approval queue into an adapter-agnostic action-proposal model. Acceptance: an MCP action proposal enters the same approval queue used by HA-gated actions and can be approved from the web shell.

### B10 `domain-marts-fillout`
- `infra` — `mart_energy_daily`, `mart_infra_cost`, `mart_uptime_summary`, `mart_cluster_utilization`. Acceptance: publication contracts, migrations, and reporting-layer tests land; each mart appears in `/api/semantic-index`.
- `home-auto` — `mart_climate_summary`, `mart_automation_reliability`, `mart_device_battery`. Acceptance: same shape as infra track.
- `assets` — `mart_asset_value`, `mart_depreciation_schedule`. Acceptance: same shape as infra track.
- `finance` — `mart_debt_overview` (cross-instrument), `mart_subscription_changes` (activation/cancellation by period). Acceptance: same shape as infra track.

### B11 `appservice-first-deploy`
- `chart` — Reconcile `charts/homelab-analytics` with `docs/notes/appservice-cluster-integration-notes.md` (namespace, ingress, OIDC secret model, Postgres connection). Acceptance: `helm template` output matches the cluster-integration notes.
- `deploy` — First live deploy to `appservice` with OIDC and Postgres. Acceptance: smoke check hits `/healthz`, `/readyz`, and one publication endpoint through the cluster ingress.

### B12 `self-observ-canvas`
- `slos` — Declare SLOs and error budget for ingestion success, publication freshness, HA bridge availability. Acceptance: SLO doc landed under `docs/runbooks/`; alert rules generated from the SLO doc.
- `dashboard` — Self-observability dashboard (Grafana JSON committed) reading platform-internal metrics distinct from product-facing publications. Acceptance: dashboard renders locally against the exported Prometheus metrics and is referenced from the operations runbook.

## 8. Sequencing and dependencies

```
B10 ─────────────────────────────────► (independent, unblocks U7)
B11 ─► B12 ────────────────────────► (independent, unblocks U14/U15)
B8  ─────────────────────────────────► (independent, unblocks U12)
B6  ─► B7 ──────────────────────────► (unblocks U10, U11)
B1  ─► B2 ──────────────────────────► (unblocks U7 partial, U8 partial)
B3  ─► B4 ─► B5 ────────────────────► (unblocks U9)
B3  ─► B9 (with B6) ────────────────► (unblocks U13)
```

Two hard cuts:
1. **B3 gates B9** — the agentic surface must consume the same semantic index that Stage 7 exposes to renderers.
2. **B6 gates B9's action proposals** — action proposals without lineage are the "eloquent intern with root access" failure mode called out in the roadmap.

## 9. Implementation session plan

See `docs/plans/2026-07-implementation-session-plan.md` for session ordering, entry criteria, exit criteria, and dispatch posture for each sprint.
