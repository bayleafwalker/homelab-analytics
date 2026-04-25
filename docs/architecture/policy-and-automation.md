# Policy and Automation Architecture

**Classification:** CROSS-CUTTING
**Status:** design boundary
**Last updated:** 2026-04-25

This document defines the Stage 5 boundary between the working Home Assistant policy/action examples that exist today and the operator-authored policy engine that is not yet implemented.

## Current State

Stage 5 is scaffolded with working examples, not product-complete policy authoring.

Implemented:

- Home Assistant entity ingest, bridge status, MQTT synthetic entity publication, and action dispatch.
- Approval-gated action proposals with approve and dismiss flows.
- `HaPolicyEvaluator` evaluating built-in Python policy definitions and producing `PolicyResult` outputs.
- Synthetic publication of selected policy/action state back into HA.

Not implemented:

- A persisted policy registry.
- Operator-authored policy CRUD.
- A rule schema or expression model for thresholds and conditions.
- Runtime policy loading from database-backed definitions.
- Extension-provided policy templates.

Until those exist, the current policies in `packages/domains/homelab/pipelines/ha_policy.py` are seeded built-in examples, not the operator-facing policy model.

## Policy Registry

The operator-authored policy engine should introduce a `PolicyRegistry` owned by the platform policy layer and backed by the control plane.

Registry records should include:

- stable `policy_id`, display name, description, enabled flag, and lifecycle timestamps
- `policy_kind`, initially limited to publication threshold, freshness threshold, and HA helper state
- `rule_schema_version` plus a JSON rule document
- declared input publication keys or HA entity selectors
- action definitions for recommendation, alerting, approval-gated automation, or publication-only state
- provenance fields for creator, updater, source kind, and optional extension/template source

Built-in policies should be seeded defaults that can be listed and evaluated through the same read path. Operator-authored policies must be stored separately from Python source and must be creatable, editable, disabled, and deleted without code changes.

## Rule Schema

The first rule schema should stay deliberately small. It should support declarative comparisons against known inputs instead of a general-purpose code execution language.

Initial rule types:

- publication value comparison: compare a named field from a publication row or aggregate to a threshold
- publication freshness comparison: compare freshness/confidence metadata to a threshold or allowed state set
- HA helper state comparison: compare a normalized helper/entity state to a configured value

Rules should declare:

- input reference and field selector
- comparison operator from an allowlist
- threshold value and unit where relevant
- verdict mapping for `ok`, `warning`, `breach`, and `unavailable`
- optional action metadata for proposal or notification creation

The schema must reject arbitrary Python, shell commands, dynamic imports, or free-form expressions. If richer expressions are needed later, they should be introduced as versioned, auditable schema additions.

## API Boundary

Policy definition APIs belong behind authenticated application-service routes, not inside the HA transport layer.

Required endpoints:

- list policy definitions with enabled state and source kind
- get one policy definition
- create an operator-authored policy definition
- update metadata, enabled state, rule document, and action definitions
- delete or archive an operator-authored policy definition
- evaluate policies through the existing policy evaluation path

Mutation endpoints require a policy-write permission. Read endpoints require policy-read permission or an existing admin/control-plane read permission if the permission model has not yet split policy scopes.

HA routes may expose policy results and approval proposals, but they should not become the source of truth for policy definition CRUD.

## Runtime Evaluation

`HaPolicyEvaluator` should evolve from iterating only over `_BUILTIN_POLICIES` to loading an evaluation catalog from the registry:

1. Fetch enabled built-in seed definitions and enabled operator-authored policies.
2. Resolve declared input data from publication, confidence, and HA state readers.
3. Evaluate versioned rule documents with deterministic, side-effect-free logic.
4. Produce `PolicyResult` records with input freshness metadata.
5. Hand action intents to the existing proposal/action-dispatch layer when approval or notification is required.

Evaluation must stay separate from action execution. A policy result can request an action proposal, but dispatch still flows through the approval/action boundary and audit trail.

## HA Publication Path

Home Assistant remains a consumer and actuation surface, not the policy-definition store.

Policy outputs may be published to HA as:

- synthetic sensors for verdicts and values
- queue/count sensors for approval proposal state
- persistent notifications for approval-gated actions
- helper-driven operator intent that becomes an approval proposal

The HA publication path should include `policy_id`, source kind, verdict, evaluated timestamp, and approval/proposal identifiers where applicable so HA dashboards can link state back to platform audit and policy records.

## Acceptance Criteria

Stage 5 policy engine work is complete only when:

- at least one operator-authored policy can be created, updated, disabled, and deleted without editing Python source
- a versioned rule schema validates policy condition and threshold documents
- `HaPolicyEvaluator` loads enabled policies from the registry at runtime
- built-ins are seeded defaults, not the exclusive policy catalog
- policy definition CRUD is authenticated and tested
- one end-to-end test covers policy creation, evaluation, `PolicyResult` production, and HA synthetic publication

