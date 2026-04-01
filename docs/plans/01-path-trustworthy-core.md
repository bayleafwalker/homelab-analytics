# Path 1 — Trustworthy Core

## One-line framing

**Prove that homelab-analytics is a decision system that knows what it knows, knows what it does not know, and says so clearly.**

## Strategic intent

This path makes the platform credible by tightening the semantic spine and the operational truth model.

The goal is not more features. The goal is to ensure that every publication, simulation, recommendation, and action proposal can answer:

- what data it used,
- how fresh that data is,
- how complete it is,
- what assumptions shaped the result,
- what degree of confidence the operator should place in it,
- what breaks when a source becomes stale or malformed.

This is the path that turns the platform from “clever household dashboards” into “an operating system for household decisions.”

## What weak / good / impressive look like

### Weak

- a few cleanup PRs,
- some additional validation checks,
- scattered freshness labels,
- improved docs but no real runtime consequence.

### Good

- all capability packs validated consistently,
- runtime symmetry between API and worker paths,
- freshness/lineage surfaced in operator views,
- publication contracts include semantic metadata that downstream surfaces actually use,
- stale or partial sources produce visible degraded states.

### Genuinely impressive

- every published output carries **freshness, lineage, confidence, and completeness**,
- simulations and recommendations are **auditable objects** rather than plain responses,
- the operator can open a trust panel and see the dependency chain behind a result,
- stale data degrades behavior honestly instead of silently drifting into false certainty,
- the same trust model is visible in API, web, assistant answers, and action proposal flows.

## Scope

### In scope

- semantic closure for core shared dimensions and publication metadata
- publication-level freshness/completeness/confidence model
- lineage visibility from source runs to published outputs
- runtime parity and pack registration consistency
- failure-state design for stale, partial, or inconsistent sources
- assistant/recommendation/auditable-action surfaces consuming trust metadata
- verification and test reshaping to assert true contracts rather than brittle string fragments where possible

### Explicit non-goals

- adding many new data sources
- redesigning the entire frontend visual language
- building broad marketplace functionality
- chasing renderer diversity before contracts are stable

## Implementation shape

### 1. Trust metadata model

Introduce or finish a platform-wide trust model attached to publications and derived outputs.

Minimum attributes:

- `freshness_status`
- `freshness_observed_at`
- `completeness_status`
- `confidence_level`
- `lineage_run_ids`
- `assumption_set_id`
- `degraded_reason`
- `source_dependency_summary`

This must not live only in docs. It needs to exist in the control plane and be consumable by:

- API responses,
- web summaries,
- assistant-answer generation,
- action proposal generation,
- source health views.

### 2. Source health to publication health propagation

Make health propagation explicit.

Examples:

- stale utility bill ingest marks downstream utility cost forecast as degraded
- partial transaction ingest weakens anomaly detection confidence
- missing household-member mapping blocks certain affordability or allocation outputs

The platform should stop pretending derived views are equally trustworthy when the upstream evidence is weak.

### 3. Runtime and pack truth alignment

Resolve pack/runtime truth and platform-wide symmetry.

Questions to force into code rather than tribal knowledge:

- Are all registered packs executable by both API and worker?
- If not, how is that declared and enforced?
- Are pack capabilities discoverable as platform metadata?
- Are capability pack validations sufficient to prevent silent dangling references and inconsistent runtime state?

### 4. Auditable recommendation objects

Convert recommendation-like surfaces into explicit objects with provenance.

A recommendation should not just say:

> Utility cost spike likely due to heating load.

It should be able to say:

- source evidence used,
- data freshness,
- assumptions used,
- confidence,
- why alternative explanations were excluded or not considered.

### 5. Trust-oriented operator surfaces

Create a trust/control operator surface with sections such as:

- source health
- degraded outputs
- stale outputs
- lineage explorer
- assumption registry
- confidence distribution across publications

This is not just admin garnish. It is the platform’s honesty interface.

## Workstreams

### Workstream A — semantic closure

Deliver:

- finish remaining core shared-dimension work
- normalize publication semantic metadata across packs
- ensure published contracts contain enough shape for downstream trust/UI use

### Workstream B — runtime parity and pack governance

Deliver:

- reconcile API/worker pack registration behavior
- remove or isolate single-domain backward-compatibility scars
- expose capability pack metadata in one authoritative place

### Workstream C — trust propagation engine

Deliver:

- rules that map source/run health into publication health
- derived-output degradation rules
- confidence scoring/banding model

### Workstream D — auditable outputs

Deliver:

- recommendation/action proposal object model with provenance
- assistant answer composition hooks for source evidence and freshness/confidence notes

### Workstream E — verification

Deliver:

- runtime contract tests for health propagation
- less brittle architecture/source text assertions where practical
- scenario fixtures for stale/partial/malformed input states

## Deliverables

A credible implementation in this path should ship the following:

1. **Trust model specification** in docs and code
2. **Publication health propagation** from source runs into derived outputs
3. **Operator trust dashboard** or equivalent control surface
4. **Auditable recommendation object** used by at least one meaningful surface
5. **Runtime symmetry cleanup** for pack registration/execution semantics
6. **Verification suite** covering stale, partial, degraded, and recovered states

## Acceptance criteria

### Minimum bar

- publications expose freshness and lineage in a usable way
- stale sources create visible degraded states in downstream views
- pack/runtime asymmetries are documented and enforced

### Strong bar

- assistant answers and action proposals consume trust metadata
- confidence/completeness semantics are visible in the operator surface
- recovery from stale/partial states is verifiable and demonstrated

### Impressive bar

- an operator can trace any recommendation or important dashboard tile back through source health, assumptions, and prior pipeline runs
- the system prefers honest degradation over synthetic certainty everywhere
- trust semantics feel native, not bolted on

## Verification plan

### Automated

- contract tests for trust metadata presence in publications
- integration tests for source-health propagation
- scenario tests for degraded and recovered states
- API/web contract tests for surfaced trust metadata
- tests that ensure assistant/action flows include provenance hooks

### Manual/demo

Demonstrate all of the following end to end:

1. ingest healthy source data
2. view healthy publication state
3. make one source stale or partial
4. observe downstream degradation and confidence change
5. recover source
6. verify publication health recovery and audit trail continuity

## Risks

- over-engineering confidence scoring into fake precision
- building an internal metadata cathedral without operator benefit
- conflating “available lineage” with “understandable lineage”
- leaving trust info technically present but invisible where decisions happen

## Anti-patterns to avoid

- adding labels with no behavior change
- burying degraded-state info in admin-only corners
- building recommendation text that sounds more certain than the evidence warrants
- keeping string-based architecture tests long after runtime contract tests could replace them

## Stop conditions

Stop this path when the following are true:

- the platform can explain its important outputs in terms of evidence, freshness, and assumptions
- stale/partial data degrades behavior honestly
- capability/runtime truth is consistent enough that later product and ecosystem work do not rest on hidden contradictions

## Why this path matters

This is the least flashy path and the most strategically important one.

If done well, it becomes the foundation that makes every later UI, assistant, and integration feature feel like part of one truthful system instead of a well-organized collection of optimistic guesses.

