# 2026-04-14 Handoff - dispatch-review landscape

## Purpose

This handoff captures a read-only landscape report for enhancing `.agents/skills/dispatch-review/`.
It summarizes the current review skill contract, adjacent dispatch contracts, review/planning/implementation mode docs, architecture guardrail tests, reference architecture docs, package size asymmetry, cross-pack coupling, and suppression hot spots.

## Inspection Status

- Repo edits during inspection: none before this handoff was requested.
- Sprint state mutations: none.
- Tests run: none. This was a read-only inventory task.
- Commands used: file discovery and read-only shell inspection such as `find`, `sed`, `rg`, `wc`, and `git status`.

## Current `dispatch-review` Skill

Files under `.agents/skills/dispatch-review/`:

- `.agents/skills/dispatch-review/SKILL.md`

Current skill prompt, verbatim:

```markdown
---
name: dispatch-review
description: Use when implementation is stable and a findings-first code review is required before final handoff or PR prep for a code-bearing scope. Spawns a Sonnet subagent in read-only review mode. Do not use during early implementation, for planning, or when a reviewer summary is not the required output.
---

## Goal

Produce a findings-first review of a completed or stable diff by delegating to a read-only Sonnet subagent.
Run this once per stable reviewable scope, not once per sprint item.

## Inputs

- The diff or set of files under review.
- The relevant requirements, architecture sections, and test coverage.
- The review mode guide at `docs/agents/review.md`.
- The applicable change-class done checklist from `docs/runbooks/project-working-practices.md`.

## Steps

1. Confirm implementation is stable enough to review — the diff is not expected to change significantly before the review completes.
2. Read the review mode guide at `docs/agents/review.md`.
3. Spawn a subagent: type=general-purpose, model=sonnet, with:
   - The diff or file list under review
   - The review mode guide content from `docs/agents/review.md`
   - The relevant requirements and architecture sections
   - The change class (docs-only, behavior, architecture) and its done criteria
   - Explicit instruction: no edits, no bash mutations — read and report only
4. Wait for the subagent to return findings.
5. Present findings to the user in findings-first order: issues by severity, then open questions, then summary.
6. If the review surfaces blockers, route to `dispatch-build` for fixes before proceeding.
7. Treat this review as complete only when the current stable scope is either cleared or any residual risks are explicitly called out in the handoff.

## Output contract

- Findings ordered by severity with file:line references.
- Open questions or missing coverage noted explicitly.
- No repo edits made during this skill.
- The reviewed scope is ready for handoff or PR prep, or the blockers preventing that are explicit.

## Do not

- Do not run the review subagent before implementation is stable.
- Do not suppress findings to produce a clean summary.
- Do not proceed to PR handoff if the review surfaces unresolved blockers.
- Do not treat this as optional for a stable code-bearing scope that is about to be handed off or pushed toward PR.
```

Reference docs it points to:

- `docs/agents/review.md`
- `docs/runbooks/project-working-practices.md`
- Relevant requirements and architecture sections, but no exact requirement or architecture file is hard-coded.

What the current single-pass review actually checks:

- Whether implementation scope is stable enough to review.
- Requirements-to-implementation traceability.
- Whether tests cover changed behavior.
- Whether app-facing reporting paths avoid bypassing reporting-layer models.
- Whether applicable change-class done criteria are satisfied.
- Bugs, regressions, missing tests, and architectural drift, in findings-first order.
- It does not define specialist lanes, machine-readable output, required reference-doc routing, or automatic `sprintctl` event capture.

Current output behavior:

- Freeform findings-first text, not JSON.
- No `sprintctl` event is produced by the skill.
- The orchestrator waits for the review subagent, presents severity-ordered findings to the user, and routes blockers back to `dispatch-build`.

## Neighbor Skill Contracts

### `dispatch-plan`

Entry file: `.agents/skills/dispatch-plan/SKILL.md`

- Purpose: delegate read-only planning to an Opus planning subagent before repo mutations when architecture decisions, new scope, or layer-boundary questions are unresolved.
- Inputs: user request, relevant requirements/docs, sprint context, live `sprintctl` state when sprint-scoped.
- Orchestration: confirm planning is needed, check existing sprint scope, read `docs/agents/planning.md`, spawn Opus with goal, success criteria, sprint summary, affected layer boundaries, and constraints.
- Output: concise decision-complete plan with goal, scope, out-of-scope, layer boundaries, deliverables, acceptance checks, and verification path.
- Handoff: present plan to user for confirmation; if accepted and new sprint scope is needed, invoke `sprint-packet`.
- Findings return shape: not findings-first review; returns a plan brief. No repo edits.

### `dispatch-build`

Entry file: `.agents/skills/dispatch-build/SKILL.md`

- Purpose: delegate spec-complete implementation to Haiku subagents.
- Inputs: approved plan or active sprint item, live item/claim state, `docs/agents/implementation.md`, relevant contracts/fixtures/extension points.
- Orchestration: claim or verify item ownership; persist claim token locally in orchestrator only; spawn implementation subagents with deliverables, guide, item context, and scoped verification commands.
- Verification contract: `ruff check <changed-python-files>`, `mypy <changed-python-files>`, and targeted `pytest <specific-test-files> -x --tb=short`; architecture-contract test required for API route/auth/scenario-policy/architecture-doc changes.
- Failure handling: collect subagent results; if tests fail, run up to 5 fix cycles before escalating.
- Handoff to review: after item verification and stable scope diff, run `dispatch-review` before final handoff or PR prep.
- Output: implemented item with passing tests, item state updated, one commit per reviewable scope, and stable scopes reviewed before handoff.
- Findings return shape: build agents return implementation/test results, not a structured review schema.

## `docs/agents/review.md` Full Contents

```markdown
# Review Mode

## Purpose

Review code with a bias toward bugs, regressions, missing tests, and architectural drift.

Use `docs/runbooks/project-working-practices.md` for the review loop and the applicable change-class done checklist.
For stable code-bearing scopes in coordinator workflows, this review pass is required before final handoff, reviewer summary, or PR preparation.

## Allowed actions

- Read code, tests, requirements, and docs.
- Run non-mutating verification or static checks.
- Summarize findings and residual risks.

## Required inputs

- The diff or files under review.
- The relevant requirements, architecture sections, and local tests.
- The expected user-facing behavior and failure modes.

## Required verification

- Check that requirements and implementation traceability still align.
- Check that tests cover the behavior that changed.
- Check that app-facing reporting does not bypass reporting-layer models.
- Check that the change satisfies the relevant done criteria for its change class.

## Required output shape

- Findings first, ordered by severity, with file references.
- Open questions or assumptions second.
- A brief summary only after the findings.

## Stop and escalate

- Stop if the change cannot be reviewed accurately without missing files or generated artifacts.
- Stop if the change introduces a new product decision without a corresponding requirements update.
- Stop if the review would require executing destructive or mutating commands.
```

## Planning And Implementation Mode Docs

`docs/agents/planning.md` headers:

- `# Planning Mode`
- `## Purpose`
- `## Allowed actions`
- `## Required inputs`
- `## Required verification`
- `## Required output shape`
- `## Stop and escalate`

Planning handoff-relevant content:

- Decide whether the first working loop is new scope registration, resume existing sprint item, or direct implementation.
- Confirm whether existing work is already in `sprintctl` or whether new scope registration through `sprint-packet` is needed.
- Output a concise scope summary, implementation outline, tests, verification steps, and assumptions.
- Stop if layer responsibilities would collapse, product decisions are undocumented, sprint ownership cannot be proven, or unrelated user changes would need reverting.

`docs/agents/implementation.md` headers:

- `# Implementation Mode`
- `## Purpose`
- `## Allowed actions`
- `## Required inputs`
- `## Required verification`
- `## Required output shape`
- `## Stop and escalate`

Implementation handoff-relevant content:

- Commit at the enclosing reviewable scope boundary.
- Run `dispatch-review` for stable code-bearing scopes before final handoff, reviewer summary, PR prep, or CI-triggering push.
- Resolve blockers before calling the scope complete.
- A repo change is not complete just because implementation verification passed; review and sprint/kctl closeout steps must be requested or explicitly reported as blocked.
- Output what changed, what was verified, residual gaps, and verification commands.

## Architectural / Contract / Boundary Test Inventory

Generated `tests/__pycache__/*.pyc` files also matched the name patterns but contain no source assertions, so they are omitted below.

| File | One-line assertion summary |
|---|---|
| `tests/contract_price_test_support.py` | Helper for creating contract-price ingestion configuration and store setup; no direct assertions. |
| `tests/fixtures/contract_prices_invalid_values.csv` | Invalid contract-price fixture data used by domain tests; no assertions. |
| `tests/fixtures/contract_prices_valid.csv` | Valid contract-price fixture data used by domain tests; no assertions. |
| `tests/test_adapter_contracts.py` | Enforces adapter manifests, runtime status, protocols, HA adapter pack shape, registry lifecycle, compatibility, validation, and renderer contracts. |
| `tests/test_architecture_contract.py` | Enforces many architecture boundaries: layer imports, reporting-route flow, auth policy coverage, pack registration, migration naming, SQLite/Postgres constraints, and selected docs consistency. |
| `tests/test_capability_pack_contract.py` | Validates capability pack schema, workflow/publication/UI declarations, finance/utilities pack completeness, publication ownership uniqueness, and reporting relation coverage. |
| `tests/test_contract_artifacts.py` | Checks API/publication/UI contract compatibility classification, exported source drift detection, and release artifact bundle generation. |
| `tests/test_contract_price_domain.py` | Exercises contract-price CSV loading, landing ingestion acceptance/rejection, transformation facts, and current-price mart refresh. |
| `tests/test_control_plane_store_contract.py` | Verifies control-plane store protocols for config, scheduling, dispatch claiming, recovery, audit events, and service tokens. |
| `tests/test_finance_contract_base.py` | Enforces finance parser protocol shape, immutable parse results, taxonomy values, and package root re-exports. |
| `tests/test_finance_contract_credit_registry.py` | Validates credit-registry parser detection, snapshot extraction, and loader output. |
| `tests/test_finance_contract_op_account.py` | Validates OP account CSV detection, row normalization, repayment enrichment, and canonical loader output. |
| `tests/test_finance_contract_op_gold_invoice.py` | Validates OP Gold invoice PDF detection, statement/line-item extraction, and loader output. |
| `tests/test_finance_contract_revolut_personal_account.py` | Validates Revolut statement detection, row extraction, provider metadata, and loader output. |
| `tests/test_ha_contract_renderer.py` | Ensures Home Assistant publication rendering uses contract metadata and produces expected summary/cost states. |
| `tests/test_observation_layer.py` | Verifies deterministic batch/observation identity, idempotent observation loading, canonical field preservation, and fact/observation parity. |
| `tests/test_publication_contract_exports.py` | Checks OpenAPI/publication catalog export, scalar type mapping, required reporting relations, and field semantics. |
| `tests/test_repository_contract.py` | Enforces expected repo directories, docs, frontend contract artifacts, architecture doc coverage, and plan references. |
| `tests/test_requirements_contract.py` | Enforces requirement document template fields, allowed status values, and traceability for implemented/in-progress requirements. |
| `tests/test_sqlite_auth_store_contract.py` | Smoke-tests SQLite auth store bootstrap support. |
| `tests/test_web_ui_contract_tooling.py` | Ensures current web UI contract artifacts, scripts, token loading, Storybook, and Playwright scaffolding exist. |
| `tests/test_workflow_contract.py` | Enforces workflow required fields, known source references, unique workflow IDs, and publication ownership by pack. |

Key implication for enhanced review: import/layer/auth/pack-registration/publication-contract mechanics are already covered by tests, especially `tests/test_architecture_contract.py`. Review specialists should focus on semantic correctness, source-to-publication traceability, risky cross-pack coupling not yet encoded, and behavior/test adequacy.

## Architecture And Decision Docs Inventory

| File | Description |
|---|---|
| `docs/architecture/adapter-governance.md` | Adapter pack trust, compatibility, structural validation, and registry lifecycle. |
| `docs/architecture/agent-surfaces.md` | Agent retrieval/action boundaries: read semantic publication indexes, keep actions approval-gated. |
| `docs/architecture/category-governance.md` | Shared category identity and governance rules across finance/budget semantics. |
| `docs/architecture/contract-governance.md` | Backend-owned contract artifacts, compatibility policy, CI/release bundle workflow. |
| `docs/architecture/data-platform-architecture.md` | Main stability-strata map: kernel, semantic engine, product packs, surfaces, and app/use-case boundary. |
| `docs/architecture/domain-model.md` | Canonical household dimensions, facts, marts, ownership, and governance notes. |
| `docs/architecture/finance-ingestion-model.md` | Finance ingestion lanes for structured imports, raw docs plus parsers, and manual reference input. |
| `docs/architecture/ha-bridge-ingest-api.md` | Home Assistant bridge ingest API endpoints, auth boundary, schema versioning, identity, and mappings. |
| `docs/architecture/homeassistant-integration-hub.md` | Six-layer HA integration architecture from ingress through semantic core and action approval. |
| `docs/architecture/integration-adapters.md` | Generic adapter model, manifests, runtime status, lifecycle, and integration expectations. |
| `docs/architecture/pipeline-ambiguity-classification.md` | Classification of ambiguous pipeline files and current seam rules. |
| `docs/architecture/publication-contracts.md` | Publication contract model, authoring rules, external pack guidance, and renderer expectations. |
| `docs/architecture/semantic-contracts.md` | Semantic contract extension rules, shared/domain-local dimensions, gaps, and checklist. |
| `docs/architecture/simulation-engine.md` | Scenario/simulation storage schema and compute model. |
| `docs/architecture/sqlite-control-plane-capability-matrix.md` | Guaranteed vs best-effort SQLite control-plane capabilities and test strategy mapping. |
| `docs/decisions/auth-boundary-external-identity-internal-authorization.md` | ADR for external identity, app-local authorization, machine auth, and break-glass posture. |
| `docs/decisions/compute-and-orchestration-options.md` | Initial compute/orchestration stack recommendation and deferred alternatives. |
| `docs/decisions/household-operating-platform-direction.md` | ADR shifting project direction from analytics platform to household operating platform. |
| `docs/decisions/household-platform-adr-and-refactor-blueprint.md` | ADR for modular monolith, headless core, domain capability packs, and replaceable presentation adapters. |
| `docs/decisions/operational-database-support-model.md` | ADR standardizing Postgres as canonical operational DB with SQLite/DuckDB scoped roles. |

## Package Size And Largest Files

Line counts are rough `wc -l` over regular files, excluding `__pycache__` and `*.pyc`.

| Package | Files | LOC | Five largest files |
|---|---:|---:|---|
| `adapters` | 10 | 1,102 | `packages/adapters/contracts.py` 223; `packages/adapters/ha_adapters.py` 202; `packages/adapters/registry.py` 168; `packages/adapters/renderer_router.py` 152; `packages/adapters/compatibility.py` 137 |
| `analytics` | 3 | 59 | `packages/analytics/cashflow.py` 49; `packages/analytics/README.md` 7; `packages/analytics/__init__.py` 3 |
| `application` | 6 | 1,463 | `packages/application/use_cases/control_terminal.py` 872; `packages/application/use_cases/auth_sessions.py` 354; `packages/application/use_cases/ingest_promotion.py` 148; `packages/application/use_cases/run_recovery.py` 66; `packages/application/use_cases/__init__.py` 23 |
| `connectors` | 1 | 3 | `packages/connectors/README.md` 3 |
| `domains` | 84 | 15,962 | `packages/domains/finance/pipelines/scenario_service.py` 1,631; `packages/domains/overview/pipelines/transformation_overview.py` 880; `packages/domains/utilities/pipelines/transformation_utilities.py` 685; `packages/domains/homelab/pipelines/ha_bridge_ingestion.py` 658; `packages/domains/finance/pipelines/transformation_transactions.py` 650 |
| `pipelines` | 99 | 9,942 | `packages/pipelines/transformation_service.py` 1,484; `packages/pipelines/reporting_service.py` 930; `packages/pipelines/upload_dry_run.py` 619; `packages/pipelines/config_preflight.py` 613; `packages/pipelines/household_promotion_handlers.py` 493 |
| `platform` | 35 | 5,191 | `packages/platform/publication_contracts.py` 617; `packages/platform/auth/oidc_provider.py` 485; `packages/platform/auth/permission_registry.py` 450; `packages/platform/capability_types.py` 314; `packages/platform/auth/machine_jwt_provider.py` 294 |
| `shared` | 12 | 2,287 | `packages/shared/external_registry.py` 775; `packages/shared/settings.py` 568; `packages/shared/extensions.py` 361; `packages/shared/function_registry.py` 154; `packages/shared/auth.py` 99 |
| `storage` | 39 | 13,672 | `packages/storage/sqlite_execution_control_plane.py` 1,154; `packages/storage/postgres_execution_control_plane.py` 989; `packages/storage/sqlite_source_contract_catalog.py` 939; `packages/storage/control_plane.py` 838; `packages/storage/postgres_source_contract_catalog.py` 741 |

Note: `packages/demo/` also exists but was not in the requested package list. It has 3 Python files / 2,139 LOC, with `packages/demo/bundle.py` at 1,384 and `packages/demo/seeder.py` at 732.

## Stability Strata Mapped To `packages/`

Best inference from code structure and imports:

| Stratum | Current package directories |
|---|---|
| Kernel | `packages/platform/`, `packages/shared/`, `packages/storage/`, most of `packages/adapters/` contracts/registry/runtime status, and empty/scaffold `packages/connectors/` |
| Semantic engine | `packages/pipelines/` core services/composition/legacy facades, plus transformation/reporting service orchestration; some semantic computation still lives inside domain pack pipeline modules |
| Product packs | `packages/domains/finance/`, `packages/domains/utilities/`, `packages/domains/homelab/`, `packages/domains/overview/` |
| Surfaces | `packages/application/` use cases, adapter implementations in `packages/adapters/`, and surface-facing pipeline files such as reporting/export/HA renderer paths. `packages/analytics/` currently looks like a finance-specific semantic helper rather than a durable kernel package because it imports finance domain types directly. |

## Existing Pack-Boundary Violations Or Cross-Pack Coupling

Likely intentional:

- `packages/domains/overview/pipelines/transformation_overview.py` imports finance, homelab, and utilities model constants. This matches the overview manifest's role as a cross-domain composition pack.

Worth review attention:

- `packages/domains/finance/pipelines/scenario_service.py` imports homelab and utilities model constants directly:
  - `packages.domains.homelab.pipelines.homelab_models`
  - `packages.domains.utilities.pipelines.utility_models`
  This makes finance scenario computation depend on peer product packs rather than `overview`, shared semantic contracts, or a platform-level publication contract.
- `packages/domains/utilities/pipelines/transformation_utilities.py` imports `packages.domains.finance.pipelines.contract_price_models` directly. That looks like a historical ownership mismatch: contract prices appear in the utilities pack manifest, but the model still lives under finance.
- `packages/analytics/cashflow.py` imports `CanonicalTransaction` from finance domain internals. If `analytics` is meant to be cross-cutting, this is a semantic ownership smell; if it is legacy finance-only, it should probably be treated as product-pack code.

Already mechanically guarded:

- `tests/test_architecture_contract.py` blocks domains importing apps/adapters, platform importing domains, shared importing domains, app/reporting bypasses, and several runtime-builder pack boundaries.
- It does not appear to block product pack A importing product pack B directly, except by specific expectations around platform/shared/app boundaries.

## Files Over 600 Lines, Grouped By Package

| Package | Files over 600 lines |
|---|---|
| `application` | `packages/application/use_cases/control_terminal.py` 872 |
| `domains` | `packages/domains/finance/pipelines/scenario_service.py` 1,631; `packages/domains/overview/pipelines/transformation_overview.py` 880; `packages/domains/utilities/pipelines/transformation_utilities.py` 685; `packages/domains/homelab/pipelines/ha_bridge_ingestion.py` 658; `packages/domains/finance/pipelines/transformation_transactions.py` 650 |
| `pipelines` | `packages/pipelines/transformation_service.py` 1,484; `packages/pipelines/reporting_service.py` 930; `packages/pipelines/upload_dry_run.py` 619; `packages/pipelines/config_preflight.py` 613 |
| `platform` | `packages/platform/publication_contracts.py` 617 |
| `shared` | `packages/shared/external_registry.py` 775 |
| `storage` | `packages/storage/sqlite_execution_control_plane.py` 1,154; `packages/storage/postgres_execution_control_plane.py` 989; `packages/storage/sqlite_source_contract_catalog.py` 939; `packages/storage/control_plane.py` 838; `packages/storage/postgres_source_contract_catalog.py` 741; `packages/storage/sqlite_asset_definition_catalog.py` 734; `packages/storage/postgres_asset_definition_catalog.py` 671 |
| `demo` | `packages/demo/bundle.py` 1,384; `packages/demo/seeder.py` 732 |

## Test Files Over 600 Lines

| File | LOC |
|---|---:|
| `tests/test_api_app.py` | 2,758 |
| `tests/test_worker_cli.py` | 1,703 |
| `tests/test_adapter_contracts.py` | 1,502 |
| `tests/test_api_main.py` | 1,280 |
| `tests/test_architecture_contract.py` | 1,276 |
| `tests/control_plane_test_support.py` | 1,260 |
| `tests/test_api_auth.py` | 999 |
| `tests/test_web_auth.py` | 875 |
| `tests/test_api_oidc.py` | 852 |
| `tests/test_control_plane_api_app.py` | 840 |
| `tests/test_auth_permission_registry.py` | 811 |
| `tests/test_ingestion_config_repository.py` | 685 |
| `tests/test_contract_artifacts.py` | 624 |
| `tests/test_ha_api.py` | 610 |

## Suppression / Coverage Hot Spots

Suppressions found: `# noqa`, `# type: ignore`, and `# pragma: no cover`.

Clusters that look architecturally relevant:

- Legacy facade/re-export cluster in `packages/pipelines/`: many one-line modules use `from ... import *  # noqa: F403` to preserve old import paths while implementation moved under domain packs or composition modules. This is intentional compatibility, but it is also a boundary-review hot spot.
- Protocol/abstract-method coverage exclusions in `packages/adapters/contracts.py`: four `pragma: no cover` protocol ellipses. Low risk, likely idiomatic.
- Storage package export suppressions in `packages/storage/__init__.py`: `# noqa: F401` for optional/re-export imports. Likely intentional API surface maintenance.
- Dynamic typing bridge in `apps/worker/runtime.py`: three `# type: ignore[return]` around runtime repository accessors. Suggests an app/runtime container typing compromise.
- Provenance row casting in `packages/storage/postgres_provenance_control_plane.py`: three `# type: ignore` entries around row dict field coercion. Suggests DB row typing friction.
- Publication confidence coercions in `packages/pipelines/publication_confidence_service.py`: two `# type: ignore` entries when converting freshness/confidence values to strings.
- Finance PDF parser optional import in `packages/domains/finance/contracts/op_gold_invoice_pdf_v1.py`: one unscoped `# type: ignore` on `pdfplumber` import.
- Tests deliberately mutate frozen dataclasses or pass fake implementations, especially `tests/test_adapter_contracts.py`, `tests/test_ha_action_dispatcher.py`, and `tests/test_postgres_reporting_integration.py`. Mostly test-only compromise, not production architecture drift.

## Structured Output And Orchestrator Behavior

`dispatch-review` currently produces freeform markdown/text constrained by an output contract, not JSON and not a `sprintctl` event.

The orchestrator's contract is:

- Spawn a read-only Sonnet/general-purpose review subagent.
- Wait for findings.
- Present findings to the user in severity order.
- Include open questions or missing coverage.
- Summarize only after findings.
- If blockers exist, route back to `dispatch-build`.
- Consider review complete only when the stable scope is cleared or residual risks are explicitly called out.

There is no current machine-readable schema, no specialist result aggregation protocol, no automatic event capture, and no explicit mapping from change type to required architecture/reference docs beyond passing "relevant requirements and architecture sections."

## Planning Implications For Enhanced `dispatch-review`

- Add specialist lanes only where they do not duplicate mechanical architecture tests. The strongest existing mechanical suite is `tests/test_architecture_contract.py`.
- A useful specialist map would likely include: semantic-pack boundary reviewer, publication/contract reviewer, storage/control-plane reviewer, auth/surface reviewer, and verification/test-adequacy reviewer.
- Reference-doc routing should be explicit. For example, publication changes should always include `docs/architecture/publication-contracts.md`, semantic model changes should include `docs/architecture/semantic-contracts.md` and `docs/architecture/domain-model.md`, auth changes should include the auth ADR, and adapter changes should include adapter governance plus integration-adapter docs.
- Structured review output would be a real enhancement. Current orchestration only promises human-readable findings, so any multi-specialist review should define an aggregation schema with severity, file, line, specialist, finding, evidence, recommendation, and blocker status.
- Current direct product-pack imports are the best initial target for a semantic-pack specialist because they are visible in code and not fully covered by the broad architecture-contract tests.
