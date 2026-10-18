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

| Dimension | Domain | Contract status |
|---|---|---|
| `dim_account` | Finance | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_budget` | Finance | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_loan` | Finance | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_asset` | Finance / inventory | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_entity` | Home automation | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_node` | Homelab infrastructure | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_device` | Homelab infrastructure | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_service` | Homelab services | Explicit contract; `CurrentDimensionContractDefinition` published |
| `dim_workload` | Homelab services | Explicit contract; `CurrentDimensionContractDefinition` published |

Domain-local does not mean ad hoc. All nine dimensions have explicit `CurrentDimensionContractDefinition` entries in `packages/pipelines/composition/current_dimension_contracts.py` and are accessible via `ReportingService.get_current_dimension_rows()` through `CURRENT_DIMENSION_RELATIONS`.

## Known governance gaps

- `fact_balance_snapshot` is implemented as the Stage 1 point-in-time balance fact across account and loan balances.
- `dim_counterparty.category` free-text bridge is retained for backward compat; `category_id` is now populated by backfill but full bridge-column removal is deferred.
- Provider semantics still live inside domain-local string columns such as `dim_contract.provider`; there is no shared provider dimension yet.
- Lineage-declared sources (`source_lineage.source_system`) without a source freshness config still default to `current` freshness; the count is surfaced as `quality_flags.freshness_unconfigured_sources` rather than degrading the verdict.

## Publication confidence metadata

**Trust source:** `publication_confidence_snapshot` table in the control plane store (Postgres or SQLite).

**Fields:** 
- `freshness_state` (lowercase StrEnum: current, due_soon, overdue, missing_period, unconfigured)
- `completeness_pct` (integer 0–100, see below)
- `confidence_verdict` (lowercase StrEnum: trustworthy, degraded, unreliable, unavailable)
- `assessed_at` (ISO 8601 UTC timestamp string)
- `quality_flags` (object of integer counters, see below)

**Signal semantics** (computed by `packages/pipelines/publication_confidence_service.py`, verdict rules in `packages/platform/publication_confidence.py`). Confidence reads landing-layer evidence (run metadata validation outcomes) and control-plane lineage; it does not read landing payloads and does not change the landing → transformation → reporting split.

- *Contributing sources*: source lineage rows targeting the publication key; each names its source via `source_system`, or via its run's `source_name` in run metadata. The latest lineage run per source is the contributing run (`contributing_run_ids`).
- *Validation*: for each contributing run, the landing validation issues and pass/fail recorded in run metadata, plus any later landing for the same source and dataset that was rejected before `assessed_at`. Reported as `validation_errors` (issue count), `rejected_runs`, and `validation_unknown_runs` (contributing runs with no run metadata). `validation_errors` is omitted when no run could be inspected — the signal is then *unknown*.
- *Completeness*: share of contributing sources whose contributing run is verifiably present (in run metadata, passed, at least one landed row, and at least one loaded row when lineage records a count). Reported as `completeness_expected_sources`, `completeness_covered_sources`, `completeness_unknown_sources`; unresolvable sources count as not covered in `completeness_pct`.
- *Unknown never upgrades*: `trustworthy` requires all sources `current`, `completeness_pct == 100` with no unknown sources, and validation known with zero errors and zero rejected runs. Validation errors or stale sources give `degraded`, or `unreliable` when completeness is below 50% even counting every unknown source as covered. Any other non-perfect or unknown signal gives `degraded`; no sources, or all sources unconfigured, gives `unavailable`.
- `PublicationConfidenceSnapshot.validation_state` / `.completeness_state` expose `known` / `partial` / `unknown` derived from `quality_flags`. Snapshots recorded before these flags existed carry a hardcoded `validation_errors: 0` and binary completeness; treat them as legacy.

**Where exposed:** `PublicationContract` dataclass (`packages/platform/publication_contracts.py`), `GET /contracts/publications`, exported `publication-contracts.json` artifact.

**Casing convention:** All enum string values are lowercase, matching `ConfidenceVerdict` and `FreshnessState` StrEnums in `packages/platform/publication_confidence.py`.

**Catalog versioning:** The `publication-contracts.json` artifact includes a top-level `catalog_schema_version` field that bumps when confidence metadata fields are added or modified (current: `1.1.0`). This field is **artifact-only** — it is not surfaced by the live `GET /contracts/publications` API, which uses `build_publication_contracts()` rather than the catalog builder.

## Change checklist

When adding or changing semantic contracts:

- update the relevant requirements entry under `requirements/`
- update this document if the shared-vs-local dimension boundary changes
- add or update focused publication-contract tests
- regenerate committed contract artifacts under `apps/web/frontend/generated/` when exported contracts change
