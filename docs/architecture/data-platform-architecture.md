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
- landing and control-plane metadata in Postgres `control` schema, with SQLite retained only as a local bootstrap fallback
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
- resolve package promotion handlers and publication refresh sets through shared registries rather than hard-wiring package branches into the central orchestrators
- expose a shared canonical-promotion processor contract so built-in and external packages can reuse the same idempotent run-promotion lifecycle
- expose transformation domain keys through a shared registry so promotion handlers can target reusable canonical loaders without depending on individual service methods
- expose a shared registration helper so external packages can register a transformation-domain loader and matching canonical promotion handler together
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

When published reporting is configured, API and web workloads should read from those published relations rather than querying the DuckDB warehouse directly. Warehouse reads remain a worker/local-development contract.

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
- allow extension modules to optionally define `register_pipeline_registries(...)` so configured transformation packages can add package catalog declarations, promotion handlers, transformation domain handlers, and publication refresh handlers through the same module-loading path
- allow extension modules to optionally define `register_functions(function_registry)` so custom callables are loaded through the same module-loading path instead of ad hoc imports
- allow executable extensions to expose handlers that can be invoked by worker jobs or application APIs

Layer expectations:

- landing extensions can add source connectors, contract presets, and ingestion orchestration helpers
- transformation extensions can add canonical transforms, enrichment steps, and custom dimension or fact builders
- reporting extensions can add marts, publication jobs, API resources, and dashboard-facing aggregates
- application extensions can add online UI, API, or operational integration surfaces that consume the same reporting contracts

Registry source expectations:

- external code sources should be persisted as control-plane configuration rather than worker-only environment variables when operators need UI-managed inclusion
- support two source kinds through one acquisition model: mounted custom folders and Git repositories, with GitHub handled as the first Git provider instead of a separate bespoke plugin path
- every external source should expose a small manifest that declares import roots, extension modules, optional function modules, and compatibility metadata before activation
- workers should sync or validate a source into a local cache, resolve an immutable revision, and only then activate it for registry loading
- runtime code loading should continue to happen from local filesystem paths; GitHub inclusion is an acquisition and version-resolution concern, not a second execution mechanism

Custom function expectations:

- custom functions are additive helpers registered by key, not arbitrary import strings embedded in user configuration
- each function should declare its owning layer, function kind, input contract, output contract, and whether it is deterministic or side-effecting
- the first supported binding point is configured CSV column mapping, where a rule may reference a `function_key` to transform the resolved source/default value before canonical validation and landing manifests are written
- config entities such as dataset checks, mapping transforms, transformation packages, and reporting publications should reference registered function keys instead of raw Python paths
- application-facing reporting functions must still respect published-versus-warehouse access contracts and must not create landing-to-dashboard shortcuts

Executable reporting extensions must declare whether they are `published` or `warehouse` backed. Application-facing execution should not infer that contract from handler internals or silently fall back to landed bytes.

If a reporting extension is `published`, it may also declare one or more named publication relations with schema and source SQL so those relations can be copied into the Postgres publication store through the same publication-key contract used by built-in marts. Source-asset publication definitions may reference those relation names directly, and config/admin publication-definition creation should reject unknown relation names before they are persisted.

This keeps the platform auditable while still allowing household-specific or community-contributed logic to live outside the main repository.

## External registry source model

UI-managed external inclusion should use explicit control-plane records rather than only startup environment variables.

Recommended entities:

- `extension_registry_source`: operator-declared source of external code with `source_kind` (`path` or `git`), location, auth secret reference, default ref, and enabled state
- `extension_registry_revision`: immutable synced result with resolved commit SHA or path fingerprint, manifest digest, sync status, and local cache path
- `extension_registry_activation`: the active revision set that API and worker processes load at startup or through an explicit reload action
- discovered exports from an active revision should be queryable in the control plane so admins can bind handler keys, publication keys, and function keys without guessing module internals

Loading lifecycle:

- admin creates or updates an external source definition
- worker or control-plane sync validates the manifest and resolves a local cached revision
- validation rejects missing modules, duplicate keys, incompatible platform versions, or unsupported function contracts before activation
- runtime processes load built-ins plus the active cached revisions through the same extension and pipeline registries already used for in-repo and env-configured modules
- initial implementation should prefer explicit reload or restart after activation rather than implicit hot-reload during request handling

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
- `execution_schedule`
- `schedule_dispatch`
- `dataset_contract`
- `column_mapping`
- `transformation_package`
- `publication_definition`
- `source_lineage`
- `publication_audit`

Binding rules:

- a `source_asset` binds one landed dataset to one canonical mapping and one transformation package
- an `ingestion_definition` describes only how bytes arrive; it must not hard-code downstream transformation behavior
- an `execution_schedule` describes only when a target is enqueued; it must not embed transformation or reporting logic
- schedule execution records belong in `schedule_dispatch`, and the scheduler should enqueue work rather than run transformations inline
- workers should claim `schedule_dispatch` rows before execution, renew those claims while work is still active, recover expired claims by failing and requeueing stale dispatches, update dispatches through `running` and terminal states, and publish lightweight heartbeat state for control-plane visibility
- `publication_definition` declares which gold outputs a transformation package publishes
- worker and API promotion should dispatch from source-asset configuration, not inferred file headers or route-specific heuristics
- control-plane transformation-package creation should validate `handler_key` values against the loaded promotion-handler registry so invalid runtime wiring is rejected before it is persisted
- control-plane publication-definition creation and `verify-config` should validate built-in publication keys against the selected package handler, while still allowing extension-declared publication relations
- API and worker startup may sync extension-declared transformation packages and publication definitions into the control plane so source assets can bind to registered external packages without manual catalog bootstrapping

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

Use one DSN with separate schemas by default:

- `control` for source registry, contracts, mappings, source assets, ingestion definitions, schedules, dispatch records, lineage, publication audit, and run metadata
- `reporting` for published marts and current-dimension relations

Runtime deployments should still support per-purpose DSN overrides so workload credentials can differ by privilege:

- API can receive control-plane and reporting DSNs aligned to its control/admin and read paths
- worker can receive write-capable control-plane, metadata, and reporting DSNs
- web remains API-backed and should avoid direct database credentials entirely

## Application and control-plane boundary

- API and web workloads should consume published reporting relations when Postgres reporting is enabled
- worker jobs and local bootstrap flows may continue to read the DuckDB warehouse directly
- bootstrap auth is local username/password with HTTP-only signed session cookies only when explicitly enabled for break-glass use; OIDC is the production interactive path; scoped service tokens are available for automation clients; `/health`, `/ready`, and `/metrics` stay public, while admin/control routes require an `admin` role
- `HOMELAB_ANALYTICS_ENABLE_UNSAFE_ADMIN` is a temporary local-only escape hatch and should stay disabled in shared deployment manifests
- the web workload should stay API-backed: the current Next.js shell consumes API routes only, and any future product/admin UI should continue to avoid server-side warehouse or control-plane reads in the web runtime

## Compute model

The default engine should be Python workers using Polars and DuckDB:

- Polars for parsing and vectorized transformation
- DuckDB for local SQL, Parquet operations, and analytic joins
- PyArrow for interchange between storage and compute

Operational defaults:

- structured JSON logs from API, web, and worker workloads
- Prometheus-compatible `/metrics` surfaces for ingestion counters, failures, duration, queue depth, worker heartbeat/stale-dispatch state, auth-failure signals, and service-token lifecycle state
- ingress or reverse-proxy routing should terminate at the web workload, with the OIDC callback served at `/auth/callback`

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
