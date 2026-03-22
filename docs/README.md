# Documentation

## Requirements

The authoritative requirements baseline lives at `requirements/` in the repository root. See `requirements/README.md` for the template, phase definitions, stage alignment, and document index.

## Architecture

- `architecture/data-platform-architecture.md` — source ingestion pattern, landing/bronze, transformation/silver, reporting/gold, SCD handling, extensibility model, and API/UI publishing model. Also covers forward-looking architectural layers: semantic domain, planning/scenario, policy/automation, multi-renderer delivery, pack ecosystem, and trust/governance.
- `architecture/sqlite-control-plane-capability-matrix.md` — explicit Postgres-vs-SQLite control-plane capability boundaries: guaranteed vs best-effort support posture.
- `architecture/contract-governance.md` — stale-artifact checks, contract compatibility policy, and CI/release contract bundle workflow.
- `architecture/publication-contracts.md` — backend-owned publication and UI descriptor contract model, semantic field metadata, renderer expectations, and generated frontend publication types.
- `architecture/homeassistant-integration-hub.md` — six-layer integration hub architecture: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication model, and resilience model.
- `architecture/simulation-engine.md` — scenario storage schema, compute model, assumption tracking, and planned scenario types.

## Product

- `product/README.md` — product documentation index and the boundary between architecture decisions and product decisions.
- `product/homeassistant-and-smart-home-hub.md` — Home Assistant as edge runtime and actuation layer, platform's role beyond HA, integration principle, and roadmap alignment.
- `product/core-household-operating-picture.md` — core product definition: the Household Operating Picture, four core views (Overview, Money, Utilities, Operations), product principles, and acceptance criteria.
- `product/initial-capability-packs-and-publications.md` — domain pack definitions, publication sets, insight types, and priority ordering for finance, utilities, homelab, and overview.
- `product/core-product-design-workflow.md` — product design intake process and workflow.
- `product/product-slice-template.md` — template for new product slices.

## Sprints

- `sprints/household-operator-product-loop.md` — 4-sprint product delivery plan: Weekly Money View, Budget vs Reality, Debt and Cost Truth, Household Control Panel.
- `sprints/product-sprint-scope.md` — initial product sprint scope and deliverables.
- `sprints/product-sprint-remaining.md` — remaining product sprint work.
- `sprints/household-operator-implementation-plan.md` — implementation plan for the household operator product loop.
- `sprints/finance-loop.md` — finance domain sprint detail.
- `sprints/budget-variance.md` — budget variance sprint detail.
- `sprints/utilities-capability-pack-proof.md` — utilities capability pack proof sprint.
- `sprints/architecture-sprint-scope.md` — architecture sprint scope.
- `sprints/ingestion-operator-ergonomics.md` — ingestion operator ergonomics sprint.
- `sprints/homelab-capability-pack.md` — Sprint A: homelab capability pack (4 sources, 4 marts, homelab API routes). Done — PR #7.
- `sprints/category-governance.md` — Sprint B: category governance Phase 1 (backfill bug fix, budget-spend overlap test). Done — PR #8.
- `sprints/simulation-engine-sprint.md` — Sprint B: simulation engine (loan what-if first). Done.
- `sprints/scenarios-page-sprint.md` — Sprint F: scenarios history page and list API. Done.
- `sprints/expense-shock-sprint.md` — Sprint E+2: expense shock / tariff / cost-of-living scenario. Done.
- `sprints/ha-integration-hub-phase1.md` — Sprint G: HA integration hub Phase 1 (entity normalization bridge). Done.
- `sprints/documentation-reconciliation-and-adapter-stage.md` — documentation reconciliation, integration adapter stage, and roadmap update.

## Agents

- `agents/planning.md` — planning mode expectations and required plan verification.
- `agents/implementation.md` — implementation mode guardrails and required validation.
- `agents/review.md` — review mode findings-first expectations and architecture checks.
- `agents/release-ops.md` — local, CI, and deployment verification expectations.

## Decisions

- `decisions/household-operating-platform-direction.md` — operating platform identity evolution, 11-stage roadmap direction, relationship to Home Assistant, and relationship to existing ADRs.
- `decisions/household-platform-adr-and-refactor-blueprint.md` — modular monolith architecture, 5-layer model, capability pack registration, boundary enforcement, and migration plan.
- `decisions/operational-database-support-model.md` — canonical operational database support model: Postgres for operational truth, SQLite as local bootstrap fallback, and DuckDB as the worker/local warehouse engine.
- `decisions/compute-and-orchestration-options.md` — comparison of Spark and alternative engines/orchestrators, with the recommended initial stack and upgrade path.
- `decisions/auth-boundary-external-identity-internal-authorization.md` — auth boundary lock: external identity, in-app authorization semantics, service-token alignment, and narrow break-glass posture.

## Plans

- `plans/household-operating-platform-roadmap.md` — 11-stage roadmap from analytics platform to household operating platform, with stage descriptions, dependencies, and phase-to-stage mapping.
- `plans/ha-addon-and-integration-design.md` — design plan for the HA add-on (outbound bridge) and HA integration (inbound semantic surface): architecture, entity model, update model, API contracts, security model, and documentation outputs.
- `plans/homelab-analytics-platform-plan.md` — strategic decisions and rationale from the bootstrap phase. Detailed requirements now live in `requirements/` at the repository root.
- `plans/additional-data-domains.md` — planned data domains beyond account transactions, with source systems, canonical models, and marts for each.
- `plans/external-registry-inclusion.md` — control-plane plan and implementation direction for GitHub or custom-folder extension sources and custom-function registration.

## Notes

- `notes/appservice-cluster-integration-notes.md` — cluster deployment notes for the `appservice` GitOps repository.
- `notes/backend-owned-contracts-review-handover.md` — merged review handoff for the backend-owned contracts workstream, including commit landmarks, review hotspots, and verification.

## Runbooks

- `runbooks/operations.md` — deployment, ingress, readiness, and alert-response guidance for shared environments.
- `runbooks/backup-and-restore.md` — backup and restore guidance for Postgres control-plane state, landed object storage, and DuckDB artifacts.
- `runbooks/configuration.md` — environment variable reference for API, worker, web, auth, storage, and extension configuration.
