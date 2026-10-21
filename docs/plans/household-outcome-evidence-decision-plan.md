---
doc_id: household-outcome-evidence-decision-plan
status: planned
concern: APP
---

# Household Outcome, Evidence Quality, and Realized Decision

## Current delivery status

**The code path is implemented end to end; the live measurement gate is still
open.** PR #24 merged the source-side evidence qualifier
(`packages/domains/utilities/pipelines/kotiakku_evidence.py`). PR #34
(`feat/outcome-evidence-loop`) adds the rest of the loop:

| Work item | Delivered | Evidence |
|---|---|---|
| 1. Name the decision | Versioned `DecisionDefinition` `kotiakku_battery_plan_review` v1.0.0 (see "Decision definition" below), registered in the composition layer | `packages/domains/utilities/battery_plan_decision.py:24`, `packages/platform/decision_definitions.py`, `packages/pipelines/household_decisions.py` |
| 2. Qualify sources | Qualifier now also returns observed-flow totals over complete windows only and the user-entered cost basis; profile (explicit entity map + timezone) comes from `HOMELAB_ANALYTICS_BATTERY_PLAN_PROFILE`, never guessed | `kotiakku_evidence.py:449` (`_observed_flow_totals`), `:474` (`_cost_basis`), `battery_plan_outcome.py` (`load_battery_plan_profile`) |
| 3. Publish the outcome | Reporting marts `mart_battery_plan_outcome` (verdict, coverage, freshness, tariff snapshot, reason codes, remediation, limitations, lineage) and `mart_battery_plan_outcome_values` (per-value status observed/derived/estimated/heuristic/user_entered, role actual/estimate/assumption/quality, explicit `is_missing`); verdict guard; `refresh-battery-plan-outcome` worker command publishes and records reporting lineage (`source_system=home_assistant`) then recomputes publication confidence; `GET /reports/battery-plan-outcome`; web page `/utilities/battery-plan` | `battery_plan_outcome.py:225` (refresh), `:476` (`_guarded_verdict`), `:498` (value disclosures), `:65` (remediation), `packages/pipelines/battery_plan_outcome_publication.py:42`, `apps/api/routes/report_routes.py:595`, DuckDB `0015`, Postgres `0014` |
| 4. Record realized decision impact | Append-only decision ledger: decision or explicit non-decision pinned to publication key, schema version, period, row reference (`assessment_id`), lineage reference and evidence snapshot; follow-ups record realized result, value status and evidence effect | `packages/storage/decision_ledger.py:118`, `packages/application/use_cases/decision_ledger.py:91`/`:156`, `apps/api/routes/decision_routes.py:66`, SQLite `0008`, Postgres `0015` |

Acceptance mapping:

- *Complete lineage path*: HA history (`fact_ha_state_change`, transformation)
  → qualifier → reporting marts → publication contracts → control-plane
  reporting lineage per source run → decision record lineage reference.
- *Per-value disclosure*: `mart_battery_plan_outcome_values`; missing values
  stay `NULL` with `is_missing = true` (for example `net_site_cost_eur`, which
  evidence contract 1.0 does not supply).
- *No confident positive claim from stale or incomplete data*: `verdict` is
  `insufficient_evidence` unless the assessment has no reason codes, the
  source is fresh and coverage is 100%; remediation text names the fix.
  Tests: `tests/test_battery_plan_outcome.py`.
- *Reconstructable*: `assessment_id` fingerprints the inputs; rows carry the
  entity map, source run IDs, tariff snapshot, window counts and freshness.
- *Decision and follow-up*: `/control/decisions` (reader read, operator
  write; no service-token scope grants either). Insufficient evidence must be
  acknowledged; a stale row reference is refused. Tests:
  `tests/test_decision_ledger.py`.
- *Read-only*: no device credentials or actuation paths; every verdict is
  `recommendation_scope = review_only`, `actuation_authorized = false`; static
  tests assert the modules hold no HA service-call or credential paths.

Still open (operator action, not code): this does not establish that HLA has
current household data. An operator must set the profile with the verified
entity mapping and timezone, ingest authorized HA history, run
`refresh-battery-plan-outcome`, verify the tariff assumptions, record an
actual decision or explicit non-decision, and later record a follow-up
observation. With identity disabled, the ledger records the actor as
`unauthenticated`; it does not treat that as an authenticated household
decision-maker. Backfill status remains unknown from HA state history.

Evidence reads are bounded by the assessment timestamp. Timestamped rows outside
the selected decision month do not affect its window-coverage or tariff checks;
records whose relevant scope cannot be established remain an explicit evidence
gap. The source contract carries a month-specific tariff configuration, so a
later month’s tariff update does not silently replace the selected month’s basis.

### KAOS activities: code delivery (`feat/decision-domains-kaos`, 2026-10-18)

Code for HLA-K01, HLA-K02 and HLA-K04 (and, from 2026-10-21, the HLA-K03 attribution review and K04 attention capture) is implemented and covered by tests on
synthetic fixtures; none of it is a live or field acceptance. HLA-K03's live
gate and the Vuoro receipt half of HLA-K04 stay open (see "Still open" below).

| Activity | Delivered | Evidence |
|---|---|---|
| HLA-K01 commitment lifecycle | `DecisionDefinition` declares purpose, owner (role, optional principal), baseline, success measure, observation window, review triggers, stop conditions and fingerprinted evidence components; battery decision bumped to **v1.1.0**. `record_decision` enforces the owner, derives the review date from the window (an explicit date may not precede the window end), and flags met stop conditions. Terms are pinned per record (`decision_commitments`); state `active` / `review_due` / `review_required` / `stopped` is derived from append-only `decision_lifecycle_events`. Owner stop/reopen; review queue excludes stopped commitments. | `packages/platform/decision_definitions.py:97` (window), `:181` (stop condition), `:202` (definition); `packages/domains/utilities/battery_plan_decision.py:54`; `packages/application/use_cases/decision_ledger.py:174` (owner), `:201` (window), `:206` (stop flags), `:341`/`:384` (stop/reopen), `:454` (state), `:672` (review queue); `apps/api/routes/decision_routes.py:177`, `:313`, `:337`; SQLite `0010`, Postgres `0017`; `tests/test_decision_commitment_lifecycle.py` (success, timed review, source-triggered review, operator stop, missing evidence) |
| HLA-K02 correction tracing | Per decision, the pinned evidence fingerprint is compared with the current reporting row for the same period. A changed source window, tariff snapshot, entity mapping or cost basis records one `evidence_superseded` event (dedupe on decision + superseding fingerprint) naming changed components, correction kinds, affected publications, superseded and superseding row refs, source version and fired review triggers; the commitment becomes `review_required`. A plain re-assessment is not a correction, other periods stay valid, and the original snapshot is untouched. Runs from `POST /control/decisions/evidence-trace`, the `trace-decision-evidence` worker command and after `refresh-battery-plan-outcome`; shown on `/utilities/battery-plan`. | `packages/domains/utilities/battery_plan_decision.py:210` (components); `packages/application/use_cases/decision_evidence_trace.py:95`, `:227` (dedupe); `apps/api/routes/decision_routes.py:195`; `apps/worker/command_handlers/ingest_commands.py:339`; `tests/test_decision_evidence_trace.py` (incl. re-landed HA runs end to end) |
| HLA-K04 outcome reference | `hla-outcome-reference/v1` envelopes replayed from decision history: commitment / publication refs (`work_ref` explicitly `null`), observation window, `accepted` / `rejected` / `insufficient_evidence` / `pending` result, attention and cost with capture coverage (unknown stays `null`, never zero), and a versioned `hla-decision-evidence/v1` pointer. Content-derived `event_id` (a retry is the same event), `supersedes` chain for corrections, `resource-changes/v1` feed. Excludes rationale, snapshots, source rows and credentials. Pull-only: no outbound call. | `packages/application/use_cases/decision_outcome_reference.py:59`, `:240`; `apps/api/routes/decision_routes.py:187`, `:277`; `apps/worker/command_handlers/decision_commands.py` (`export-outcome-references`); `tests/test_decision_outcome_reference.py` |
| HLA-K03 attribution review (code, 2026-10-21) | A follow-up keeps the measured result apart from an estimated baseline: either a value pinned in the commitment baseline (`baseline_value_key`, e.g. `estimated_net_benefit_eur`) or an explicit estimate that must state its basis. It records the attribution hypothesis, confounders, uncertainty and declared missing evidence; `attribution_review` lists every unrecorded part in `not_recorded`, reports `measured_minus_estimate_eur` only when both sides exist, and always says `causal_claim: false`. Operator minutes on the review are captured as `user_entered` and otherwise stay unknown. Follow-up rows stay append-only; rows from before the migration read back as not recorded. The follow-up form on both decision pages takes the new fields. | `packages/application/use_cases/decision_ledger.py:287` (follow-up), `:346` (estimate and basis), `:674` (review payload); `apps/api/routes/decision_routes.py:81`; `apps/web/frontend/app/utilities/_decisions/decision-ledger.js:278`; SQLite `0014`, Postgres `0023`; `tests/test_decision_attribution_review.py` |
| HLA-K04 attention capture (2026-10-21) | `attention` in `hla-outcome-reference/v1` sums the minutes entered on follow-ups: `captured` when every follow-up has minutes, `partial` (known minutes only, never padded) when some do, unchanged `not_captured` / `null` when none do, so earlier exports keep their `event_id`. | `packages/application/use_cases/decision_outcome_reference.py:242`; `tests/test_decision_attribution_review.py` |
| HLA-K03 live-gate enablers (2026-10-21) | **Retrospective entry:** a decision may carry `decided_at` (when the household actually decided, earlier than recording) with a required `retrospective_basis`; the observation window derives from `decided_at`, `created_at` stays the recording time, and the record says `entry_mode: retrospective`. Follow-ups for successive closed periods can then be recorded now, without backdating. **History backfill:** `backfill-ha-history` reads closed-window HA recorder history for the profile entities so past months can be assessed; what HA purged stays a coverage gap. | `packages/application/use_cases/decision_ledger.py` (`_decision_time`); `packages/domains/homelab/pipelines/ha_history_backfill.py`; `packages/domains/homelab/pipelines/ha_service.py` (`ingest_ha_history_states`); SQLite `0015`, Postgres `0024`; `tests/test_decision_retrospective.py`, `tests/test_ha_history_backfill.py` |
| Morning brief | Battery section at order 45 via a `ReportingPublicationReader` accessor; confidence decides confirmed / provisional / withheld; an `insufficient_evidence` verdict is stated as no savings claim with remediation. | `packages/application/use_cases/morning_brief_sections.py:426`, `:798`; `apps/api/routes/briefing_routes.py:64`; `tests/test_morning_brief.py`, `tests/test_briefing_api.py` |
| Second decision domain | `electricity_contract_keep_or_switch` v1.0.0 over `mart_electricity_price_current` (+ contract review, renewal and cost-trend marts) on the same ledger, lifecycle and trace; insufficient-evidence guard (contract, energy price, comparable alternative, twelve usage months); page `/utilities/energy-contract`. | `packages/domains/utilities/energy_contract_decision.py:89`, `:238`; `packages/pipelines/household_decisions.py`; `tests/test_energy_contract_decision.py` |

Still open after this delivery: HLA-K03's live gate (a real decision and
follow-up on authorized household data, recorded with its attribution
review, then a second scheduled review that continues or stops the
commitment; synthetic fixtures cannot close it); HLA-K04's receipt and
correction demonstration in Vuoro (VU-K09's experiment contract is not
available to HLA yet, and HLA does not hold a Vuoro work reference, so
`work_ref` stays `null`). Attention is captured only when the operator enters
minutes on a follow-up; there is no passive time capture.

## Decision definition

`kotiakku_battery_plan_review`, version `1.1.0`
(`packages/domains/utilities/battery_plan_decision.py`). Bump the version when
any field below changes; decision records pin the version they were made under.
Version 1.1.0 adds the commitment lifecycle (purpose, owner, baseline,
success measure, observation window, review triggers, stop conditions);
records made under 1.0.0 keep their fixed follow-up date and are traced from
their evidence snapshot.

- **Question:** Over one closed household-local calendar month, do the
  Kotiakku battery-versus-no-battery estimated savings cover the battery
  plan's effective monthly cost, so that the current battery plan, tariff and
  contract need no review?
- **Authorized decision-maker:** the `operator` role (permission
  `control.decisions.write`); readers can review the evidence and history.
- **Evidence window:** one closed calendar month in the household timezone,
  as complete five-minute source windows from HA history, bounded by the
  assessment timestamp.
- **Evidence that could change the decision:** estimated savings moving
  above or below the effective monthly cost; a change in the battery cost
  basis; a tariff snapshot change; further months showing seasonality;
  observed bills contradicting the estimate.
- **Insufficient evidence:** coverage below 100% of expected windows; source
  older than 15 minutes at assessment; missing, invalid, conflicting or
  ambiguously scoped records; missing/mixed tariff snapshot or signature
  mismatch; missing savings estimate or cost basis, or disagreeing counters;
  unsupported contract/method/period; month not closed; no profile.
- **Outcome options (no action preselected):** keep the current plan; open a
  review; change tariff or contract (executed outside HLA); or the explicit
  non-decision "defer until the evidence improves".
- **Purpose:** keep the battery plan, tariff and contract only while observed
  economics justify them; reopen when the evidence or the plan changes.
- **Baseline:** the subject month's estimated savings, user-entered effective
  monthly cost and their difference (estimates and assumptions, not cash).
- **Success measure:** realized monthly net benefit at least 0 EUR/month,
  recorded on a follow-up as `observed` or `user_entered`; otherwise
  `unmeasured`.
- **Observation window and follow-up:** the first full calendar month after
  the decision; the review is due 14 days after it closes, then every 30 days
  while active. A follow-up records the realized result, an optional realized
  value labelled `observed` or `user_entered`, and whether evidence confirmed
  or changed the decision, preserved a deliberate non-decision, or exposed a
  source or model defect.
- **Review triggers:** observation window closed (timed); source window
  corrected, tariff revised, entity mapping revised, cost basis changed
  (evidence change); verdict changed alongside a correction.
- **Stop conditions:** battery plan ended (flagged by
  `battery_cost_basis_missing`); tariff or contract changed (flagged by that
  outcome); purpose expired (owner stop). Flags recommend a stop; only the
  owner stops a commitment.

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
planned implementation scope, not implementation completion. Code delivery
for K01, K02 and K04 is recorded under "KAOS activities: code delivery"
above; item status is changed by the coordinator, not by the delivery.

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
