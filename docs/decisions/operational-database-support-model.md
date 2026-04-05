# ADR: Operational Database Support Model

**Classification:** PLATFORM
**Status:** Accepted
**Owner:** Juha
**Decision type:** Architecture / storage support model
**Applies to:** Control-plane state, landing metadata, published reporting, local bootstrap workflows, worker warehouse flows

---

## 1. Executive summary

The platform standardizes on **Postgres as the canonical operational database**.

That means:

- Postgres is the operational truth for control-plane state, landing metadata, run metadata, auth state, scheduling state, lineage, and published reporting relations.
- SQLite remains supported only as a **local bootstrap and smoke-test fallback**.
- DuckDB remains the **analytical worker and local-development warehouse engine** for transformation and local reporting iteration.

The project is **not** committing to long-term feature parity across SQLite, Postgres, and DuckDB for operational storage.

---

## 2. Context

The repository grew support for multiple backends during bootstrap so the platform could ship early ingestion, transformation, and reporting paths without immediately requiring a shared Postgres deployment.

That bootstrap flexibility now creates the wrong expectation in some docs:

- SQLite, Postgres, and DuckDB are sometimes described as if they are equal long-term database targets.
- control-plane and landing-metadata work risks being designed around lowest-common-denominator database behavior
- reporting can appear to treat warehouse reads as the primary application contract instead of a worker concern

This creates avoidable cost:

- migration burden increases because operational features must be implemented, migrated, and documented across multiple engines
- feature friction increases when scheduling, auth, lineage, or control-plane changes have to preserve SQLite semantics that are not the intended shared-deployment target
- dialect drift increases when the repo tries to keep operational SQL behavior aligned across SQLite, Postgres, and DuckDB even though those engines serve different roles

The platform-first direction needs a clearer support model.

---

## 3. Decision

### 3.1 Canonical operational database

Postgres is the canonical operational database for shared and production-oriented deployments.

It owns:

- control-plane configuration and registry state
- landing and validation metadata
- ingestion run metadata
- auth, scheduling, dispatch, lineage, and audit state
- published reporting relations used by API and application-facing reads

New operational capabilities should be designed **Postgres-first**.

### 3.2 SQLite role

SQLite remains in the repository as a retained compatibility path for:

- local bootstrap
- smoke and adapter tests
- single-node convenience flows
- controlled snapshot export/import and local recovery drills

SQLite is **not** a co-equal long-term operational target. Documentation should describe it as a local or transitional fallback, not as a parity commitment.

### 3.3 DuckDB role

DuckDB remains the warehouse engine for:

- transformation-layer fact and dimension persistence
- worker-local analytical queries
- local-development reporting iteration
- scenario and other analytical workloads that belong with the warehouse

DuckDB stays central to the analytical path. This ADR does **not** remove DuckDB from the platform.

DuckDB warehouse reads are not the application's primary shared-production contract. Application-facing reads should prefer published reporting relations when those are configured.

### 3.4 Reporting contract

Published reporting may continue to target Postgres, and that published layer is the preferred application contract for shared deployments.

Warehouse reads may still exist for worker flows and local development, but the platform should not present direct DuckDB reads as the default production read path for the application surface.

---

## 4. Consequences

### Positive

- clearer operational target for new control-plane work
- lower migration burden for future control-plane features
- less feature friction when concurrency, auth, scheduling, and audit behavior evolve
- less SQL dialect drift in the operational path
- cleaner separation between operational state and analytical warehouse responsibilities

### Tradeoffs

- local bootstrap defaults may remain different from the canonical shared-deployment target for a period of time
- some SQLite compatibility code and tests will remain until the repo chooses to retire them explicitly
- docs must distinguish between canonical support, retained compatibility, and local-development convenience

---

## 5. Non-goals

This ADR does not:

- promise immediate removal of SQLite support
- remove DuckDB as an analytical engine
- require immediate runtime-default changes in code
- forbid local development paths that still use SQLite and DuckDB together

Those follow-ups can happen incrementally. The decision here is the support model and the language the repository should use now.

---

## 6. Required documentation posture

Repository docs should consistently reflect the following model:

- **Postgres** = operational truth, control plane, landing metadata, published reporting
- **SQLite** = local bootstrap fallback and smoke-test convenience only
- **DuckDB** = transformation/reporting warehouse engine for workers and local development

Docs should stop implying full long-term operational parity across all three engines.
