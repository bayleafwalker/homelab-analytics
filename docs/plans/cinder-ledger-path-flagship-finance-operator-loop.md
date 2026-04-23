# Sprint #64 kickoff packet — cinder-ledger-path / Flagship Finance Operator Loop

**Classification:** CROSS-CUTTING
**Status:** Authoritative kickoff packet
**Sprint:** `#64 cinder-ledger-path — Flagship Finance Operator Loop`
**Scope owner:** Kickoff artifact only. This document sets the starting contract for the sprint; it does not pre-implement the broader finance loop.
**Goal:** Make one finance operator journey boringly reliable from source intake to action: ingest a finance source, understand freshness and trust, read the monthly operating picture, run one expense-shock scenario, and leave with a clear next step.

---

## Purpose

This is the tracked, durable kickoff packet for sprint `#64`.

Use it as the authoritative starting point for sprint execution, review, and follow-on docs updates.
The ignored draft at `docs/sprints/flagship-finance-operator-loop.md` is now only a local pointer so the sprint does not depend on an untracked source of truth.

## Scope

- Treat the finance loop as the product, not as a demo of platform flexibility.
- Reuse existing upload, source-freshness, reporting, and scenario surfaces instead of inventing a new finance-specific shell.
- Keep the operator story consistent across docs, API contracts, reporting contracts, and fixture-backed verification.
- Make degraded inputs visible and actionable without forcing the operator to infer state from logs or raw tables.

## Out of scope

- New domain packs, new source integrations, or new scenario types
- Generic seam-reduction work that does not directly unblock the flagship finance loop
- Broad UI redesign outside the finance operator path
- A new route family, renderer lane, or quasi-surface created just for this sprint
- Release-process expansion beyond the proof assets needed for the loop

## Dependencies

- Sprint `#63 confidence-export-seam` far enough along that publication trust metadata is available to app-facing reporting surfaces
- Existing demo bundle and seed flow under `infra/examples/demo-data/`
- Existing operator docs: `README.md`, `docs/runbooks/operator-walkthrough.md`, and `docs/product/source-freshness-workflow.md`
- Existing finance reporting and expense-shock scenario surfaces

## Non-negotiable boundaries

### 1. Keep source freshness/remediation separate from publication trust

Source freshness and remediation stay source-operational concerns:

- stale, overdue, missing-period, failed, rejected, or unconfigured source inputs
- operator next actions such as upload, retry, fix mapping, or inspect a failed run
- primary homes: Sources, Runs, and remediation flows

Publication trust stays publication/reporting concern:

- `freshness_state`
- `confidence_verdict`
- source-freshness rollups attached to a published reporting output
- completeness and quality context for the reporting or scenario input being read

The sprint may thread both kinds of signals through the same operator loop, but it must not collapse them into one concept or rename publication trust metadata as source-remediation state.

### 2. Keep the journey route-neutral until `#414` locks it

The kickoff packet defines the operator sequence, not a new route map.

Until item `#414` lands, refer to:

- the current finance reporting read surface
- the current post-ingest finance destination candidate
- the expense-shock action reachable from that finance path

Do not invent a new page, renderer lane, or interim pseudo-surface just to describe the journey. If the sprint needs a concrete anchor before `#414` finishes, use only an already-owned existing finance reporting surface.

### 3. Keep app/web/API work thin through the application seam

App-facing work must stay thin:

- web, API, admin, and other surfaces authenticate, route, call use cases, and render
- workflow sequencing belongs in `packages/application`
- app-facing reads use reporting-layer contracts and publications, not landing or transformation shortcuts
- finance-view and scenario-entry surfaces must remain consumers of reporting contracts rather than bespoke source-specific query paths

This sprint must not put finance-loop orchestration directly into route handlers, frontend page modules, or ad hoc API glue.

## Canonical operator journey to lock

The sequence to harden across docs and implementation is:

`source upload or refresh -> source freshness and remediation status -> finance reporting read surface -> publication trust context on that surface -> expense-shock action -> visible next step`

This sequence is intentionally route-neutral until `#414` chooses the exact existing destination and inventory.

## Deliverables

### 1. Journey contract (`#414`)

Lock one canonical operator path across docs and implementation surfaces:

- choose the exact existing finance reporting surface that represents the monthly operating read point
- choose the post-ingest default destination or keep the packet explicitly route-neutral until that choice is complete
- align README, walkthrough, route inventory, and finance/scenario references to the same path

### 2. Trust-signal continuity (`#416`)

Thread trust signals through the loop without collapsing semantics:

- source freshness and remediation cues remain source-level and action-oriented
- publication trust metadata remains reporting-level and contract-oriented
- the same vocabulary appears consistently across Sources, Runs, the finance read surface, and the expense-shock entry path

### 3. Monthly operating view to action handoff (`#418`)

Keep one monthly finance reporting surface as the stable read point, then attach one direct operator action:

- launch an expense-shock scenario from the finance path
- show baseline, projected value, and delta without route hunting
- keep the action tied to the same finance story rather than a generic scenario-first workflow

### 4. Proof assets and walkthrough (`#417`)

Refresh the proof so a fresh clone can demonstrate the loop without tribal knowledge:

- walkthrough steps
- proof assets aligned to the chosen route or explicitly route-neutral phrasing
- README and demo copy that tell the same operator story

### 5. End-to-end verification (`#415`)

Add or tighten fixture-backed coverage for:

- ingest -> promotion -> reporting refresh or publication read
- degraded source freshness and remediation visibility
- publication trust visibility on the finance reporting surface
- finance-view to expense-shock handoff

## Acceptance checks

- A fresh-clone operator can follow one documented path from demo data to a visible finance outcome in under 10 minutes.
- After a successful finance ingest, the operator can immediately reach the canonical finance reporting read surface without route hunting.
- If a source is stale, failed, rejected, or missing a period, the loop shows a concrete remediation action.
- If a finance reporting output is degraded or unavailable, the loop exposes `freshness_state` and `confidence_verdict` as publication trust metadata rather than as a substitute for remediation guidance.
- The expense-shock action is reachable from the finance path and shows baseline, projected value, and delta clearly enough to support a household decision.
- Web, API, and admin changes remain thin and route through `packages/application` plus reporting-layer contracts.

## Verification path

- Focused doc and contract updates for the chosen route-neutral or route-locked story
- Targeted `ruff`, `mypy`, and `pytest` only for implementation files changed by sprint items
- `pytest tests/test_architecture_contract.py -x --tb=short` if route, architecture, or contract-boundary work changes the application seam
- `make verify-fast` before any PR or CI-triggering push

## Notes

- This packet narrows ambition on purpose. The sprint proves one operator loop rather than broadening the platform story.
- If scope pressure appears, cut generic cleanup first and preserve the end-to-end finance operator loop.
