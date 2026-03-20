# Documentation

## Requirements

The authoritative requirements baseline lives at `requirements/` in the repository root. See `requirements/README.md` for the template, phase definitions, stage alignment, and document index.

## Architecture

- `architecture/data-platform-architecture.md` — source ingestion pattern, landing/bronze, transformation/silver, reporting/gold, SCD handling, extensibility model, and API/UI publishing model. Also covers forward-looking architectural layers: semantic domain, planning/scenario, policy/automation, multi-renderer delivery, pack ecosystem, and trust/governance.
- `architecture/homeassistant-integration-hub.md` — six-layer integration hub architecture: entity normalization bridge, bidirectional event/command fabric, synthetic entity publication model, and resilience model.

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

## Agents

- `agents/planning.md` — planning mode expectations and required plan verification.
- `agents/implementation.md` — implementation mode guardrails and required validation.
- `agents/review.md` — review mode findings-first expectations and architecture checks.
- `agents/release-ops.md` — local, CI, and deployment verification expectations.

## Decisions

- `decisions/household-operating-platform-direction.md` — operating platform identity evolution, 10-stage roadmap direction, relationship to Home Assistant, and relationship to existing ADRs.
- `decisions/household-platform-adr-and-refactor-blueprint.md` — modular monolith architecture, 5-layer model, capability pack registration, boundary enforcement, and migration plan.
- `decisions/compute-and-orchestration-options.md` — comparison of Spark and alternative engines/orchestrators, with the recommended initial stack and upgrade path.

## Plans

- `plans/household-operating-platform-roadmap.md` — 10-stage roadmap from analytics platform to household operating platform, with stage descriptions, dependencies, and phase-to-stage mapping.
- `plans/ha-addon-and-integration-design.md` — design plan for the HA add-on (outbound bridge) and HA integration (inbound semantic surface): architecture, entity model, update model, API contracts, security model, and documentation outputs.
- `plans/homelab-analytics-platform-plan.md` — strategic decisions and rationale from the bootstrap phase. Detailed requirements now live in `requirements/` at the repository root.
- `plans/additional-data-domains.md` — planned data domains beyond account transactions, with source systems, canonical models, and marts for each.
- `plans/external-registry-inclusion.md` — control-plane plan and implementation direction for GitHub or custom-folder extension sources and custom-function registration.

## Notes

- `notes/appservice-cluster-integration-notes.md` — cluster deployment notes for the `appservice` GitOps repository.

## Runbooks

- `runbooks/operations.md` — deployment, ingress, readiness, and alert-response guidance for shared environments.
- `runbooks/backup-and-restore.md` — backup and restore guidance for Postgres control-plane state, landed object storage, and DuckDB artifacts.
- `runbooks/configuration.md` — environment variable reference for API, worker, web, auth, storage, and extension configuration.
