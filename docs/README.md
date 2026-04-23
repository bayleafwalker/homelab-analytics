# Documentation

## Requirements

The authoritative requirements baseline lives at `requirements/` in the repository root. See `requirements/README.md` for the template, phase definitions, stage alignment, and document index.

## Concern tags

Use these tags when adding or updating docs so kernel-vs-app ownership stays explicit:

- `PLATFORM` — platform kernel architecture, runtime primitives, security foundations, and storage support model.
- `APP` — household-app product behavior, operator workflows, and domain-facing UX guidance.
- `CROSS-CUTTING` — docs that intentionally span platform and app concerns (for example sprint/process guidance or boundary ADRs).

## Concern-oriented starting points

### Platform kernel docs (`PLATFORM`)

- `decisions/operational-database-support-model.md`
- `decisions/compute-and-orchestration-options.md`
- `decisions/auth-boundary-external-identity-internal-authorization.md`
- `architecture/data-platform-architecture.md`
- `architecture/contract-governance.md`
- `runbooks/release-governance.md`

### Household app docs (`APP`)

- `product/core-household-operating-picture.md`
- `product/initial-capability-packs-and-publications.md`
- `product/finance-source-contracts.md`
- `product/source-freshness-workflow.md`
- `examples/finance-source-contracts/README.md`

### Boundary docs (`CROSS-CUTTING`)

- `decisions/household-platform-adr-and-refactor-blueprint.md`
- `decisions/household-operating-platform-direction.md`
- `runbooks/project-working-practices.md`
- `runbooks/testing-and-verification.md`
- `runbooks/sprint-and-knowledge-operations.md`
- `agents/implementation.md`

## Architecture

- `architecture/data-platform-architecture.md` — source ingestion pattern, landing/bronze, transformation/silver, reporting/gold, SCD handling, extensibility model, and API/UI publishing model. Also covers forward-looking architectural layers: semantic domain, planning/scenario, policy/automation, multi-renderer delivery, pack ecosystem, and trust/governance.
- `architecture/finance-ingestion-model.md` — personal-finance ingestion taxonomy, lane model, canonical dataset types, parser protocol, lifecycle, and evidence/lineage expectations.
- `architecture/sqlite-control-plane-capability-matrix.md` — explicit Postgres-vs-SQLite control-plane capability boundaries: guaranteed vs best-effort support posture.
- `architecture/contract-governance.md` — stale-artifact checks, contract compatibility policy, and CI/release contract bundle workflow.
- `architecture/publication-contracts.md` — backend-owned publication and UI descriptor contract model, semantic field metadata, renderer expectations, and generated frontend publication types.
- `architecture/semantic-contracts.md` — shared-dimension promotion rules, publication semantic-contract expectations, and Stage 1 cross-domain governance guidance.
- `architecture/homeassistant-integration-hub.md` — six-layer integration hub architecture: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication model, and resilience model.
- `architecture/ha-bridge-ingest-api.md` — implemented HA bridge landing API surface: typed payload contracts, `ha-bridge:ingest` auth boundary, canonical entity/device/area mapping targets, schema versioning, and route guardrails.
- `architecture/integration-adapters.md` — Stage 6 adapter contract packet: `AdapterManifest`, ingest/publish/action contracts, lifecycle model, HA-as-reference mapping, and candidate external integration surfaces.
- `architecture/simulation-engine.md` — scenario storage schema, compute model, assumption tracking, and planned scenario types.
- `architecture/agent-surfaces.md` — Stage 10 agent retrieval and proposal boundaries for semantic publication exploration.

## Product

- `product/README.md` — product documentation index and the boundary between architecture decisions and product decisions.
- `product/finance-source-contracts.md` — operator-facing guidance for personal-finance source contracts, reconciliation roles, acquisition flow, validation behavior, and canonical output fields.
- `product/source-freshness-workflow.md` — source freshness model, operator workflow, and next-action remediation guidance for manual sources.
- `product/manual-reference-inputs.md` — operator-maintained sparse-fact pathway for loan policy, account metadata, and transaction overrides.
- `product/homeassistant-and-smart-home-hub.md` — Home Assistant as edge runtime and actuation layer, platform's role beyond HA, integration principle, and roadmap alignment.
- `product/core-household-operating-picture.md` — core product definition: the Household Operating Picture, four core views (Overview, Money, Utilities, Operations), product principles, and acceptance criteria.
- `product/initial-capability-packs-and-publications.md` — domain pack definitions, publication sets, insight types, and priority ordering for finance, utilities, homelab, and overview.
- `product/core-product-design-workflow.md` — product design intake process and workflow.
- `product/frontend-ui-delivery-playbook.md` — UI control loop, style/primitive/scenario contracts, draft-vs-publish lanes, and the target validation stack for agent-heavy frontend work.
- `product/product-slice-template.md` — template for new product slices.

## Examples

- `examples/finance-source-contracts/op-account-csv.md` — OP account CSV contract guide, canonical output fields, and operator validation notes.
- `examples/finance-source-contracts/README.md` — entrypoint for the finance source contract demo bundle and walkthrough order.
- `examples/finance-source-contracts/op-gold-invoice.md` — OP Gold invoice example and statement snapshot notes.
- `examples/finance-source-contracts/revolut-personal-account-csv.md` — Revolut personal account example and canonical transaction notes.
- `examples/finance-source-contracts/credit-registry-snapshot.md` — Finnish positive credit registry contract guide, record types, and reconciliation notes.
- `examples/ui-contracts/README.md` — example frontend contract bundle with `intent.md`, `baseline.tokens.json`, and `ui-contract.yaml`.

## Sprints

Use `docs/sprints/TRACKER.md` for the live sprint index. Keep this section to durable anchors rather than a full sprint catalog.

- `sprints/household-operator-implementation-plan.md` — implementation plan for the household operator product loop.
- `sprints/finance-ingestion-subsystem.md` — sprint plan for the finance ingestion subsystem.
- `sprints/architecture-sprint-scope.md` — architecture sprint scope and baseline decisions.
- `sprints/documentation-reconciliation-and-adapter-stage.md` — documentation reconciliation, integration adapter stage, and roadmap update.
- `sprints/agentic-and-assistant-layer.md` — agentic retrieval and safe action proposals.

## Agents

- `agents/planning.md` — planning mode expectations and required plan verification.
- `agents/implementation.md` — implementation mode guardrails and required validation.
- `agents/review.md` — review mode findings-first expectations and architecture checks.
- `agents/release-ops.md` — local, CI, and deployment verification expectations.
- `agent-guidance-refactor.md` — migration note for the compact `AGENTS.md` plus `.agents/skills/` split.

## Agent Skills

- `../.agents/skills/README.md` — short index of repo skills and when to use them.
- `../.agents/skills/domain-impact-scan/SKILL.md` — impact scan for cross-layer, contract, architecture, and requirements changes.
- `../.agents/skills/sprint-packet/SKILL.md` — build an execution-ready sprint or work packet from roadmap or requirements material when the scope is accepted but not yet registered in `sprintctl`.
- `../.agents/skills/sprint-resume/SKILL.md` — safely resume an already-registered sprint item from live `sprintctl` state, including claim identity checks and handoff behavior.
- `../.agents/skills/code-change-verification/SKILL.md` — select, run, and report the right local verification.
- `../.agents/skills/pr-handoff-summary/SKILL.md` — produce a concise reviewer or handoff summary after the change shape is stable.
- `../.agents/skills/workflow-artifact-capture/SKILL.md` — classify session outputs at workflow close, promote curated examples into `docs/training/`, and route concise durable lessons into `kctl` when appropriate.
- `../.agents/skills/sprint-snapshot/SKILL.md` — render the active sprint state from sprintctl into the committed plaintext snapshot after live status changes.
- `../.agents/skills/kctl-extract/SKILL.md` — run sprint-close knowledge extraction and review with kctl.

## Knowledge

- `knowledge/README.md` — conventions for committed `kctl` render outputs.
- `knowledge/knowledge-base.md` — canonical committed knowledge base rendered from published `kctl` entries.

## Training

- `training/README.md` — guidance for committed curated training artifacts derived from sessions and workflow experiments.
- `training/workflow-artifact-TEMPLATE.md` — template for new workflow training artifacts promoted out of `.agents/sessions/`.

## Decisions

- `decisions/household-operating-platform-direction.md` — operating platform identity evolution, 11-stage roadmap direction, relationship to Home Assistant, and relationship to existing ADRs.
- `decisions/household-platform-adr-and-refactor-blueprint.md` — modular monolith architecture, 5-layer model, capability pack registration, boundary enforcement, and migration plan.
- `decisions/operational-database-support-model.md` — canonical operational database support model: Postgres for operational truth, SQLite as local bootstrap fallback, and DuckDB as the worker/local warehouse engine.
- `decisions/compute-and-orchestration-options.md` — comparison of Spark and alternative engines/orchestrators, with the recommended initial stack and upgrade path.
- `decisions/auth-boundary-external-identity-internal-authorization.md` — auth boundary lock: external identity, in-app authorization semantics, service-token alignment, and narrow break-glass posture.

## Plans

- `plans/household-operating-platform-roadmap.md` — 11-stage roadmap from analytics platform to household operating platform, with stage descriptions, dependencies, and phase-to-stage mapping.
- `plans/2026-04-backlog-refinement.md` — bounded next-backlog recommendation: execution posture, priority items, parked work, anti-backlog, and sprint packaging for the next planning cycle.
- `plans/cinder-ledger-path-flagship-finance-operator-loop.md` — authoritative kickoff packet for sprint `#64`, including the route-neutral finance journey, source-freshness vs publication-trust boundary, and thin-surface application seam.
- `plans/ha-addon-and-integration-design.md` — design plan for the HA add-on (outbound bridge) and HA integration (inbound semantic surface): architecture, entity model, update model, API contracts, security model, and documentation outputs.
- `plans/homelab-analytics-platform-plan.md` — strategic decisions and rationale from the bootstrap phase. Detailed requirements now live in `requirements/` at the repository root.
- `plans/additional-data-domains.md` — planned data domains beyond account transactions, with source systems, canonical models, and marts for each.
- `plans/non-finance-domain-backlog.md` — assessment and backlog recommendation for non-finance domains while the finance sprint remains active.
- `plans/external-registry-inclusion.md` — control-plane plan and implementation direction for GitHub or custom-folder extension sources and custom-function registration.

## Notes

- `notes/appservice-cluster-integration-notes.md` — cluster deployment notes for the `appservice` GitOps repository.
- `notes/backend-owned-contracts-review-handover.md` — merged review handoff for the backend-owned contracts workstream, including commit landmarks, review hotspots, and verification.

## Runbooks

- `runbooks/project-working-practices.md` — repo-wide working loops, source-of-truth precedence, change-class done criteria, multi-agent coordination rules, and session-note policy.
- `runbooks/release-governance.md` — branch lifetime, tag types, GitHub Release policy, and minimum release checklist.
- `runbooks/operations.md` — deployment, ingress, readiness, and alert-response guidance for shared environments.
- `runbooks/backup-and-restore.md` — backup and restore guidance for Postgres control-plane state, landed object storage, and DuckDB artifacts.
- `runbooks/configuration.md` — environment variable reference for API, worker, web, auth, storage, and extension configuration.
- `runbooks/sprint-and-knowledge-operations.md` — repo-level operating model for `sprintctl` and `kctl`, including shared artifacts, workflow phases, and local-vs-committed boundaries.
