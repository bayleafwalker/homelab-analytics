# Sprint K — Household Decision Surfaces

**Status:** Active
**Stage:** 4 — Delivered surface plus corrective packet
**Goal:** Keep the shipped homelab decision surface aligned by closing the remaining reporting-boundary, knowledge-publication, and sprint-state cleanup gaps.

## Why this sprint exists

The worktree already delivered the homelab ROI panel, compare workflow, and compare-set saving path on `main`. The remaining sprint value is no longer another feature slice. It is making sure the homelab scenario baseline uses the same reporting-backed source of truth as the operator surface, publishing the Sprint K decisions into durable repo knowledge, and normalizing the sprint-state artifacts before the next execution slice.

## Scope

- Reporting-backed homelab scenario baseline alignment
- Sprint K knowledge publication from recorded decision events
- Duplicate sprint cleanup and refreshed shared sprint snapshot

## Out of scope

- New homelab product capabilities
- New source connectors or domain foundations
- Runtime-profile simplification
- Generic adapter extraction
- Broad HA feature expansion unrelated to decision support

## Dependencies

- Existing homelab ROI/reporting routes and scenario engine
- Recorded Sprint K events in `sprintctl` and the `kctl` review pipeline
- Canonical live sprint state in sprint `#12`

## Deliverables

1. Reporting-aligned homelab scenario packet:
   creation and staleness checks use the reporting-backed homelab baseline when available.
2. Sprint K durable artifact packet:
   published homelab knowledge entries plus normalized sprint state and refreshed shared snapshot.

## Acceptance checks

- Homelab cost/benefit scenario creation and comparison staleness align with the reporting-backed homelab surface when published reporting is configured.
- `docs/knowledge/knowledge-base.md` contains the approved Sprint K homelab ROI and compare workflow decisions.
- Sprint `#12` is the only active Sprint K record and the shared snapshot reflects items `#75` through `#78`.

## Verification path

- Focused homelab scenario service/API tests plus web/auth architecture coverage
- `kctl extract`, review, publish, and render for Sprint 12 decisions
- `sprintctl maintain check` and `sprintctl render` after live sprint-state cleanup
