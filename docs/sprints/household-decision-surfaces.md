# Sprint K — Household Decision Surfaces

**Status:** Active
**Stage:** 4 — Homelab ROI and scenario surface
**Goal:** Close the current operator-facing decision loop around homelab ROI and cost/benefit scenarios instead of widening into more new domains.

## Why this sprint exists

The worktree already moved utility tariff shock and approval-gated action flows forward. The next high-value product work is not another substrate sprint. It is finishing the homelab decision surface that turns the current household operating picture into a decisive control loop.

## Scope

- Homelab value loop: reporting mart plus operator-facing surface
- Homelab cost/benefit scenario
- Scenario comparison view for saved scenarios

## Out of scope

- New source connectors or domain foundations
- Runtime-profile simplification
- Generic adapter extraction
- Broad HA feature expansion unrelated to decision support

## Dependencies

- Existing scenario engine and tariff-shock flow
- Existing homelab pack marts, routes, and HA publication surface

## Deliverables

1. Homelab value loop packet:
   reporting mart and operator surface that tie cost, service value, and actionability together.
2. Stage 4 simulation packet:
   homelab cost/benefit scenario plus comparison view.

## Acceptance checks

- An operator can create a homelab cost/benefit scenario from `/homelab` without reading raw marts.
- Homelab cost/benefit decisions use reporting-layer models and scenario outputs rather than ad hoc API composition.
- Scenario comparison is explainable and clearly separated from observed state.

## Verification path

- Focused reporting, API, and UI tests for each new decision surface
- Scenario tests covering assumptions and comparison outputs
- Requirements and product-doc updates for new decision-support behavior
