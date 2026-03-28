# Knowledge Base — homelab-analytics
Generated: 2026-03-28T19:01:03Z

## Decisions

### Keep utility provider pulls on configured HTTP CSV landing
Source: track: stage-1, sprint: 4
Tags: utilities, ingestion, freshness

Utility-provider pulls should reuse the configured HTTP CSV landing path instead of introducing a provider-specific transport. Freshness policy belongs in source-freshness configuration so transport, authentication, and reminder logic stay decoupled.

---

### Model infrastructure metrics with SCD dimensions plus raw facts
Source: track: stage-1, sprint: 4
Tags: infrastructure, scd, duckdb

Infrastructure metrics should model nodes and devices as SCD-capable dimensions while retaining separate raw fact tables for cluster metrics and power consumption. Historical metadata changes belong in dimensions; measured evidence belongs in facts for later marts and reporting.

---

### Standardize release governance on main-only branches and versioned releases
Source: sprint: 4
Tags: release-policy, github, git, docs

Repository release governance uses main-only long-lived branch flow, annotated semantic-version tags, and GitHub Releases only for version tags. Sprint checkpoint tags remain internal markers and should not create public GitHub Releases.

---

### Publish current dimensions through reporting-layer registries
Source: track: stage-1, sprint: 4
Tags: home-automation, reporting, current-dimension, publication

App-facing current-dimension access should go through reporting-layer registries when a published current view exists. This preserves the landing/transformation/reporting split and avoids adding new landing-to-dashboard shortcuts for current-dimension reads.

---

### Treat balance snapshots as transformation facts
Source: track: stage-1, sprint: 4
Tags: fact_balance_snapshot, stage-1, transformation

Balance snapshots belong in the transformation layer as DuckDB-backed facts derived from balance evidence and repayment history. They should not remain vague carryover scope or be modeled as reporting-only shortcuts.

---

## Patterns

### Use raw landing for JSON-backed internal connectors
Source: track: stage-1, sprint: 4
Tags: ingestion, landing, prometheus, home-assistant

Prometheus and Home Assistant API responses should land unchanged through raw-byte landing, while connector-specific validation can run against a projected tabular contract. This preserves immutable upstream evidence in landing and keeps normalization concerns out of the bronze payload.

---

## Lessons

### Claimed sprint items require claim proof for status transitions
Source: track: stage-1, sprint: 4
Tags: sprintctl, claims, coordination

When a sprint item has an exclusive claim, matching actor or workspace metadata is not enough to mutate its status. Status transitions must carry the originating claim proof, including the claim id and claim token, or the operation should fail and be handed off explicitly.

---
