# Compute And Orchestration Options

## Decision summary

Recommended initial stack:

- compute: Python + Polars + DuckDB + PyArrow
- execution unit: containerized worker process or Kubernetes Job
- scheduling: application scheduler for user-managed jobs plus Kubernetes CronJobs for platform-managed recurring jobs
- scale-out trigger: only introduce queueing or distributed compute when measured workload requires it

Deferred but supported upgrade paths:

- Dagster for richer orchestration and lineage
- Argo Workflows for Kubernetes-native multi-step execution
- Spark on Kubernetes for genuinely large or distributed workloads

## What the project needs right now

The early platform needs:

- strong CSV/XLSX/API handling
- schema drift tolerance
- easy local development
- low cluster overhead
- reproducible batch runs
- credible open-source packaging for later public release

It does not need:

- distributed streaming
- multi-terabyte joins
- always-on scheduler infrastructure on day one

## Compute options

### Python + Polars + DuckDB

Pros:

- excellent fit for heterogeneous file ingestion
- simple packaging in one worker image
- strong local and Kubernetes batch ergonomics
- easy use of Parquet and object storage
- good path to reusable transformation code

Cons:

- bounded by node-scale compute unless the work is partitioned
- custom orchestration logic is still required

Assessment:

- best default for this repository

### Spark on Kubernetes

Pros:

- credible open-source distributed engine
- strong ecosystem for large-scale transformation
- clear path for partitioned workloads and heavy joins

Cons:

- materially more operational overhead in a homelab
- poor fit for the likely early workload size
- more friction for local iteration and connector debugging

Assessment:

- keep as an optional backend when data volume or concurrency proves the need

### dbt Core on DuckDB/Postgres

Pros:

- good SQL-based transformation ergonomics
- test and documentation patterns are well-known
- useful once canonical models settle

Cons:

- weaker fit for messy file ingestion and Python-heavy normalization
- introduces another modeling tool before the raw source contracts are stable

Assessment:

- useful later for reporting marts, not the initial control plane

### Apache Flink

Pros:

- strong streaming engine

Cons:

- wrong complexity profile for the current use case

Assessment:

- not recommended

## Orchestration options

### In-application scheduler plus Kubernetes Jobs and CronJobs

Pros:

- simplest path to an integrated product
- no extra control plane required
- easy to expose run history in the same API and UI

Cons:

- lineage, retries, and dependency management need to be built carefully

Assessment:

- recommended starting point

### Dagster Open Source

Pros:

- strong asset model, lineage, and developer ergonomics
- credible open-source option
- good fit if the project becomes a broader data platform

Cons:

- introduces a second UI and orchestration model
- heavier operational footprint than the initial platform needs

Assessment:

- best orchestration upgrade if in-app scheduling becomes too limited

### Argo Workflows

Pros:

- Kubernetes-native
- strong multi-step job orchestration
- works well with GitOps environments

Cons:

- less natural as the primary end-user product UI
- more infrastructure-centric than domain-centric

Assessment:

- good cluster-side execution option if workflows become more complex

### Apache Airflow

Pros:

- mature and widely known

Cons:

- heavy for a homelab-first product
- comparatively awkward for app-integrated user experiences

Assessment:

- not recommended initially

## Workload management options

Recommended progression:

1. Run worker pods directly for manual jobs and low-volume schedules.
2. Use Kubernetes Jobs or CronJobs for isolated recurring runs.
3. Add KEDA only if queue-backed autoscaling becomes necessary.
4. Introduce Dagster or Argo only when the dependency graph and operational burden justify them.
5. Introduce Spark Operator only when datasets or SLAs exceed single-node processing.

## Security and secrets

Recommended cluster posture:

- use External Secrets Operator or SOPS-managed Secrets for provider credentials
- mount credentials into worker pods only when required
- separate read-only reporting credentials from ingestion credentials
- use OIDC for the main UI once external access is needed
- keep a local admin username/password fallback for bootstrap or break-glass access

## Release and portability implications

This decision supports the planned release targets:

- one Docker image family for API, worker, and web
- one Helm chart for Kubernetes deployment
- optional Compose examples for non-cluster development
- clear OSS story for GitHub or Forgejo release automation

## Trigger points to revisit the decision

Re-open this choice if any of the following become true:

- a single run no longer fits comfortably on one node
- multiple pipelines must run concurrently with strict isolation
- pipeline dependency graphs become too complex for the in-app scheduler
- end users need rich asset lineage beyond run history
- streaming ingestion becomes a real requirement
