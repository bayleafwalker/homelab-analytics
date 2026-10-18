---
doc_id: household-outcome-evidence-decision-plan
status: planned
concern: APP
---

# Household Outcome, Evidence Quality, and Realized Decision

## Current delivery status

**The source-side evaluator is present on canonical main; this plan is not
complete.** HLA includes a transformation helper that consumes
explicitly mapped Home Assistant history, checks complete five-minute windows
for a selected closed month, validates source freshness, units, duplicate
conflicts and the Kotiakku evidence contract, and returns a traced review-only
recommendation or `insufficient_evidence`. Synthetic tests exercise both
recommendation outcomes and refusal cases. A companion change in
`ha-elisa-kotiakku` adds the versioned local sensor attributes that carry its
monthly savings estimates, tariff snapshot and cost inputs.

This does not establish that the integration or HLA has current household data,
that a recommendation has been published to an application surface, or that a
household decision or realized result exists. The contract requires explicit
entity mapping and household timezone. Backfill status remains unknown from HA
state history. The source implementation and synthetic fixtures do not close the
live measurement gate; an operator still needs to supply authorized source
history, verify the mapping and tariff assumptions, and record an actual
decision or explicit non-decision plus a later observation.

Evidence reads are bounded by the assessment timestamp. Timestamped rows outside
the selected decision month do not affect its window-coverage or tariff checks;
records whose relevant scope cannot be established remain an explicit evidence
gap. The source contract carries a month-specific tariff configuration, so a
later month’s tariff update does not silently replace the selected month’s basis.

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

The current source-side evaluator is a transformation helper, not an API or user
surface, so it adds no identity bootstrap. Repository code supports OIDC and
`local_single_user`, while the checked-in `.env.example` keeps identity disabled;
that is code/config evidence only and does not establish the deployed identity
provider or its readiness. Any future publication must use the existing HLA
identity and authorization boundary. This work does not install or configure an
OIDC provider, create bootstrap credentials, or treat disabled local identity as
proof of an authenticated household decision-maker.

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


## KAOS backcast: sustained household outcomes

Planning addendum, 2026-10-18. All activities below are planned, not deployed or
accepted. This refines the [estate KAOS 2028 roadmap](https://github.com/bayleafwalker/agentops/blob/main/docs/plans/agentops/2026-10-18-kaos-2028-roadmap.md).
Sequence is dependency-driven, not a calendar commitment.

### Goal, responsibilities, and obstacles

**G-HLA:** Maintain a household commitment whose recommendations stay qualified
by evidence, whose actual consequences are observed, and whose supervision
burden is measurable. AND-refine this goal into G-HLA-1 explicit commitment
lifecycle, G-HLA-2 evidence-change validity, G-HLA-3 realized-outcome review, and
G-HLA-4 bounded cross-project feedback. Each child is necessary; one successful
recommendation does not satisfy the parent.

HLA owns household commitments, observations, domain decisions, and reporting.
The household operator supplies authorized source access and makes decisions.
Home Assistant retains device authority. Vuoro owns work/experiment accounting
and receives references and bounded feedback, not household state. Agentops owns
the estate baseline and cross-project sequencing.

| Obstacle | Resolution and owner |
|---|---|
| Purpose expires while monitoring continues | K01 stop/review semantics; HLA and commitment owner |
| Source, tariff, or mapping changes invalidate a conclusion | K02 versioned impact and review-required state; HLA |
| Estimated benefit is presented as realized or causal | K03 observed result separated from baseline and attribution hypothesis; HLA |
| Missing effort capture appears as zero cost | K04 coverage and explicit unknown values; HLA/Vuoro |
| Retried feedback duplicates an outcome | K04 stable identity and superseding correction; HLA/Vuoro |

### Feature and activity contracts

**HLA-K01 — Household commitment lifecycle (G-HLA-1).** Depends on AO-K02's
estate baseline, one named household question, and the existing identity and
authorization boundary. Extend this plan's decision record with purpose,
authorized owner, baseline and success measure/window, next review,
evidence-change triggers, stop conditions, state, and history. Reuse the
existing operating picture and finance journey; do not add another dashboard.
Acceptance: fixtures demonstrate success, timed review, source-triggered review,
operator stop, and missing evidence. Stopped commitments produce no new proactive
proposals; historical decisions remain readable. An operator can see why the
commitment remains active and what will stop or reopen review.

**HLA-K02 — Source-change impact and invalidation (G-HLA-2).** Depends on K01
and existing source/publication identities. Extend freshness and lineage, keeping
freshness distinct from publication trust. Acceptance: correcting a source
window, tariff revision, or mapping revision identifies affected publication
revisions, recommendation, and commitment and marks them review-required with
reason, time, and source version. Unrelated periods remain valid; repeated
revision delivery creates no duplicate review. Original evidence remains
reconstructible and recomputation produces a new version. Stale or unknown
quality refuses a confident positive savings claim and identifies remediation.

**HLA-K03 — Realized outcome and attribution review (G-HLA-3).** Depends on K02,
a reporting publication, and actual authorized source observations. Complete the
existing decision/follow-up scope rather than replace it. Acceptance: link a
decision or explicit non-decision to exact publication and lineage; retain
follow-up window, observed result, estimated baseline, attribution hypothesis,
confounders, uncertainty, and missingness. Show actual result separately from
estimated avoided cost. Record one real follow-up and a second scheduled review
that demonstrates continuation or stop. Synthetic fixtures cannot close this
live gate. Recommendations do not authorize actuation.

**HLA-K04 — Outcome and attention feedback (G-HLA-4).** Depends on K03 and
VU-K09's experiment contract. Publish a minimal versioned feedback envelope,
leaving domain state in HLA. Acceptance: export stable commitment/work and
publication references, observation window, accepted/rejected/insufficient-
evidence result, measured attention/cost with capture coverage, and an evidence
pointer. Unknown duration/cost remains unknown. Exclude raw transactions, source
rows, and credentials. Retry yields one logical event; correction emits a
superseding version. Demonstrate receipt and correction in Vuoro and provenance
reconstruction through references without transferring household authority.

Backcast: sustained accepted outcome requires K04 feedback and K03 real reviews;
those require K02 current evidence validity; that requires K01 commitment identity
and the existing source-to-reporting foundations. Build deterministic domain
contracts first; no model provider or new agent platform is required. Consume
Vuoro's external contract when available rather than building duplicate work or
experiment storage in HLA.

### Existing work and implementation handoff

Canonical plan items registered for this addendum: HLA-K01 → #2693,
HLA-K02 → #2694, HLA-K03 → #2695, HLA-K04 → #2696. Registration records
planned implementation scope, not implementation completion.

Reuse tracker items 1860 (finance-loop integration proof) and 1862 (demo and
walkthrough); respect the active owner of 1859 (canonical operator journey).
Items 1868, 1705, 1706, 2332, and 2333 provide existing freshness, snapshot, and
idempotency foundations. Pending 1964–1965 provide recovery qualification;
1973–1974 are conditional shared-deployment dependencies, not evidence of a live
deployment; 1975–1976 provide operating evidence. Items 1966–1967 are optional
agent-consumption paths. Before selecting unfinished confidence/lineage work,
reconcile duplicate pending groups 1552–1558 and 1571–1577 with newer delivered
capabilities. These references come from the 2026-10-18 tracker inspection; live
state and claims must be checked before execution.

Requirements: ANA-05 remains the utility evidence foundation; ANA-10 specifies
the outcome contract and APP-18 the lifecycle/feedback surfaces. Implementation
areas are domain services, transformation/reporting models, existing API/web
surfaces, versioned persistence where necessary, and targeted tests. Preserve
immutable landing, normalized transformation/SCD decisions, and reporting-only
application reads. Do not bypass these layers or add identity provisioning,
battery controls, deployment changes, or a general assistant platform here.

Verification: lifecycle, invalidation, and feedback tests must exercise the
negative cases above; retain `tests/test_kotiakku_evidence.py` coverage. For API or
boundary changes run `make test-target TEST="tests/test_architecture_contract.py -x --tb=short"`. Run targeted tests for changed behavior and
`make verify-fast` before PR or CI-triggering push. Code-bearing scopes receive
dispatch review. A documentation landing records planned scope only; each
implementation and live outcome requires its own evidence before completion.
