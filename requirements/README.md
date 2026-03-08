# Requirements Baseline

This folder is the authoritative source for product and technical requirements.

Each document follows a common template (see below) and covers one requirement domain. Requirements are uniquely identified, phased, and linked to acceptance criteria so that implementation and test coverage can be traced back to stated goals.

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

| Phase | Name | Focus |
|---|---|---|
| 0 | Bootstrap | Repo structure, planning docs, first scaffold vertical slice |
| 1 | Foundation | Production stack, first complete dataset through all three layers |
| 2 | Generalization | Multiple datasets, generic connectors, frontend |
| 3 | Household packs | Utility, loan, budget, cluster analytics |
| 4 | Productization | Auth, CI/CD, public release, admin UI |

## Conventions

- Requirement IDs are stable — never reuse a retired ID.
- Phase assignments are targets, not guarantees; adjust as scope clarifies.
- Status tracks implementation, not importance.
- Acceptance criteria must be testable — prefer "pytest passes X" or "API returns Y" over vague quality statements.
