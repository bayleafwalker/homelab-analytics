# Data Platform Requirements

## Overview

The platform implements a three-layer data architecture — landing (bronze), transformation (silver), and reporting (gold) — with explicit contracts between layers. Landing owns immutability and validation. Transformation owns normalization, SCD dimensions, and canonical models. Reporting owns consumer-facing views, marts, and API datasets.

---

## Requirements

### PLT-01: Immutable raw payload storage

**Description:** Every ingestion run persists the original payload unchanged to immutable storage. Raw payloads must never be modified after landing.

**Rationale:** Immutability ensures auditability, reprocessing capability, and source-of-truth preservation.

**Phase:** 0–1
**Status:** implemented (filesystem remains the default local blob store, manual/config-driven filesystem and HTTP ingestion preserve original payload bytes, and an S3-compatible adapter now exists for production-oriented landing storage)

**Acceptance criteria:**
- Raw file bytes are written to blob storage exactly as received.
- No downstream process modifies or deletes landed payloads.
- Payloads are addressable by dataset, date partition, and run ID.
- S3-compatible blob store adapter is available for production use (Phase 1).

**Dependencies:** none

---

### PLT-02: Run identification and metadata

**Description:** Each ingestion run receives a unique run ID. Metadata includes: source, dataset, timestamp, file hash (SHA-256), schema fingerprint, row count, source metadata, and status (received/landed/rejected/failed).

**Rationale:** Run-level metadata enables lineage tracking, reprocessing, deduplication, and operational monitoring.

**Phase:** 0
**Status:** implemented (Postgres-backed run metadata is the canonical operational target, while the existing SQLite path remains in place as a local bootstrap fallback)

**Acceptance criteria:**
- Every ingestion writes a run record with all specified metadata fields.
- Run records are queryable by status, dataset, and date range.
- Postgres adapter is available for the canonical shared-deployment path (Phase 1).

**Dependencies:** none

---

### PLT-03: Data quality and contract validation

**Description:** Each ingestion run is validated against its dataset contract before promotion. Validation checks include: required columns, column type compatibility, duplicate columns, unexpected columns, row-level type validation with row/column error references, duplicate file detection by content hash, row count thresholds, value enumeration checks, and source freshness checks.

**Rationale:** Catching data problems at landing prevents bad data from contaminating transformation and reporting layers.

**Phase:** 0
**Status:** implemented (6 type validators, contract-driven, row-level reporting; config-driven sources validate a canonical mapped projection while still persisting the raw payload unchanged)

**Acceptance criteria:**
- Valid files pass and are promoted; invalid files are rejected with specific issue details.
- Validation issues include row number, column name, issue type, and message.
- Failed runs remain queryable but are not promoted.
- Tests cover valid, missing-column, and invalid-value scenarios.

**Dependencies:** none

---

### PLT-04: Landing storage layout

**Description:** Raw payloads are stored in a date-partitioned path: `{dataset}/{YYYY}/{MM}/{DD}/{run_id}/`. A JSON manifest with validation results and metadata accompanies each payload.

**Rationale:** Consistent partitioning enables efficient browsing, retention policies, and reprocessing of specific time windows.

**Phase:** 0
**Status:** implemented

**Acceptance criteria:**
- Landed files follow the partitioned path convention.
- JSON manifest includes run ID, file hash, row count, validation status, and issue list.
- Manifest is written atomically alongside the raw payload.

**Dependencies:** PLT-01

---

### PLT-05: Canonical fact models

**Description:** The transformation layer produces reusable, source-agnostic fact tables.

| Fact | Description | Phase |
|---|---|---|
| `fact_transaction` | All monetary transactions (account + card) | 1 |
| `fact_subscription_charge` | Subscription and recurring-service charge records | 2 |
| `fact_contract_price` | Temporal contract pricing and tariff rows | 2 |
| `fact_balance_snapshot` | Point-in-time account and loan balances | 2 |
| `fact_utility_usage` | Metered utility consumption | 3 |
| `fact_bill` | Invoiced charges from providers | 3 |
| `fact_loan_repayment` | Actual and planned repayment events | 3 |
| `fact_cluster_metric` | Homelab infrastructure metrics | 3 |
| `fact_power_consumption` | Sampled device power draw | 3 |
| `fact_asset_event` | Acquisition, disposal, and depreciation events for tracked assets | 3 |
| `fact_sensor_reading` | Home automation state snapshots | 3 |
| `fact_automation_event` | Home automation automation events | 3 |

**Rationale:** Canonical facts decouple source-specific formats from downstream analytics and enable cross-source joining.

**Phase:** 1–3
**Status:** in-progress (`fact_transaction`, `fact_subscription_charge`, `fact_contract_price`, `fact_utility_usage`, `fact_bill`, `fact_cluster_metric`, `fact_power_consumption`, `fact_asset_event`, `fact_sensor_reading`, and `fact_automation_event` are persisted in DuckDB via `TransformationService`; balance and loan facts are not started)

**Acceptance criteria:**
- Each fact table is persisted in DuckDB/Parquet with documented schema.
- Fact tables are source-agnostic — the same fact schema accepts data from multiple sources via column mappings.
- Tests verify fact population from at least two different source formats per fact (where applicable).

**Dependencies:** PLT-07, ING-08

---

### PLT-06: Canonical dimension models

**Description:** The transformation layer produces reusable, source-agnostic dimension tables.

| Dimension | Description | Phase |
|---|---|---|
| `dim_account` | Bank, investment, and loan accounts | 1 |
| `dim_counterparty` | Payees, merchants, transfer targets | 1 |
| `dim_contract` | Service contracts, subscriptions, and temporal tariffs | 2–3 |
| `dim_meter` | Utility meters | 3 |
| `dim_node` | Cluster nodes | 3 |
| `dim_device` | Physical infrastructure devices | 3 |
| `dim_loan` | Loan instruments with terms | 3 |
| `dim_asset` | Physical and digital assets | 3 |
| `dim_entity` | Home automation entities | 3 |
| `dim_household_member` | Household members for attribution | 2 |
| `dim_category` | Transaction/cost categories | 2 |
| `dim_budget` | Budget definitions and periods | 3 |

**Rationale:** Canonical dimensions enable consistent attribution across all facts and support SCD-based historical analysis.

**Phase:** 1–3
**Status:** in-progress (`dim_account` and `dim_counterparty` are implemented with SCD-2 in DuckDB; `dim_contract` supports subscriptions and temporal contract-pricing domains; `dim_category` is implemented for shared category use; `dim_meter` now supports utility usage and billing domains; `dim_node`, `dim_device`, and `dim_asset` now support infrastructure and asset domains; `dim_entity` now supports home automation state; remaining dimensions are not started)

**Acceptance criteria:**
- Each dimension is persisted with SCD Type 2 handling (see PLT-07).
- Natural keys and surrogate keys are separate.
- Tests verify dimension creation, update (new version), and current-view accuracy.

**Dependencies:** PLT-07

---

### PLT-07: Slowly changing dimension handling

**Description:** Dimensions with attributes that can change over time are persisted as SCD Type 2 with: `valid_from`, `valid_to`, `is_current`, surrogate key, and source lineage columns (`source_system`, `source_run_id`).

**Rationale:** SCD Type 2 preserves historical context for point-in-time reporting without losing current state.

**Phase:** 1
**Status:** implemented (`DuckDBStore` now persists SCD-2 insert, update, close, current-view, and point-in-time queries together with `source_system` and `source_run_id` lineage columns on current and historical dimension rows)

**Acceptance criteria:**
- Inserting a new dimension record sets `is_current = TRUE` and `valid_to = NULL` (or far-future sentinel).
- Updating an existing dimension record closes the previous version (`is_current = FALSE`, `valid_to = update_date`) and inserts a new current version.
- Current-dimension views return only `is_current = TRUE` rows.
- Tests verify insert, update, and point-in-time query behavior.

**Dependencies:** none

---

### PLT-08: Source-agnostic normalization

**Description:** Transformation standardizes: naming conventions, data types, time semantics (UTC), currencies (original preserved, normalized if applicable), units (kWh, liters), and identifiers (natural keys mapped to surrogate keys).

**Rationale:** Consistent representation enables cross-source analytics and simplifies reporting logic.

**Phase:** 1
**Status:** in-progress (`TransformationService` now persists UTC timestamps, preserves original currency while deriving `normalized_currency`, and standardizes quantity units used by the contract-pricing domain; broader multi-domain normalization is still pending)

**Acceptance criteria:**
- All timestamps are stored in UTC.
- Amounts preserve original currency and include a normalized currency field.
- Unit fields use standardized enumeration values.
- Tests verify normalization from at least two differently formatted source files.

**Dependencies:** ING-08, PLT-05, PLT-06

---

### PLT-09: Transformation independence

**Description:** Transformation logic is independent of any specific dashboard layout or reporting requirement. Models serve multiple downstream consumers.

**Rationale:** Tight coupling between transformation and reporting prevents reuse and forces rework when dashboards change.

**Phase:** 1
**Status:** implemented (transformation modules remain independent of application/reporting modules, and reporting marts are exercised through shared fact tables)

**Acceptance criteria:**
- No transformation module imports from reporting modules.
- Fact and dimension schemas are documented independently of any specific mart.
- At least two different reporting marts consume the same fact table in tests.

**Dependencies:** none

---

### PLT-10: Bridge and helper models

**Description:** Support supplementary models: tag/category mappings, budget allocations, source column mapping references, and reconciliation/lineage metadata.

**Rationale:** Bridge tables enable many-to-many relationships (e.g. transaction-to-category) and lineage tables enable auditability beyond run metadata.

**Phase:** 2–3
**Status:** in-progress (control-plane repositories now persist source-lineage and publication-audit metadata; category and budget bridge models remain pending)

**Acceptance criteria:**
- Category mapping bridge persists user-defined or rule-inferred category assignments.
- Budget allocation bridge links budget definitions to categories and periods.
- Lineage metadata records which source run populated which fact/dimension rows.

**Dependencies:** PLT-05, PLT-06

---

### PLT-11: Current dimension views (reporting)

**Description:** The reporting layer publishes current-time snapshots of SCD dimensions (`WHERE is_current = TRUE`).

**Rationale:** Dashboard and API consumers need simple, current-state views without knowing SCD mechanics.

**Phase:** 1
**Status:** in-progress (reporting views now publish current snapshots for `dim_account`, `dim_counterparty`, `dim_contract`, `dim_category`, and `dim_meter`; FastAPI exposes them via `GET /reports/current-dimensions/{dimension_name}`, and the Postgres publication path mirrors the implemented current-dimension relations for the shared app-facing contract when configured)

**Acceptance criteria:**
- Each SCD dimension has a corresponding current-view in the reporting layer.
- Current views are queryable via the API and used by dashboard marts.
- Tests verify that current views return exactly one row per natural key.

**Dependencies:** PLT-07

---

### PLT-12: Dashboard-oriented reporting marts

**Description:** The reporting layer produces consumer-facing analytical models:

| Mart | Phase |
|---|---|
| Monthly household cash-flow | 1 |
| Subscription summary | 2 |
| Current contract prices | 2 |
| Current electricity tariffs | 2 |
| Monthly electricity cost and usage | 3 |
| Loan repayment plan vs. actual | 3 |
| Recurring cost baseline | 3 |
| Budget vs. actual | 3 |
| Household cost summary | 3 |
| Homelab service cost | 3 |
| Net worth estimate | 3 |

**Rationale:** Marts provide the stable query surfaces that dashboards and APIs consume.

**Phase:** 1–3
**Status:** in-progress (`TransformationService` materialises `mart_monthly_cashflow`, `mart_subscription_summary`, `mart_contract_price_current`, `mart_electricity_price_current`, and `mart_utility_cost_summary` in DuckDB; a Postgres publication path now mirrors the implemented marts and current-dimension snapshots, including `rpt_current_dim_entity`, for shared app-facing reads when configured, and remaining marts are still not implemented)

**Acceptance criteria:**
- Each application-facing mart is materialized in Postgres with a documented schema.
- Marts are refreshable from transformation-layer inputs.
- The API exposes each mart through a reporting endpoint.
- Tests verify mart content from known fixture data.

**Dependencies:** PLT-05, PLT-06, PLT-11

---

### PLT-13: Exportable datasets

**Description:** Users can export reporting datasets as CSV or Parquet for offline analysis.

**Rationale:** Power users and external tools need raw data access beyond dashboard views.

**Phase:** 2
**Status:** not-started

**Acceptance criteria:**
- API endpoint accepts a mart name and optional filters, returns CSV or Parquet.
- Export respects the same access controls as the dashboard.

**Dependencies:** PLT-12

---

### PLT-14: Persistent analytical store

**Description:** Standardize on Postgres as the canonical operational database for control-plane state, landing metadata, and published reporting; retain SQLite only as a local bootstrap fallback; and use DuckDB/Parquet for transformation-layer intermediate storage and local analytical work.

**Rationale:** SQLite is inadequate for concurrent access, multi-process workers, and production-scale metadata. Maintaining peer operational support across SQLite, Postgres, and DuckDB would increase migration burden, feature friction, and dialect drift. DuckDB provides efficient columnar analytics without Spark overhead and remains the right warehouse engine for worker and local-development use.

**Phase:** 1
**Status:** in-progress (DuckDB is already the transformation store, runtime backend selection still supports SQLite or Postgres for control-plane and metadata wiring, and Postgres-backed publication storage now exists for implemented marts/current dimensions; the remaining work is to complete the Postgres-first operational direction and keep the SQLite path clearly scoped as a local fallback instead of a parity promise)

**Acceptance criteria:**
- Postgres adapter implements `RunMetadataStore` protocol and passes storage adapter verification.
- Postgres is the documented canonical operational store for control-plane, landing metadata, and published reporting.
- DuckDB is used for transformation-layer reads and writes (fact/dimension persistence).
- Polars is used for in-process data manipulation replacing stdlib CSV processing.
- Existing SQLite path remains only as a development fallback and is documented as transitional rather than parity-critical.

**Dependencies:** none

---

### PLT-15: Atomic run processing

**Description:** A failed transformation must not leave partial results in the reporting layer. Processing is atomic at the run level.

**Rationale:** Partial writes corrupt downstream analytics and are difficult to debug or repair.

**Phase:** 1
**Status:** implemented (`DuckDBStore.atomic()` context manager wraps all statements in a DuckDB transaction; `TransformationService.load_transactions()` runs dimension upserts and fact inserts inside a single `atomic()` block — a failure before commit rolls back all partial writes; test verifies that an injected failure during fact insert leaves zero dimension and fact rows)

**Acceptance criteria:**
- Transformation writes are atomic; only a successful run commits results to the published layer.
- A simulated mid-transformation failure leaves no partial fact or dimension rows.
- Tests verify atomicity by injecting a failure during transformation.

**Dependencies:** PLT-05, PLT-14

---

### PLT-16: Idempotent ingestion

**Description:** Re-submitting the same file is detected by content hash and handled gracefully: rejected as duplicate or accepted with deduplication metadata.

**Rationale:** Users and automated systems may inadvertently submit the same file twice. Silent duplication corrupts analytics.

**Phase:** 1
**Status:** implemented (`RunMetadataRepository.find_run_by_sha256(sha256, dataset_name=...)` scopes duplicate detection to the target dataset; `LandingService` injects a `duplicate_file` ValidationIssue when a matching passed run is found, causing the second submission to be stored as REJECTED with a reference to the original run ID)

**Acceptance criteria:**
- Submitting an identical file (by SHA-256) to the same dataset returns a duplicate status.
- The duplicate run references the original run ID.
- Tests verify duplicate detection for identical file contents.

**Dependencies:** PLT-02

---

### PLT-17: Audit trail

**Description:** Every ingestion run, transformation execution, and reporting materialization is logged with sufficient metadata for debugging and lineage reconstruction.

**Rationale:** A complete audit trail is essential for trust in derived analytics and for debugging data issues.

**Phase:** 1–2
**Status:** in-progress (ingestion audit is complete via `RunMetadataRepository`; transformation audit is implemented in DuckDB; control-plane repositories now persist source-lineage plus publication-audit records for published reporting refreshes, and API control endpoints can query that metadata; broader mart/run traceability and non-published reporting audit remain pending)

**Acceptance criteria:**
- Ingestion audit: run ID, timestamp, source, file hash, validation status, issue count.
- Transformation audit: input run IDs, output fact/dimension counts, processing duration.
- Reporting audit: mart name, refresh timestamp, input transformation runs.
- Audit records are queryable via the API.

**Dependencies:** PLT-02, PLT-05, PLT-12

---

### PLT-18: Run promotion orchestration

**Description:** The runtime exposes one supported path to promote landed runs into transformation and reporting storage. Built-in datasets must not require separate ad hoc execution paths for landing versus silver/gold publication.

**Rationale:** Split execution paths create drift between what ingestion stores and what reporting publishes, which breaks lineage and makes operational behavior harder to reason about.

**Phase:** 1
**Status:** implemented (manual and config-driven built-in runs now promote through one source-asset-driven path; `transformation_package` selects the canonical promotion handler, control-plane package creation validates `handler_key` values against the loaded promotion-handler registry, control-plane publication-definition creation and config preflight reject built-in publication keys that are unsupported by the selected package handler, `publication_definition` constrains which marts refresh, config-driven sources preserve raw bronze bytes while storing a canonical projection artifact for promotion, re-promoting the same run is a retry-safe no-op, and extension modules can register custom transformation domains and canonical promotion handlers through the same registry contract)

**Acceptance criteria:**
- A worker or API entrypoint can promote a landed run into the configured transformation store.
- Promotion dispatch is driven by persisted source-asset configuration rather than route-local or header-inference heuristics.
- Config-driven runs that preserve source-shaped bronze payloads can still promote through a canonical projection artifact without reparsing the raw source format.
- Re-promoting an already promoted run does not duplicate fact rows or fail with a primary-key error.
- Built-in reporting views and marts refresh from promoted runs without requiring a separate manual code path.
- Tests verify that a landed built-in dataset appears in published current-dimension views or marts through the supported promotion flow.

**Dependencies:** PLT-05, PLT-06, PLT-11

---

### PLT-19: External registry source inclusion

**Description:** The platform supports external pipeline and function registration from operator-configured custom folders or Git-backed repositories. GitHub is handled through the Git-backed source path. External sources resolve into explicit, immutable revisions that are activated into the same landing, transformation, reporting, application, promotion-handler, and custom-function registries used by built-in code.

**Rationale:** Environment-only module loading is enough for bootstrap, but UI-managed onboarding of household-specific connectors, marts, and helper functions needs a persisted control-plane contract with versioned activation and auditability.

**Phase:** 2–3
**Status:** in-progress (control-plane stores now persist external registry sources, revisions, and activations; path-backed and Git-backed sources can sync a manifest into a validated revision through API or worker commands; Git-backed sync resolves commit SHAs into cache-managed worktrees with optional secret-managed https auth; API/worker startup now loads activated revisions through the existing extension, pipeline, and function registries; configured CSV column mappings can reference registered `function_key` values for mapping-time transforms; and the admin API/web catalog plus worker CLI now expose source lifecycle, revision activation, loaded function discovery, transformation-handler discovery, publication-key discovery, and archive-aware transformation-package/publication-definition configuration flows for operators; broader config binding is still pending)

**Acceptance criteria:**
- Control-plane configuration persists external registry sources with at least: source kind (`path` or `git`), location, auth secret reference, enabled state, and desired ref or path target.
- Syncing a source produces an immutable revision record with resolved commit SHA or path fingerprint, manifest metadata, validation status, and local cache path.
- Activated revisions load through the same extension and pipeline registry contracts used by built-in modules rather than a separate execution path.
- External modules can optionally register custom functions through an explicit function registry with declared keys and contracts.
- Existing config entities reference discovered handler, publication, and function keys rather than raw Python import paths.

**Dependencies:** PLT-18, SEC-05

---

## Traceability

| Requirement | Architecture doc section | Implementation module | Test file |
|---|---|---|---|
| PLT-01 | Input and landing, Storage pattern | `packages/storage/local_landing.py`, `packages/storage/blob.py`, `packages/storage/s3_blob.py` | `tests/test_local_landing_storage.py`, `tests/test_blob_store.py` |
| PLT-02 | Input and landing | `packages/storage/run_metadata.py`, `packages/storage/postgres_run_metadata.py` | `tests/test_run_metadata_repository.py`, `tests/test_postgres_run_metadata_integration.py` |
| PLT-03 | Input and landing, Typical landing checks | `packages/pipelines/csv_validation.py` | `tests/test_csv_landing_validation.py` |
| PLT-04 | Input and landing | `packages/storage/landing_service.py` | `tests/test_landing_service.py` |
| PLT-05 | Transformation | `packages/pipelines/transaction_models.py`, `packages/pipelines/subscription_models.py`, `packages/pipelines/contract_price_models.py`, `packages/pipelines/utility_models.py`, `packages/pipelines/infrastructure_models.py`, `packages/pipelines/transformation_service.py` | `tests/test_transformation_service.py`, `tests/test_subscription_domain.py`, `tests/test_contract_price_domain.py`, `tests/test_utility_domain.py`, `tests/test_infrastructure_domain.py` |
| PLT-06 | Transformation | `packages/pipelines/transaction_models.py`, `packages/pipelines/subscription_models.py`, `packages/pipelines/contract_price_models.py`, `packages/pipelines/utility_models.py`, `packages/pipelines/infrastructure_models.py`, `packages/pipelines/transformation_service.py` | `tests/test_transformation_service.py`, `tests/test_subscription_domain.py`, `tests/test_contract_price_domain.py`, `tests/test_utility_domain.py`, `tests/test_infrastructure_domain.py` |
| PLT-07 | SCD handling | `packages/storage/duckdb_store.py`, `packages/pipelines/transformation_service.py` | `tests/test_scd_dimension.py`, `tests/test_subscription_domain.py`, `tests/test_contract_price_domain.py` |
| PLT-08 | Transformation | `packages/pipelines/normalization.py`, `packages/pipelines/transformation_service.py` | `tests/test_transformation_normalization.py` |
| PLT-09 | Transformation | `packages/pipelines/transformation_service.py`, `packages/pipelines/transformation_domain_registry.py`, `packages/pipelines/transformation_refresh_registry.py`, `packages/pipelines/builtin_transformation_refresh.py`, `packages/pipelines/transformation_transactions.py`, `packages/pipelines/transformation_subscriptions.py`, `packages/pipelines/transformation_contract_prices.py`, `packages/pipelines/transformation_utilities.py`, `packages/pipelines/transaction_models.py`, `packages/pipelines/subscription_models.py`, `packages/pipelines/contract_price_models.py` | `tests/test_architecture_contract.py`, `tests/test_transformation_service.py` |
| PLT-10 | Transformation, Bridge models | `packages/storage/control_plane.py`, `packages/storage/control_plane_snapshot.py`, `packages/storage/ingestion_config.py`, `packages/storage/postgres_ingestion_config.py`, `packages/storage/sqlite_control_plane_schema.py`, `packages/storage/sqlite_execution_control_plane.py`, `packages/storage/postgres_execution_control_plane.py`, `packages/storage/sqlite_provenance_control_plane.py`, `packages/storage/postgres_provenance_control_plane.py`, `packages/storage/sqlite_auth_control_plane.py`, `packages/storage/postgres_auth_control_plane.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py` | `tests/test_control_plane_store_contract.py`, `tests/test_postgres_ingestion_config_integration.py`, `tests/test_control_plane_api_app.py`, `tests/test_s3_postgres_control_plane_integration.py` |
| PLT-11 | Reporting | `packages/storage/duckdb_store.py`, `packages/storage/postgres_reporting.py`, `packages/pipelines/builtin_reporting.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/transformation_transactions.py`, `packages/pipelines/transformation_subscriptions.py`, `packages/pipelines/transformation_contract_prices.py`, `packages/pipelines/transformation_utilities.py`, `packages/pipelines/reporting_service.py`, `apps/api/app.py` | `tests/test_transformation_normalization.py`, `tests/test_subscription_domain.py`, `tests/test_api_app.py`, `tests/test_postgres_reporting_integration.py` |
| PLT-12 | Reporting | `packages/storage/postgres_reporting.py`, `packages/pipelines/builtin_reporting.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/transformation_transactions.py`, `packages/pipelines/transformation_subscriptions.py`, `packages/pipelines/transformation_contract_prices.py`, `packages/pipelines/transformation_utilities.py`, `packages/pipelines/reporting_service.py`, `apps/api/app.py`, `apps/worker/main.py` | `tests/test_monthly_cashflow_reporting.py`, `tests/test_subscription_domain.py`, `tests/test_contract_price_domain.py`, `tests/test_utility_domain.py`, `tests/test_api_app.py`, `tests/test_worker_cli.py`, `tests/test_postgres_reporting_integration.py`, `tests/test_reporting_api_app.py` |
| PLT-13 | Reporting publication forms | — | — |
| PLT-14 | Storage pattern, Compute model | `pyproject.toml`, `packages/storage/duckdb_store.py`, `packages/storage/postgres_run_metadata.py`, `packages/storage/postgres_reporting.py`, `packages/storage/runtime.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py` | `tests/test_project_metadata.py`, `tests/test_transformation_service.py`, `tests/test_storage_runtime.py`, `tests/test_postgres_run_metadata_integration.py`, `tests/test_postgres_reporting_integration.py`, `tests/test_reporting_service.py` |
| PLT-15 | Transformation, Atomicity | `packages/storage/duckdb_store.py`, `packages/pipelines/transformation_service.py` | `tests/test_transformation_service.py` |
| PLT-16 | Input and landing | `packages/storage/run_metadata.py`, `packages/storage/landing_service.py` | `tests/test_landing_service.py`, `tests/test_run_metadata_repository.py` |
| PLT-17 | Audit trail | `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py`, `packages/storage/control_plane.py`, `packages/storage/ingestion_config.py`, `packages/storage/postgres_ingestion_config.py`, `packages/storage/sqlite_provenance_control_plane.py`, `packages/storage/postgres_provenance_control_plane.py`, `packages/storage/sqlite_auth_control_plane.py`, `packages/storage/postgres_auth_control_plane.py`, `packages/pipelines/transaction_models.py` | `tests/test_transformation_service.py`, `tests/test_api_app.py`, `tests/test_control_plane_api_app.py`, `tests/test_control_plane_store_contract.py`, `tests/test_postgres_ingestion_config_integration.py`, `tests/test_s3_postgres_control_plane_integration.py` |
| PLT-18 | Canonical data flow | `packages/pipelines/promotion.py`, `packages/pipelines/promotion_registry.py`, `packages/pipelines/promotion_types.py`, `packages/pipelines/pipeline_catalog.py`, `packages/pipelines/extension_registries.py`, `packages/pipelines/builtin_packages.py`, `packages/pipelines/builtin_reporting.py`, `packages/pipelines/transformation_domain_registry.py`, `packages/pipelines/transformation_refresh_registry.py`, `packages/pipelines/builtin_transformation_refresh.py`, `packages/pipelines/builtin_promotion_handlers.py`, `packages/shared/extensions.py`, `packages/pipelines/account_transaction_service.py`, `packages/pipelines/subscription_service.py`, `packages/pipelines/contract_price_service.py`, `packages/storage/landing_service.py`, `packages/storage/ingestion_config.py`, `apps/api/app.py`, `apps/api/main.py`, `apps/worker/runtime.py`, `apps/worker/main.py` | `tests/test_promotion.py`, `tests/test_extensions.py`, `tests/test_transformation_service.py`, `tests/test_subscription_domain.py`, `tests/test_contract_price_domain.py`, `tests/test_api_app.py`, `tests/test_api_main.py`, `tests/test_worker_cli.py` |
| PLT-19 | Extensibility model, External registry source model | `packages/storage/control_plane.py`, `packages/storage/external_registry_catalog.py`, `packages/storage/sqlite_external_registry_catalog.py`, `packages/storage/postgres_external_registry_catalog.py`, `packages/storage/control_plane_snapshot.py`, `packages/shared/external_registry.py`, `packages/shared/function_registry.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/config_preflight.py`, `packages/pipelines/promotion_registry.py`, `apps/api/app.py`, `apps/api/main.py`, `apps/api/routes/config_routes.py`, `apps/worker/runtime.py`, `apps/worker/command_handlers.py`, `apps/web/frontend/app/control/catalog/page.js`, `apps/web/frontend/app/control/catalog/transformation-packages/route.js`, `apps/web/frontend/app/control/catalog/publication-definitions/route.js`, `apps/web/frontend/components/external-registry-panel.js`, `apps/web/frontend/components/function-catalog-panel.js`, `apps/web/frontend/components/transformation-catalog-panel.js`, `apps/web/frontend/lib/backend.ts`, `apps/web/frontend/lib/config-spec.js` | `tests/test_external_registry_support.py`, `tests/test_configured_csv_ingestion.py`, `tests/test_config_preflight.py`, `tests/test_api_app.py`, `tests/test_api_main.py`, `tests/test_worker_cli.py`, `tests/test_control_plane_store_contract.py`, `tests/test_web_auth.py` |
