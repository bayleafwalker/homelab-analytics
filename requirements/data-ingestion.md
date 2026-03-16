# Data Ingestion Requirements

## Overview

The platform must accept data from heterogeneous sources — manual file uploads, watched folders, authenticated API pulls, batch extracts, and internal platform endpoints — without requiring code changes for each new source. Ingestion is configuration-driven: every source is onboarded through a declared source system, dataset contract, and column mapping.

---

## Requirements

### ING-01: Manual file upload

**Description:** Accept CSV, XLSX, and JSON file uploads through the web UI and API. Each upload must be associated with a source system and dataset definition.

**Rationale:** Manual import is the first and most common onboarding path for household data exports.

**Phase:** 1
**Status:** in-progress (CSV multipart upload and server-side path ingestion now work through FastAPI; web upload UI and non-CSV upload formats are not yet built)

**Acceptance criteria:**
- API endpoint accepts multipart file upload and returns a run ID.
- Web UI file upload form submits to the same endpoint.
- Uploaded file is persisted to landing storage unchanged.
- Validation runs against the configured dataset contract before promotion.

**Dependencies:** ING-07, ING-08
**Notes:** Current implementation preserves uploaded CSV bytes unchanged in landing and validates them against the selected dataset contract. Config-driven sources also store a canonical projection artifact so promotion does not need to reinterpret the raw source layout. XLSX and JSON upload handling are still pending.

---

### ING-02: Watched folder ingestion

**Description:** Monitor one or more configured directories for new files and ingest them automatically. Supported folder backends: local filesystem, NFS mounts, and directories synced from cloud providers via rclone, WebDAV, or mount-based sync.

**Rationale:** Folder-based ingestion lets users drop exports into a shared folder rather than interacting with the UI every time.

**Phase:** 1–2
**Status:** in-progress (config-driven filesystem ingestion definitions can process a watched folder; the legacy account-transactions inbox commands now bootstrap into the same source-asset and ingestion-definition flow for compatibility; explicit `execution_schedule` and `schedule_dispatch` control-plane entities now exist; a general schedule-dispatch worker can now enqueue due work, claim dispatches, renew active leases, recover expired stale dispatches, and execute them continuously with heartbeat visibility; richer multi-source orchestration is still pending)

**Acceptance criteria:**
- Configuration defines watched directories, expected dataset, and polling interval.
- New files are ingested, validated, and moved to processed or failed directories.
- Multiple watched directories can be configured independently.
- Synced cloud folders (OneDrive, Nextcloud, Google Drive) are consumed as regular filesystem paths after external sync.

**Dependencies:** ING-07
**Notes:** The platform does not need to implement proprietary cloud storage APIs. Prefer rclone CronJob sidecars or mount-based sync.

---

### ING-03: Direct API ingestion

**Description:** Pull data from authenticated REST APIs on a configured schedule or on demand. Target APIs include utility providers (Elisa Kotiakku, Helen), Home Assistant REST API, Prometheus query API, and generic authenticated endpoints.

**Rationale:** Automated API pulls eliminate manual export steps and enable near-real-time data freshness.

**Phase:** 2–3
**Status:** in-progress (config-driven HTTP CSV pulls now preserve raw response bytes in landing, validate the configured CSV projection, and resolve request headers from stored secret references at runtime; provider-specific auth modes and response normalization remain)

**Acceptance criteria:**
- API connector configuration defines URL, authentication method (bearer token, API key, basic auth), request parameters, and response mapping.
- Connector executes a pull and writes the response to landing storage as an immutable payload.
- Configuration persists secret references rather than raw credential values.
- Landing validation runs on the result before promotion.
- Tests use a mock HTTP server to verify connector behavior.

**Dependencies:** ING-07, ING-08
**Notes:** Current implementation supports configured HTTP requests with secret-referenced headers, timeout, and CSV landing. Raw response bytes are preserved unchanged in landing, while a mapped canonical CSV projection can be generated for validation and downstream promotion. Elisa Kotiakku and Helen API availability still needs to be confirmed. Default to CSV import if APIs are undocumented.

---

### ING-04: Batch extract ingestion

**Description:** Ingest files fetched by authenticated HTTP requests — scheduled curl-style downloads with headers, bearer tokens, or session cookies.

**Rationale:** Some data sources only provide download links or authenticated export endpoints, not programmatic APIs.

**Phase:** 2–3
**Status:** in-progress (config-driven HTTP CSV downloads now preserve raw response bytes in landing, validate the configured CSV projection, and resolve request headers from stored secret references at runtime; richer extract lifecycle is still pending)

**Acceptance criteria:**
- Configuration defines download URL, authentication headers, output format, and schedule.
- Worker executes the download and writes the result to landing storage.
- Configuration persists secret references rather than raw credential values.
- Output is treated identically to a file drop after download.

**Dependencies:** ING-07
**Notes:** Current implementation supports HTTP GET downloads with secret-referenced headers and timeout. Raw extract bytes are preserved unchanged in landing, while a mapped canonical CSV projection can be generated for validation and downstream promotion. Batch extracts and direct API connectors still share the same generic HTTP transport path for CSV responses.

---

### ING-05: Financial data ingestion

**Description:** Support ingestion of financial dataset types: account transactions, card transactions, daily balance snapshots, loan details, repayment schedules, and planned repayment records. Each type has its own dataset contract and canonical mapping.

**Rationale:** Financial data is the primary household analytics use case and requires precise type handling (decimals, dates, currencies).

**Phase:** 1–3
**Status:** in-progress (account transactions CSV implemented)

**Acceptance criteria:**
- Each financial dataset type has a registered dataset contract with typed column definitions.
- Account transactions: landing contract, canonical mapping, and transformation are complete (Phase 1).
- Card transactions and daily balances: contracts and mappings exist and are testable (Phase 2).
- Loan details and repayments: contracts and mappings exist (Phase 3).
- All financial types flow through landing → transformation → reporting.

**Dependencies:** ING-07, ING-08, PLT-01 through PLT-06

---

### ING-06: Internal platform ingestion

**Description:** Ingest data from internal homelab sources: Prometheus metric queries via PromQL HTTP API, Home Assistant entity state exports or API reads, and Kubernetes resource usage metrics.

**Rationale:** Homelab infrastructure data enables cluster cost modeling, energy monitoring integration, and automation-driven analytics.

**Phase:** 3
**Status:** not-started

**Acceptance criteria:**
- Prometheus connector executes a PromQL query and writes the result matrix to landing as JSON or CSV.
- Home Assistant connector reads entity states via REST API and writes to landing.
- Landing contracts validate the expected schema for each internal source.
- Tests use mock HTTP responses for both connectors.

**Dependencies:** ING-03, ING-07

---

### ING-07: Ingestion configuration model

**Description:** Source onboarding must be configuration-driven. The platform maintains these configuration entities:

| Entity | Purpose |
|---|---|
| `source_system` | External or internal data provider identity |
| `source_asset` | A specific dataset from a source system |
| `ingestion_definition` | Transport and fetch rules for a source asset |
| `dataset_contract` | Schema and DQ expectations for a dataset |
| `column_mapping` | Source-to-canonical column mapping |
| `transformation_package` | Which transformation logic applies |
| `publication_definition` | Which reporting outputs are derived |

**Rationale:** Hard-coding per-source logic prevents scaling to many sources. Configuration-driven onboarding lets the platform grow without code changes for each new provider.

**Phase:** 1
**Status:** implemented (SQLite-backed `source_system`, `source_asset`, `ingestion_definition`, `dataset_contract`, `column_mapping`, `transformation_package`, and `publication_definition` entities exist; filesystem and HTTP ingestion definitions resolve at runtime; source assets now bind transformation packages and publication selection for promotion)

**Acceptance criteria:**
- Configuration entities are defined as data models and persisted (initially file-based YAML/JSON, later database-backed).
- Adding a new CSV source requires only configuration, not new Python modules.
- Worker resolves ingestion definitions at runtime to determine how to handle a file or API pull.
- Tests verify that a new source can be onboarded by adding configuration alone.

**Dependencies:** none

---

### ING-08: Custom source-to-canonical mapping

**Description:** Users define and version column mappings from source file layouts to canonical landing and transformation models. Initial version is configuration-file-driven. Dashboard-based mapping editing is a later deliverable.

**Rationale:** Every source has its own column naming. Mappings decouple source layout from canonical models and enable non-developer source onboarding.

**Phase:** 1 (file-based), 4 (UI-based)
**Status:** in-progress (persisted column mappings now drive configured contract validation while preserving the landed raw payload unchanged; a canonical projection artifact is also stored so downstream promotion can use the mapped shape without mutating bronze; versioned UI management is still pending)

**Acceptance criteria:**
- A YAML or JSON mapping file can specify source column → canonical column, type coercion, and default values.
- Transformation applies the mapping during normalization.
- Mappings are versioned — changing a mapping creates a new version without breaking existing runs.
- Tests verify that different mappings for the same source type produce correct canonical output.

**Dependencies:** ING-07

---

### ING-09: Folder sync sources

**Description:** Support ingestion from directories synced from OneDrive, Nextcloud, and Google Drive. The platform treats synced directories as regular watched folders after external sync tools land the files.

**Rationale:** Cloud storage is a common drop point for bank exports, utility reports, and other household documents.

**Phase:** 3–4
**Status:** not-started

**Acceptance criteria:**
- Documentation describes how to configure rclone CronJob or WebDAV mount per provider.
- The platform's watched-folder ingestion handles files in synced directories identically to local drops.
- Helm chart values support mounting additional PVCs for synced directories.

**Dependencies:** ING-02

---

### ING-10: Subscription and recurring-services ingestion

**Description:** Support ingestion of subscription and recurring-service records from CSV exports. Each record captures the service name, provider, billing cycle, amount, currency, and optional end date. Records feed `dim_contract`, `fact_subscription_charge`, and `mart_subscription_summary`.

**Rationale:** Subscriptions and recurring services are a major household fixed-cost category. Explicit ingestion (distinct from transaction detection) allows proactive tracking before transactions appear.

**Phase:** 2
**Status:** implemented (CSV landing contract, canonical loader, `SubscriptionService`, `promote_subscription_run`, API endpoint, worker command, and mart refresh all implemented)

**Acceptance criteria:**
- A dataset contract defines subscription column types and required fields.
- Ingestion rejects CSV rows with invalid amounts or unparseable dates.
- Canonical loader normalises billing cycles to a monthly equivalent.
- Promotion is idempotent — re-promoting the same run does not duplicate rows.
- Tests verify landing validation, canonical loading, mart population, and status/currency filtering.

**Dependencies:** PLT-05, PLT-06, PLT-01

---

### ING-11: Contract pricing and tariff ingestion

**Description:** Support ingestion of temporal contract pricing records from CSV exports and configured pulls. Records describe a contract, price component, billing cadence, unit price, optional quantity unit, and validity window. They feed `dim_contract`, `fact_contract_price`, `mart_contract_price_current`, and `mart_electricity_price_current`.

**Rationale:** Many household and homelab costs are known first as contract terms or tariffs, not as realised bills. Temporal pricing data is required to model electricity tariffs, broadband contracts, insurance, and other recurring priced services before actual spending data arrives.

**Phase:** 2
**Status:** implemented (CSV landing contract, canonical loader, `ContractPriceService`, generic contract dimension extraction, `promote_contract_price_run`, API endpoints, worker commands, and current-price marts are implemented)

**Acceptance criteria:**
- A dataset contract defines contract-pricing column types and required fields.
- Ingestion rejects invalid decimal values or invalid validity dates.
- Canonical loading preserves temporal validity windows and quantity units.
- Promotion publishes current contract prices and current electricity price rows without duplicating facts on re-run.
- Tests verify landing validation, canonical loading, mart population, and API/worker reporting access.

**Dependencies:** PLT-05, PLT-06, PLT-01

---

## Traceability

| Requirement | Architecture doc section | Implementation module | Test file |
|---|---|---|---|
| ING-01 | Source classes, Input and landing | `packages/pipelines/account_transaction_service.py`, `apps/api/app.py` | `tests/test_account_transaction_service.py`, `tests/test_api_app.py` |
| ING-02 | Source classes | `packages/pipelines/account_transaction_inbox.py`, `packages/pipelines/configured_ingestion_definition.py` | `tests/test_account_transaction_inbox.py`, `tests/test_configured_ingestion_definition.py` |
| ING-03 | Source classes, Direct provider API | `packages/storage/ingestion_catalog.py`, `packages/storage/ingestion_config.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/configured_ingestion_definition.py`, `apps/api/app.py` | `tests/test_ingestion_config_repository.py`, `tests/test_configured_ingestion_definition.py`, `tests/test_api_app.py` |
| ING-04 | Source classes, Batch extract | `packages/storage/ingestion_catalog.py`, `packages/storage/ingestion_config.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/configured_ingestion_definition.py` | `tests/test_ingestion_config_repository.py`, `tests/test_configured_ingestion_definition.py` |
| ING-05 | Source classes | `packages/pipelines/csv_validation.py`, `packages/pipelines/account_transactions.py` | `tests/test_csv_landing_validation.py`, `tests/test_account_transaction_transform.py` |
| ING-06 | Source classes, Internal platform | — | — |
| ING-07 | Mapping and ingestion config model | `packages/storage/ingestion_catalog.py`, `packages/storage/ingestion_config.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/configured_ingestion_definition.py`, `packages/pipelines/promotion.py`, `apps/api/app.py`, `apps/worker/main.py` | `tests/test_ingestion_config_repository.py`, `tests/test_configured_csv_ingestion.py`, `tests/test_configured_ingestion_definition.py`, `tests/test_api_app.py`, `tests/test_worker_cli.py` |
| ING-08 | Mapping and ingestion config model | `packages/storage/ingestion_catalog.py`, `packages/storage/ingestion_config.py`, `packages/pipelines/configured_csv_ingestion.py`, `packages/pipelines/promotion.py` | `tests/test_configured_csv_ingestion.py`, `tests/test_api_app.py`, `tests/test_promotion.py` |
| ING-09 | Source classes, Synced folder | — | — |
| ING-10 | Source classes | `packages/pipelines/subscription_service.py`, `packages/pipelines/subscriptions.py`, `packages/pipelines/subscription_models.py`, `packages/pipelines/promotion.py`, `apps/api/app.py`, `apps/worker/main.py` | `tests/test_subscription_domain.py`, `tests/test_api_app.py`, `tests/test_worker_cli.py` |
| ING-11 | Source classes | `packages/pipelines/contract_price_service.py`, `packages/pipelines/contract_prices.py`, `packages/pipelines/contract_price_models.py`, `packages/pipelines/promotion.py`, `apps/api/app.py`, `apps/worker/main.py` | `tests/test_contract_price_domain.py`, `tests/test_api_app.py`, `tests/test_worker_cli.py` |
