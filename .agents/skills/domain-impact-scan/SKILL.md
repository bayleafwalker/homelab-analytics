---
name: domain-impact-scan
description: Use when evaluating a new domain, ingestion family, or major cross-cutting capability such as health data. Do not use for small feature edits, routine bug fixes, or implementation work whose scope and layer impact are already settled.
---

## Goal

Decide which layers, contracts, docs, and tests a new domain or cross-cutting change must touch before implementation starts.

## Inputs

- The requested domain or capability change.
- Relevant requirements, architecture docs, and existing sprint or plan docs.
- The target sources, dimensions, marts, or app-facing outputs under consideration.

## Steps

1. Name the affected layers: `landing`, `transformation`, `reporting`, and any app surface.
2. Identify the governing docs and contracts that already constrain the change.
3. Check repo-specific domain rules:
   connector landing contract and validation, canonical mapping target, dimension SCD handling, reporting-layer app paths.
4. For a new domain such as health data, list the likely source families, canonical entities, reporting outputs, and any missing product or architecture decisions.
5. Produce a short stop/go note: what can proceed now, what docs must be updated, and what unresolved decision should block implementation.

## Output contract

- A short impact summary grouped by affected layer.
- A concrete list of docs, requirements, and tests that must move with the change.
- An explicit blocker list if the request depends on an undecided contract or product choice.

## Do not

- Do not redesign architecture that already exists in repo docs.
- Do not turn the scan into a full implementation plan.
- Do not approve changes that collapse landing, transformation, and reporting responsibilities.
