# Documentation

## Requirements

The authoritative requirements baseline lives at `requirements/` in the repository root. See `requirements/README.md` for the template, phase definitions, and document index.

## Architecture

- `architecture/data-platform-architecture.md` — source ingestion pattern, landing/bronze, transformation/silver, reporting/gold, SCD handling, and API/UI publishing model.

## Agents

- `agents/planning.md` — planning mode expectations and required plan verification.
- `agents/implementation.md` — implementation mode guardrails and required validation.
- `agents/review.md` — review mode findings-first expectations and architecture checks.
- `agents/release-ops.md` — local, CI, and deployment verification expectations.

## Decisions

- `decisions/compute-and-orchestration-options.md` — comparison of Spark and alternative engines/orchestrators, with the recommended initial stack and upgrade path.

## Plans

- `plans/homelab-analytics-platform-plan.md` — strategic decisions and rationale from the bootstrap phase. Detailed requirements now live in `requirements/` at the repository root.
- `plans/additional-data-domains.md` — planned data domains beyond account transactions, with source systems, canonical models, and marts for each.

## Notes

- `notes/appservice-cluster-integration-notes.md` — cluster deployment notes for the `appservice` GitOps repository.
