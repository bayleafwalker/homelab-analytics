# Semantic Contracts

**Classification:** PLATFORM

Semantic contracts define how the canonical model is extended without turning reporting relations into one-off, domain-local shapes.

They sit between the transformation-layer model and the reporting/publication surface:

- landing owns source-shaped payloads and validation only
- transformation owns canonical dimensions, facts, and SCD history
- reporting owns current snapshots, marts, and publication contracts consumed by APIs and renderers

## Contract rules

- Shared dimensions must be named once and reused across domains. Do not create parallel per-domain copies when a dimension already exists in transformation.
- When a shared dimension is promoted, update the relevant requirements entry and publication contract in the same change. Do not leave a promoted dimension half-documented between transformation and reporting.
- Reporting-facing current dimensions must publish an explicit semantic contract. Do not rely on inferred-only metadata when the relation is intended to be a durable app or renderer surface.
- The current-dimension publication key stays aligned to the canonical dimension name, while the backing relation remains `rpt_current_dim_*`.
- Surrogate key columns such as `sk` are identifiers in contract metadata, not anonymous string dimensions.
- New cross-domain semantics should move from free-text bridges to canonical identifiers over time. Temporary bridge fields must be called out explicitly in docs and contract descriptions.
- App-facing reads continue to use reporting-layer relations only. Do not add landing-to-dashboard shortcuts to expose partially normalized semantics.

## Current shared dimensions

| Dimension | Role | Notes |
|---|---|---|
| `dim_category` | Shared category registry | Used across budgets and cost attribution; publication contract is explicit. |
| `dim_counterparty` | Shared finance-facing counterparty dimension | `category_id` FK added (Sprint Q); populated by backfill from `dim_category`. Free-text `category` bridge retained for backward compat — full removal deferred. |
| `dim_contract` | Shared contract/provider spine | Reused by subscriptions and contract-pricing flows; provider is still embedded as text, not a separate shared dimension. |
| `dim_meter` | Shared utility metering spine | Reused across utility usage and billing domains. |
| `dim_household_member` | Shared household-member dimension | Implemented Sprint Q. Default `household` member seeded at startup. Natural key: `member_id`. |

## Current domain-local dimensions

These are canonical, but they are still domain-owned rather than cross-domain registries:

- `dim_account`
- `dim_budget`
- `dim_loan`
- `dim_asset`
- `dim_entity`
- `dim_node`
- `dim_device`
- `dim_service`
- `dim_workload`

Domain-local does not mean ad hoc. Each still needs reporting-layer publication semantics when exposed to apps or renderer consumers.

## Known governance gaps

- `fact_balance_snapshot` is implemented as the Stage 1 point-in-time balance fact across account and loan balances.
- `dim_counterparty.category` free-text bridge is retained for backward compat; `category_id` is now populated by backfill but full bridge-column removal is deferred.
- Provider semantics still live inside domain-local string columns such as `dim_contract.provider`; there is no shared provider dimension yet.

## Publication confidence metadata

**Trust source:** `publication_confidence_snapshot` table in the control plane store (Postgres or SQLite).

**Fields:** 
- `freshness_state` (lowercase StrEnum: current, due_soon, overdue, missing_period, unconfigured)
- `completeness_pct` (integer 0 or 100, binary presence flag — TODO: replace with proportional)
- `confidence_verdict` (lowercase StrEnum: trustworthy, degraded, unreliable, unavailable)
- `assessed_at` (ISO 8601 UTC timestamp string)

**Where exposed:** `PublicationContract` dataclass (`packages/platform/publication_contracts.py`), `GET /contracts/publications`, exported `publication-contracts.json` artifact.

**Casing convention:** All enum string values are lowercase, matching `ConfidenceVerdict` and `FreshnessState` StrEnums in `packages/platform/publication_confidence.py`.

**Catalog versioning:** The `publication-contracts.json` artifact includes a top-level `catalog_schema_version` field that bumps when confidence metadata fields are added or modified (current: `1.1.0`). This field is **artifact-only** — it is not surfaced by the live `GET /contracts/publications` API, which uses `build_publication_contracts()` rather than the catalog builder.

## Change checklist

When adding or changing semantic contracts:

- update the relevant requirements entry under `requirements/`
- update this document if the shared-vs-local dimension boundary changes
- add or update focused publication-contract tests
- regenerate committed contract artifacts under `apps/web/frontend/generated/` when exported contracts change
