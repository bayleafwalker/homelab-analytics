# Data Platform Architecture

## Goals

The platform needs one architecture that supports:

- manual ingestion first, without blocking later automation
- reusable transformation logic instead of dashboard-specific wrangling
- household and homelab datasets under one model
- publishable outputs through both API and dashboard surfaces
- built-in product logic with explicit extension points for external code

## Source classes

The source registry should classify each source by `source_type`, `transport`, `schedule_mode`, and `mapping_strategy`.

Initial source classes:

- file drop sources: CSV, XLSX, ZIP, JSON
- synced folder sources: NFS, SMB, WebDAV, OneDrive, Nextcloud, Google Drive
- direct provider API sources: utility APIs, banking exports, card exports, authenticated REST pulls
- batch extract sources: curl with static auth, curl with token refresh, browser-exported files
- internal platform sources: Prometheus queries, Home Assistant exports, Home Assistant API payloads

## Canonical data flow

Use three layers with explicit contracts between them.

### 1. Input and landing

The input surface accepts uploaded files, watched folders, synced folders, or scheduled fetch jobs. Every ingestion run creates a landing record before any downstream transformation is attempted.

Landing responsibilities:

- persist the original payload unchanged
- assign a source, dataset, and run identifier
- capture file hash, schema fingerprint, and source metadata
- execute data quality and contract checks before promotion
- write row-level and file-level validation outcomes

Landing storage is the bronze layer:

- immutable object storage for raw payloads and snapshots
- landing metadata in Postgres
- optional temporary local work files on PVC

Typical landing checks:

- required columns present
- column type compatibility
- duplicate file detection
- row count thresholds
- currency/date parsing sanity
- allowed enumerations
- source freshness checks for scheduled pulls

If a landing contract fails, the payload remains queryable for troubleshooting but is not promoted.

Landing extensibility:

- keep core ingestion contracts and baseline connectors in the application itself
- allow external connectors, source adapters, and dataset contracts to be loaded from external repositories or custom paths
- treat landing extensions as registration-based plugins rather than direct edits to application code

### 2. Transformation

The transformation layer turns source-shaped data into reusable domain models. This is the silver layer and should be dashboard-agnostic.

Transformation responsibilities:

- normalize naming, types, and time semantics
- standardize currencies, units, and identifiers
- map source-specific columns to canonical business entities
- build reusable fact and dimension models
- persist slowly changing dimensions as SCD tables
- calculate reconciliation and lineage metadata

Recommended transformation outputs:

- canonical dimensions such as `dim_account`, `dim_counterparty`, `dim_contract`, `dim_meter`, `dim_loan`, `dim_asset`, `dim_household_member`
- canonical facts such as `fact_transaction`, `fact_subscription_charge`, `fact_contract_price`, `fact_balance_snapshot`, `fact_utility_usage`, `fact_bill`, `fact_loan_repayment`, `fact_cluster_metric`
- bridge or helper models for tags, categories, budgets, and source mappings

SCD handling:

- dimensions should be stored as Type 2 SCD by default when attributes can change historically
- use `valid_from`, `valid_to`, `is_current`, and source lineage columns
- keep natural keys and surrogate keys separate

Transformation extensibility:

- keep key canonical transformations inside the application as the reference implementation
- allow external transformation packages to register additional canonical models, enrichments, and mapping logic
- require every external transformation to publish its canonical target, version, and lineage metadata

### 3. Reporting

The reporting layer is the gold layer and should be model-aligned to consumers rather than source systems.

Reporting responsibilities:

- publish current-time dimension views from SCD dimensions
- build dashboard-oriented marts and aggregates
- materialize stable metrics tables for API and UI access
- expose curated data products with predictable schemas

Typical reporting outputs:

- current household budget status
- monthly electricity cost and usage summaries
- current electricity tariff and contract price views
- loan repayment plan vs actual
- recurring cost baseline
- homelab service cost and profitability assessment
- anomaly and trend views for spending or energy

Reporting publication forms:

- Postgres schemas or materialized views for the application
- Parquet extracts for reproducible snapshots
- API endpoints for downstream tools
- dashboard datasets for interactive charts

Reporting extensibility:

- keep primary marts and shared metrics in the application repository
- allow external marts, publication handlers, and report-specific enrichments to be loaded from external repositories or custom paths
- publish built-in and external reporting assets through the same registry and contract model

## Extensibility model

The application should remain useful on its own, so core transformations and reports belong in-repo. External code is an additive mechanism, not a replacement for the core product.

Recommended loading pattern:

- load built-in landing, transformation, reporting, and application entries first
- extend the import path with operator-configured custom paths or checked-out external repositories
- import explicitly configured extension modules
- require each extension module to register itself into a shared layer registry
- allow executable extensions to expose handlers that can be invoked by worker jobs or application APIs

Layer expectations:

- landing extensions can add source connectors, contract presets, and ingestion orchestration helpers
- transformation extensions can add canonical transforms, enrichment steps, and custom dimension or fact builders
- reporting extensions can add marts, publication jobs, API resources, and dashboard-facing aggregates
- application extensions can add online UI, API, or operational integration surfaces that consume the same reporting contracts

Executable reporting extensions must declare whether they are `published` or `warehouse` backed. Application-facing execution should not infer that contract from handler internals or silently fall back to landed bytes.

If a reporting extension is `published`, it may also declare one or more named publication relations with schema and source SQL so those relations can be copied into the Postgres publication store through the same publication-key contract used by built-in marts. Source-asset publication definitions may reference those relation names directly, and config/admin publication-definition creation should reject unknown relation names before they are persisted.

This keeps the platform auditable while still allowing household-specific or community-contributed logic to live outside the main repository.

## Mapping and ingestion configuration model

Source onboarding should not be hard-coded per provider. The platform should carry configuration for:

- source connection definition
- landing dataset definition
- file or API selection rules
- mapping from raw columns to canonical columns
- transformation package version
- reporting publication targets

Configuration entities:

- `source_system`
- `source_asset`
- `ingestion_definition`
- `dataset_contract`
- `column_mapping`
- `transformation_package`
- `publication_definition`

Binding rules:

- a `source_asset` binds one landed dataset to one canonical mapping and one transformation package
- an `ingestion_definition` describes only how bytes arrive; it must not hard-code downstream transformation behavior
- `publication_definition` declares which gold outputs a transformation package publishes
- worker and API promotion should dispatch from source-asset configuration, not inferred file headers or route-specific heuristics

For folder-like external systems, prefer sync-to-folder first:

- use NFS directly where available
- use WebDAV for Nextcloud where appropriate
- use `rclone` jobs or a sidecar for OneDrive and Google Drive
- treat all synced files as normal folder ingestion once landed

This avoids implementing multiple proprietary file APIs in the first release.

## Storage pattern

Use storage according to responsibility rather than trying to collapse everything into one engine.

| Layer | Primary store | Purpose |
|---|---|---|
| Input queue / sync area | PVC or mounted share | Short-lived watched folders and synced data |
| Landing / bronze | S3-compatible object storage | Immutable payload archive |
| Transformation / silver | DuckDB files plus Parquet on PVC or object storage | Batch normalization and reusable intermediate models |
| Reporting / gold | Postgres | Published marts, API datasets, app metadata |

Metadata that spans all layers belongs in Postgres:

- run history
- source registry
- contract results
- lineage
- publication metadata

## Compute model

The default engine should be Python workers using Polars and DuckDB:

- Polars for parsing and vectorized transformation
- DuckDB for local SQL, Parquet operations, and analytic joins
- PyArrow for interchange between storage and compute

Spark remains an optional later execution backend for larger workloads, but not the initial default.

## API and dashboard publication

The application boundary should expose the same curated reporting models through:

- dashboard APIs used by the web UI
- service APIs for Home Assistant or other automations
- admin APIs for source, mapping, and run management

The dashboard UI should eventually support:

- ingestion run monitoring
- manual file upload and source assignment
- folder source configuration
- mapping review and versioning
- dataset exploration
- reporting and alert views

## Security boundaries

Separate runtime concerns by trust level:

- raw source secrets are referenced by ingestion definitions only
- landing payloads are immutable and append-only
- transformation code can read landing and write silver
- reporting services can read published gold models but should not mutate landing

Secrets should come from cluster-native secret management, not checked-in values files.
Application configuration should persist only secret references. Resolved secret values belong to runtime secret providers such as Kubernetes Secrets, External Secrets Operator, SOPS-managed env injection, or equivalent operator-controlled mechanisms.

## Initial design constraints

The first implementation should bias toward simple, auditable batch pipelines:

- file and API batch ingestion first
- no streaming requirement
- no Spark cluster requirement
- no custom DSL before the core source and mapping model works

That path keeps the architecture open for future scale without paying the full complexity cost on day one.
