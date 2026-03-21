# Requirements Baseline

This folder is the authoritative source for product and technical requirements for the household operating platform.

Each document follows a common template (see below) and covers one requirement domain. Requirements are uniquely identified, phased, and linked to acceptance criteria so that implementation and test coverage can be traced back to stated goals. The phase model aligns with the 11-stage operating platform roadmap defined in `docs/plans/household-operating-platform-roadmap.md`.

## Documents

| Document | Domain |
|---|---|
| [data-ingestion.md](data-ingestion.md) | Source onboarding, connectors, file/folder/API ingestion |
| [data-platform.md](data-platform.md) | Landing, transformation, reporting layers and data modeling |
| [analytics-and-reporting.md](analytics-and-reporting.md) | Derived analytics, marts, projections, household models |
| [application-services.md](application-services.md) | API, web UI, worker CLI, service endpoints |
| [security-and-operations.md](security-and-operations.md) | Auth, secrets, observability, deployment, release |

## Template

Every requirements document uses the following structure:

```
# <Domain> Requirements

## Overview
One-paragraph summary of the domain and why it exists.

## Requirements
Each requirement has:
- **ID** — unique, prefixed by domain code (e.g. ING-01)
- **Title** — short imperative statement
- **Description** — what the system must do
- **Rationale** — why it matters
- **Phase** — target implementation phase (0–4)
- **Status** — not-started | in-progress | implemented | deferred
- **Acceptance criteria** — observable, testable conditions
- **Dependencies** — other requirement IDs this depends on
- **Notes** — clarifications, open questions, design choices

## Traceability
Links to architecture docs, implementation modules, and tests.
```

## Phases

| Phase | Name | Focus | Stage alignment |
|---|---|---|---|
| 0 | Bootstrap | Repo structure, planning docs, first scaffold vertical slice | Stage 0 |
| 1 | Foundation | Production stack, first complete dataset through all three layers | Stages 0–1 |
| 2 | Generalization | Multiple datasets, generic connectors, operating views | Stages 1–2 |
| 3 | Household operating model | Budget, loans, cost model, planning surfaces, homelab operations | Stages 2–3 |
| 4 | Platform maturity | Auth, CI/CD, multi-renderer, policy, ecosystem foundations | Stages 3–5 |

## Conventions

- Requirement IDs are stable — never reuse a retired ID.
- Phase assignments are targets, not guarantees; adjust as scope clarifies.
- The phase model was expanded in the Stage 0 documentation reset to align with the operating-platform roadmap. Requirement IDs and statuses remain stable across all phases.
- Status tracks implementation, not importance.
- Acceptance criteria must be testable — prefer "pytest passes X" or "API returns Y" over vague quality statements.

## Verification

- `tests/test_requirements_contract.py` enforces the shared requirement template, allowed status values, and traceability path existence.
- Requirement changes should be accompanied by implementation and test updates in the same change when status moves to `in-progress` or `implemented`.
- Local backend verification now also includes `make test-storage-adapters` for filesystem/S3 blob behavior plus SQLite/Postgres metadata-store and Postgres publication coverage.
