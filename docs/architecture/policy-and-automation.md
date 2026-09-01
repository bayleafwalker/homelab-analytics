# Policy and Automation Architecture

**Classification:** CROSS-CUTTING
**Status:** implemented (backend); authoring UI pending (Stage A2)
**Last updated:** 2026-09-01

This document describes the shipped Stage 5 policy engine: the persisted registry, the declarative rule schema, the production evaluation path with its authority semantics, and the boundaries that still hold.

## Current State

Implemented:

- Home Assistant entity ingest, bridge status, MQTT synthetic entity publication, and action dispatch.
- Approval-gated action proposals with approve and dismiss flows; proposal registration is idempotent per action id, and `unavailable` verdicts dispatch no actions and never count as transitions.
- A persisted policy registry: `packages/storage/{postgres,sqlite}_policy_registry.py`, mixed into the control-plane repository (migrations `postgres/0009`, `sqlite/0007`).
- Operator-authored policy CRUD at `/control/policies` (`apps/api/routes/policy_routes.py`), authenticated, with publication-reference validation at create, rule update, and enable.
- A versioned rule schema: `packages/platform/policy_schema.py`, `RULE_SCHEMA_VERSION = "1.0"`, three declarative rule kinds (`publication_value_comparison`, `publication_freshness_comparison`, `ha_helper_state_comparison`).
- Runtime loading in production: `apps/api/ha_startup.py` constructs `HaPolicyEvaluator` with the control-plane store as registry, a publication fetch function, and a last-known-good snapshot file (see "Authority semantics").
- Synthetic publication of selected policy/action state back into HA.

Not implemented:

- The policy authoring UI (`/control/policies` web page) — Stage A2.
- Extension-provided policy templates — seeded via `ensure_builtin_policies` when they exist (A2).
- Demotion of the four code built-ins to seeded registry rows — deliberately not done; see "Built-ins and expressibility".

## Authority semantics

Registry-policy evaluation has exactly three authority modes, visible at
`GET /api/ha/policies/authority` and stamped into each registry result's
metadata:

- **registry** — enabled policies were loaded live from the registry. Every
  successful load persists a versioned effective-policy snapshot to a local
  file under `data_dir` (outside the registry's failure domain).
- **snapshot** — the registry is unreachable; evaluation runs against the
  last-known-good snapshot and reports degraded state. Only *enabled*
  policies are ever snapshotted, so an operator-disabled policy cannot be
  revived by an outage.
- **unavailable** — no registry is configured, or it is unreachable and no
  snapshot exists. Registry policies are not evaluated; nothing is silently
  revived; approval-gated action stays inert.

Code built-ins are bootstrap input only: they evaluate as code and never act
as failover authority for registry-defined policies.

## Evaluation-cycle snapshot semantics

One evaluation cycle observes one snapshot of facts: the effective policy set
is resolved first, the publications referenced by its value-comparison rules
are fetched once as a deduplicated, bounded batch through the reporting
layer, and every policy evaluates against those rows. Each publication-based
result carries that publication's confidence snapshot; stale input
(`OVERDUE`, `MISSING_PERIOD`, `PARSE_FAILED`) forces an explicit
`unavailable` verdict. Missing publication data is `unavailable`, never a
guess.

Every result carries both a `value` and a `reason`. `value` is the measurement
that was read; `reason` states why the verdict holds — the field, observed
value, comparison and threshold for a rule that fired, or the specific cause
when no verdict could be reached (no rows, missing field, non-numeric value,
unparseable timestamp, unknown entity, stale input). The two are not
interchangeable: a stale publication keeps its observed `value` and explains
the staleness in `reason`.

## Built-ins and expressibility

`_BUILTIN_POLICIES` (budget status, monthly spend rate, bridge health,
kitchen-light request) remain code-defined: none is expressible
behavior-identically in the shipped rule kinds. The budget pair aggregate
across all budget rows with dual warning/breach thresholds; bridge health
reads bridge sync state no rule kind covers; the kitchen-light request needs
a `warning` verdict plus approval-action metadata that declarative rules
cannot carry. Approximating any of these with a semantically different rule
is prohibited (the same honesty rule that governs A2 templates). A registry
row can never shadow a builtin id — the evaluator skips it with a warning.

The versioned, idempotent seed machinery (`ensure_builtin_policies`) is
shipped and invoked at API startup: one row per stable id under concurrent
starts, upgrades apply only while the row still matches previously seeded
content, the operator-owned `enabled` flag is never overwritten, operator
deletes are tombstoned, and removed seeds are reported orphaned rather than
deleted. Its production seed list is empty until richer rule kinds or A2
templates exist.

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

`HaPolicyEvaluator` evaluates the code built-ins plus the effective registry catalog (live or snapshot, per the authority semantics above):

1. Resolve the effective policy set under snapshot authority.
2. Resolve declared input data from publication, confidence, and HA state readers — one batched, deduplicated publication read per cycle.
3. Evaluate versioned rule documents with deterministic, side-effect-free logic.
4. Produce `PolicyResult` records with input freshness metadata (per-publication where applicable).
5. Hand action intents to the existing proposal/action-dispatch layer when approval or notification is required; proposal registration is idempotent per cycle.

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

Status as of 2026-09-01 (sprint ember-rule-keel):

- ✅ operator-authored policies are created, updated, disabled, and deleted without editing Python source (`tests/test_policy_registry.py`, `tests/test_policy_api_routes.py`)
- ✅ a versioned rule schema validates policy condition and threshold documents (`packages/platform/policy_schema.py`)
- ✅ `HaPolicyEvaluator` loads enabled policies from the registry at runtime through the production wiring (`tests/test_ha_policy.py::ProductionWiringTests`)
- ✅ built-ins are not the exclusive policy catalog; they are also deliberately **not** demoted to seeded rows (see "Built-ins and expressibility") — the seed machinery exists and is tested, its production list is empty
- ✅ policy definition CRUD is authenticated and tested
- ✅ end-to-end coverage: creation → evaluation → `PolicyResult` → HA surface (`tests/test_policy_e2e.py`)

