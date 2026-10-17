---
doc_id: household-outcome-evidence-decision-plan
status: planned
concern: APP
---

# Household Outcome, Evidence Quality, and Realized Decision

## Goal

Complete one decision-useful Household Operating Picture outcome end to end: answer whether observed battery and tariff economics justify reviewing a household tariff, contract, or battery plan; show source quality and uncertainty; record what the household actually decided and what happened afterward.

This packet joins the existing Household Operating Picture, source-freshness workflow, finance operator loop, and Home Assistant boundary. It does not create another data authority or dashboard.

## Dependencies and contracts

- Use the landing → transformation → reporting layers. App-facing results come from reporting models and stable publications.
- Follow `docs/product/source-freshness-workflow.md`: freshness/remediation is distinct from publication trust.
- Follow `docs/product/core-household-operating-picture.md` and `docs/plans/cinder-ledger-path-flagship-finance-operator-loop.md`.
- Use the read-only measurements from `ha-elisa-kotiakku`; preserve its five-minute granularity, cloud dependency, tariff snapshot assumptions, and heuristic battery-health limits.
- Home Assistant remains the device authority and actuation surface.

## Work

1. **Name the decision.** Select one question whose answer could change a real tariff, contract, or battery-planning decision. Record the authorized decision-maker, evidence window, what evidence could change the decision, and what would count as insufficient evidence. Do not preselect an action.
2. **Qualify sources.** For every source and period preserve source identity, retrieval/update time, reporting interval and timezone, expected/received coverage, gaps, duplicates, backfill status, units, directional-field completeness, tariff inputs, and provenance through landing, transformation, and publication. Label values as observed, derived, heuristic, or user-entered. Missing fields do not silently become zero.
3. **Publish the outcome.** Show observed flows, calculated net site cost and battery-versus-baseline estimate, freshness/coverage, tariff assumptions, and material limitations in one traceable view. Keep actuals, estimates, and assumptions distinct. A forecast is not realized cash, and the comparison does not establish causality beyond its assumptions.
4. **Record realized decision impact.** Link a decision record to the exact publication and source lineage. Capture decision or explicit non-decision, rationale, evidence gaps, uncertainty, authorized actor, and follow-up observation. On follow-up record realized result and whether evidence changed the decision, preserved a deliberate non-decision, or exposed a source/model defect.

## Read-only and authorization boundary

The Kotiakku integration supplies read-only measurements and calculations. This work must not add battery charge/discharge controls, grid-service enrollment, or device credentials to HLA. A recommendation or policy result is not authorization.

Any future device change must execute through Home Assistant under a separate, current, operator approval bound to the specific action and target and checked at execution time. Telemetry permission, a prior decision, or a favorable estimate cannot be reused as actuation permission. Keep recommendation, approval, dispatch, and observed effect as separate records.

## Acceptance

- One named household question has a complete source-to-reporting lineage path.
- The view discloses source freshness, interval coverage, missing fields, tariff assumptions, and observed/derived/estimated/user-entered status for each material value.
- Stale or incomplete data cannot produce a confident positive savings claim; the view gives an actionable remediation.
- A reviewer can reconstruct the result from source windows and calculation assumptions.
- One actual decision or explicit non-decision and a follow-up observation are recorded; projected and realized outcomes remain distinct.
- The read-only Kotiakku source cannot actuate a battery. Any separately authorized HA action remains target-specific and operator-approved.

## Completion evidence

A household operator can assess the answer and its evidence quality, record what they decided, and later compare it with observed results without confusing estimates with actuals or recommendations with authorization.
