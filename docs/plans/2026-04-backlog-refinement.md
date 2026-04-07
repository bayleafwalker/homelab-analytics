# Homelab-analytics backlog refinement — April 2026

**Classification:** CROSS-CUTTING

## 1. Current-state read

### What is already strong

- The modular-monolith shape is real rather than aspirational. The repository has a credible layer split between landing, transformation, and reporting, and the product docs consistently frame the platform around stable publications rather than ad hoc dashboards.
- The household operating picture is no longer hypothetical. Finance, utilities, scenarios, homelab reporting, confidence metadata, and approval-gated action proposals are all present enough that the next backlog does not need another round of “platform foundations” work.
- Operator trust has improved materially. Publication confidence, freshness propagation, lineage, publication audit, and reporting-layer contracts already give the repo a strong truth-telling spine.

### What is fragile

- The first-source operator path is still more fragmented than the product posture implies. Onboarding, source configuration, upload, freshness, failure analysis, and remediation exist, but they do not yet feel like one coherent flow.
- The runtime stance is architecturally correct but not always operator-obvious. Postgres is the canonical control-plane and published-reporting path, while SQLite and DuckDB are narrower support roles, yet some defaults and guidance still make the transitional paths look more first-class than they should.
- Reporting truth is present but not surfaced clearly enough. The repo supports both warehouse-backed and published-reporting reads, but an operator still has to infer too much about which path is active and what publication state the app is relying on.

### What is transitional debt

- SQLite remains a necessary bootstrap path, but it is also a maintenance trap if treated as a peer control-plane backend.
- The repo has more than one user-facing shell now. The classic Next.js surface is the primary product surface, while the retro routes are a legitimate alternate renderer, but they create pressure to expand a second parallel UI before the first operator path is fully coherent.
- Extension-registry and partner-surface capabilities are ahead of their operator ergonomics. The APIs and runtime hooks exist, but the admin experience still assumes a developer who is comfortable inferring state from CLI or raw contracts.

### What should not be disturbed casually

- Do not collapse the landing, transformation, and reporting split to make a workflow feel faster.
- Do not blur the explicit Postgres control-plane plus DuckDB warehouse support model into a generic “any backend works” posture.
- Do not reopen Home Assistant scope as if it were the whole platform. It is a first-class partner surface, not the architectural center.
- Do not add a second privileged frontend path or a new renderer lane before the current operator workflows are coherent on the existing surface.

## 2. Recommended execution posture

**Posture:** harden the base by stability, not by deployable service.

The repository should keep one repo and one deployment story. The useful cut for the next backlog is not API vs worker vs web. The useful cut is which parts should stay boring and slow-moving, which parts are the reusable semantic engine, which parts are product-pack logic, and which parts are thin surfaces.

That yields one planning rule for the next backlog:

**Base = kernel + semantic engine.**

If a candidate item mainly improves operator presentation while leaving kernel or semantic seams muddy, it should lose to the smaller item that makes the base more explicit. If a candidate item mainly adds a new surface or partner path before the existing operator loop is coherent, it should be parked.

## 3. Stability strata

### Stratum 1: Kernel

The kernel is the part that should still make sense if every current domain pack disappeared tomorrow.

It owns:

- runtime and container build
- config and settings
- auth primitives and policy assembly
- control-plane store contracts
- run metadata and scheduling/dispatch primitives
- blob/object storage
- capability, publication, and UI descriptor types
- extension loading
- audit, lineage, and health primitives

If code mentions cashflow, tariff comparison, HA entities, homelab workloads, scenario assumptions, or dashboard composition, it probably does not belong here.

### Stratum 2: Semantic engine

The semantic engine is the reusable household brain that turns evidence into normalized meaning.

It owns:

- canonical facts and dimensions
- ingestion-to-promotion orchestration
- transformation registries and publication materialization
- reporting access contracts
- scenario storage and compute
- policy evaluation primitives

This is not the kernel. It changes faster and should be allowed to change faster. But it is still base infrastructure, not product-surface glue.

### Stratum 3: Product packs

Finance, utilities, homelab, and overview are product packs attached to the semantic engine.

They own:

- source definitions
- pack workflows
- publication definitions
- pack-local reporting and transformation rules
- heuristics and insight logic
- optional UI descriptors tied to pack outputs

Deleting a pack should not force a runtime, auth, or storage redesign. That is the boundary test.

### Stratum 4: Surfaces

API, worker, web, Home Assistant, exports, Prometheus, and admin views are surfaces. They should be aggressively thin.

They should only:

- accept requests or events
- authenticate and authorize
- call explicit use-case entrypoints
- serialize, render, publish, or bridge outputs

If a surface knows business sequencing, it is carrying application logic that belongs elsewhere.

### Mandatory seam: application use-cases

The repo still needs an explicit orchestration seam even though it is not a separate stability stratum.

Surfaces should call stable use-cases such as:

- `run_ingestion`
- `promote_run`
- `publish_outputs`
- `retry_run`
- `compute_scenario`
- `evaluate_policy`
- `dispatch_action_proposal`

That seam is the main missing boundary keeping `apps/api/app.py` and other surface code too knowledgeable.

## 4. Priority backlog

| Priority | Stratum | Item | Type | Size | Why now | Depends on | Acceptance criteria | Risks / notes |
|---|---|---|---|---|---|---|---|---|
| must do now | Kernel | Postgres-first operator defaults and SQLite guardrails | architecture integrity | S | The repo already documents Postgres as canonical, but demo-friendly defaults and fallback language still make SQLite look safer than it is for ongoing operator use. | none | Non-demo runbooks and examples default to Postgres control-plane plus published reporting; SQLite is explicitly documented and surfaced as bootstrap-only; local demo flow remains intact; any runtime warning or admin disclosure makes the fallback posture obvious. | Narrow and label the fallback; do not remove it. |
| must do now | Kernel | Auth policy decomposition and thin FastAPI assembly | architecture integrity | M | Auth is kernel policy, but the current API assembly still carries too much policy branching and middleware detail inline. | none | Credential resolution, principal authentication, CSRF and session checks, permission evaluation, scope evaluation, break-glass policy, and audit or metrics hooks have explicit homes; FastAPI assembly becomes composition only. | Wrong choice if it becomes a framework rewrite instead of a seam cleanup. |
| must do now | Semantic engine | Publish remaining homelab and infrastructure current-dimension contracts | semantic closure | S | `docs/architecture/semantic-contracts.md` still calls out unpublished app-facing parity gaps for `dim_node`, `dim_device`, `dim_service`, and `dim_workload`. Leaving those implicit invites ad hoc partner-surface reads. | none | Reporting-layer current snapshots and explicit semantic metadata exist for the remaining homelab and infrastructure current dimensions; app-facing access goes through the reporting contract path; focused contract tests cover the new exposures. | Confirm names and intended reuse before publishing. |
| must do now | Semantic engine | Extract explicit application/use-case entrypoints for run, publish, scenario, and policy flows | boundary hardening | M | The most important missing seam is still orchestration. Surfaces should not continue to own sequencing. | none | Surface code calls stable use-cases for ingest, promotion, publication, retry, scenario compute, policy evaluation, and action dispatch; route or worker composition stops embedding workflow order. | This is a seam, not a fifth platform. Keep it boring. |
| should do soon | Product packs | First-source onboarding flow closure | product usability | M | The repo has enough onboarding pieces to help a real operator, but not enough coherence to make first-time setup feel finished. | Kernel posture should be settled first for non-demo guidance. | A first representative source can be created, previewed, uploaded, and verified from the main operator surface without CLI fallbacks; onboarding points into source asset setup, preview, upload, and freshness follow-up; docs and UI tell the same story. | Keep the slice focused on a golden path, not a generic pipeline builder. |
| should do soon | Product packs | Failed-run to remediation action path | product usability | S | Run detail, source freshness, and retry context already exist, but they do not yet consistently tell the operator what to do next. | First-source onboarding flow closure | Failed and stale states link to the right action: retry, upload missing period, inspect binding, or fix contract; source-freshness docs and run detail surfaces use the same action vocabulary. | It should close the loop on existing signals, not add a new orchestration surface. |
| should do soon | Product packs | Keep onboarding and remediation sequencing under pack or application ownership | boundary hardening | S | The product loop is still at risk of leaking back into route modules and shell code. | Explicit use-case entrypoints | Pack-local source setup, preview, remediation vocabulary, and follow-up actions are defined once and consumed by surfaces rather than rederived per UI. | Avoid inventing a second registry just for UX metadata. |
| should do soon | Surfaces | Reporting mode disclosure and publication audit summary | operational reliability | S | Operators still have to infer too much about whether a view is warehouse-backed or publication-backed and why it should be trusted. | publication confidence and audit plumbing already shipped | Control-plane surfaces show reporting backend mode, publication freshness, last refresh or publish status, and drill-down to publication audit; runbooks explain when to stay warehouse-backed and when to move to published reporting. | Keep the backend choice explicit, not abstracted away. |
| should do soon | Surfaces | Terminal task library and command discovery | developer ergonomics | XS | The allowlisted terminal is strategically useful, but today it feels like an undocumented escape hatch rather than a deliberate operator aid. | Failed-run to remediation action path | `/control/terminal/commands` is surfaced in grouped, task-oriented language; control and remediation surfaces link to common commands; `docs/runbooks/operations.md` names the exact jobs the terminal is for. | It should bridge operator gaps, not become a shell product. |
| later, once surface truth is in place | Surfaces | Extension registry visibility surface | capability expansion | S | The extension registry is too far along architecturally to remain developer-only, but it is not important enough to outrank base hardening and product-loop closure. | Reporting mode disclosure and publication audit summary | Admin UI exposes registry sources, revisions, sync or validation state, discovered handlers, publication keys, function keys, and active revision without implying hot reload; operator-facing docs explain activation posture. | Keep this read-only. Activation and rollback workflows belong in a later sprint. |

## 5. Parked backlog

### Guarded extension activation diff and rollback workflow

**Reason to park:** The repo first needs read-only visibility so operators can understand registry state. Mutation-heavy flows before that would add complexity on top of a still-weak operator story.

**Trigger to pull later:** Once registry visibility is live and at least one real external pack is operated without CLI-only recovery.

### Home Assistant REST-sensor packaging and add-on polish

**Reason to park:** HA is already a strong partner surface. Packaging and ecosystem polish would improve reach, but it does not currently reduce structural risk or improve the first operator loop inside the platform.

**Trigger to pull later:** A real installation needs repeatable HA packaging beyond the current platform-managed integration paths.

### Broader non-published reporting traceability

**Reason to park:** Publication audit and confidence are already strong enough for the current operator posture. The remaining gap is real, but it is governance depth rather than an immediate credibility blocker.

**Trigger to pull later:** Operators start relying on warehouse-backed runs in a way that needs auditable explanation beyond current run detail and publication audit surfaces.

### Dataset exploration UI

**Reason to park:** It is useful, but it is secondary to making the main operator loop coherent. Right now it risks becoming a curious side surface rather than fixing a daily job.

**Trigger to pull later:** First-source onboarding and remediation are coherent enough that read-only exploration becomes the next obvious support tool.

### Separate deployable kernel image or platform repo

**Reason to park:** The repo should keep one deployment story until a second real consumer exists and the kernel has held stable over time. Extraction readiness is a later gate, not the next sprint shape.

**Trigger to pull later:** A second non-household consumer exists, or monorepo packaging and release friction becomes materially painful for multiple sprints.

## 6. Reject for now

### Repo split or microservice breakup

**Why it is seductive:** The repo spans API, worker, web, control plane, domain packs, and HA integration, so splitting it can feel like architectural maturity.

**Why it is wrong for the current repo state:** The modular-monolith direction is working. The main problems are explicit contract completion and operator coherence, not team-scale ownership boundaries. A split would multiply release and coordination cost for a solo maintainer without solving the real seams.

### Generic query abstraction over DuckDB and Postgres

**Why it is seductive:** The code already supports warehouse-backed and published-backed read paths, so a unified abstraction can look “cleaner.”

**Why it is wrong for the current repo state:** The backend distinction is operationally meaningful and should remain visible. Hiding it behind a generalized query layer would make the system feel simpler while actually making operator truth less explicit.

### More retro-shell expansion or a third renderer lane

**Why it is seductive:** The retro routes are distinctive, and renderer work produces visible progress quickly.

**Why it is wrong for the current repo state:** The main operator path is not finished enough to justify parallel surface expansion. Another renderer lane would spend product energy on presentation multiplicity before the core workflows are coherent.

### Distributed workflow or task-queue platformization

**Why it is seductive:** A queue, scheduler, or orchestration layer can look like the next natural move for a growing data platform.

**Why it is wrong for the current repo state:** The current bottlenecks are trust, workflow coherence, and explicit contracts, not compute scale. Adding a task platform would increase operating burden without solving the problems operators actually feel.

### Backlog planning by deployable service

**Why it is seductive:** API, worker, web, HA, and admin surfaces are visible, so turning each into its own planning bucket can look tidy.

**Why it is wrong for the current repo state:** Those cuts hide the real change-rate boundary. The repo’s quality problem is not that services are co-deployed. It is that kernel, semantic-engine, product-pack, and surface concerns still blur together in code and planning.

## 7. Things that look tempting but should not enter the next backlog

- repo split or service extraction work
- unified cross-backend query abstraction
- more retro-shell or alternate-renderer expansion
- Home Assistant add-on packaging polish
- auto-categorization or “smart” finance heuristics

## 8. Suggested sprint packaging

The next planning cycle should supersede earlier operator-theme packaging with stability-strata packaging.

### Sprint `keel-ledger-bond`

**Objective:** Make the kernel boring again by clarifying runtime posture and moving auth policy back into kernel-owned seams.

**Included items:** Postgres-first operator defaults and SQLite guardrails; auth policy decomposition and thin FastAPI assembly.

**Expected repo impact:** runtime docs, configuration guidance, auth composition cleanup, minimal API assembly changes.

**Rollback / containment notes:** keep the same auth capabilities and SQLite fallback behavior; the work should reduce branching and ambiguity, not change the external product story.

### Sprint `semantic-seam-forge`

**Objective:** Make the reusable semantic engine explicit and stop surfaces from carrying workflow order.

**Included items:** Publish remaining homelab and infrastructure current-dimension contracts; extract explicit application/use-case entrypoints for ingest, publish, scenario, and policy flows.

**Expected repo impact:** reporting-contract updates, transformation and publication orchestration cleanup, route and worker simplification through use-case entrypoints.

**Rollback / containment notes:** preserve existing APIs and worker commands; do not introduce a second generic orchestration framework.

### Sprint `pack-loop-harbor`

**Objective:** Make the first-source and first-broken-run loop feel like one product owned by packs and application use-cases instead of by whatever surface the operator touched first.

**Included items:** First-source onboarding flow closure; failed-run to remediation action path; keep onboarding and remediation sequencing under pack or application ownership.

**Expected repo impact:** onboarding, runs, source freshness, and supporting runbooks; no new ingestion abstraction layer.

**Rollback / containment notes:** preserve existing upload and refresh APIs; changes should compose current contracts instead of inventing new ones.

### Sprint `surface-glass-bridge`

**Objective:** Make surfaces thinner and more honest by exposing reporting truth, terminal task discovery, and extension state without widening platform scope.

**Included items:** Reporting mode disclosure and publication audit summary; terminal task library and command discovery; extension registry visibility surface.

**Expected repo impact:** control-plane and admin UI work, read-only registry visibility, runbook updates, minimal runtime changes.

**Rollback / containment notes:** keep registry work read-only and keep backend choices explicit. Do not introduce hot reload, marketplace flows, or a new renderer lane in this sprint.
