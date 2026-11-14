---
doc_id: basis-tracked-revalidation-qualification
status: planned
concern: APP
---

# Qualify revalidation against the basis of an assessment

**Planning status:** requested and accepted for backlog/planning on 2026-11-14.
Implementation, experimental results and production selection remain pending.
This is the canonical qualification packet; estate plans should link here.

## Goal and existing boundary

Determine whether a small, explicit record of an assessment's basis can identify
when its result needs recomputation, including changes to the method while the
source evidence stays identical. Compare it with full recomputation on the
existing `electricity_contract_keep_or_switch` path. No production check is
skipped by this qualification.

Inspected baseline: `9cf62cb7271ed0e15e35877ab772709808470bea`.
HLA-K01 commitment lifecycle and HLA-K02 source correction tracing already exist;
the [household outcome plan](household-outcome-evidence-decision-plan.md) records
their delivery and the separate live gates. Extend those foundations rather than
creating another task, decision, acceptance or evidence owner.

| Existing path | Source |
|---|---|
| Published electricity prices, alternatives and trailing usage → deterministic assessment | `packages/domains/utilities/energy_contract_decision.py` |
| Reporting rows → versioned subject, snapshot, baseline and lineage | `packages/pipelines/household_decisions.py` |
| Pinned components → correction trace and deduplicated lifecycle event | `packages/application/use_cases/decision_evidence_trace.py` |
| Current and historical decision views | `apps/web/frontend/app/utilities/energy-contract/page.js` |
| Existing fixture coverage | `tests/test_energy_contract_decision.py`, `tests/test_decision_evidence_trace.py`, `tests/test_decision_commitment_lifecycle.py` |

The assessment is Decimal arithmetic; its existing fixture has four price rows
and twelve usage rows. No costly model inference or generative asset workload is
established here. Token savings, performance gains and household savings are
unmeasured. Public synthetic fixtures suffice for qualification; they cannot
close HLA-K03's actual follow-up/second-review gate or HLA-K04's Vuoro receipt gate.

## Source identity and assessment applicability

`evidence_fingerprint` identifies source components. `_trace_one()` returns
`unchanged` when those components match, before comparing verdicts. Existing
tests deliberately preserve source evidence through a later reassessment.
Keep that meaning and immutable history.

The experiment separately records the basis used to interpret that evidence:

- Exact subject and selected source-component references/digests, including the
  publication, period/window and known coverage.
- Decision-definition version, effective criteria/thresholds and evaluator code
  revision/digest; an unchanged version label is insufficient if its code changed.
- Publication schema/semantic contract revision and applicable freshness or
  evaluation-time conditions. Incidental timestamps are not dependencies.

Use existing identities and fields where available. This is an experiment-local
record, not a new production persistence or wire contract. Missing or unresolvable
basis means reuse is unqualified: recompute or report the evidence gap. A changed
method may require a current assessment while the old source evidence remains
correct. Do not label that distinction a source-tracing defect.

For a named assessment scope, qualify reuse only when its conservatively complete
input basis is known, no relevant dependency or applicability condition changed,
and the current required cheap checks pass. That basis must cover collection
membership (including additions/removals), negative reads/absence assumptions,
selection predicates, relevant configuration/environment/freshness, and the
criteria and required verifier set as well as the source/method references above.
Only qualified complete declarations or qualified complete observations may
establish that scope. Ordinary observations or inferred edges may widen required
work; they cannot justify exclusions. Missing or incomplete scope means rerun or
explicit unknown, never a reuse claim.

The concrete method seed changes the switch threshold from 5% to 30%, with a
definition-version bump, on the existing 467.88/335.88 annual-cost fixture. The
132 difference is about 28.2%: the verdict changes while source components do not.

## Preregistered corpus and oracle

Freeze twelve cases before developing selection logic: eight development cases
and four held-out cases. Record their fixture hashes, source revision, expected
affected observations, expected non-effects, comparison fields and permitted
volatile-field exclusions. The table fixes the case families; an independent
reviewer pins exact held-out variants and expectations without exposing their
payloads to candidate tuning. Reveal them only after the candidate revision is
pinned. After any post-reveal fix, keep revealed cases as regressions and obtain
new held-out variants; report both attempts. Independent review may be performed
by an agent or existing policy mechanism; it introduces no new human approval gate.

| ID | Split | Change family | Required qualification result |
|---|---|---|---|
| BR01 | Development | Reassessment metadata changes; source and method basis identical | Reuse may be proposed only with qualified complete scope; source history remains unchanged. |
| BR02 | Development | Current energy tariff changes | Recompute dependent cost and verdict; identify `contract_terms`. |
| BR03 | Development | Recorded alternative quote changes | Recompute comparison; identify `alternatives`/`market_reference`. |
| BR04 | Development | Usage coverage drops from twelve months to eleven | Recompute to `insufficient_evidence`; preserve no old qualified claim. |
| BR05 | Development | Non-electricity cost-trend row changes | Exclude the row only when qualified scope proves it irrelevant; otherwise rerun/unknown. |
| BR06 | Development | Switch threshold and decision version change; input values identical | Method basis changes; old source fingerprint cannot qualify reuse. |
| BR07 | Development | Evaluator implementation changes without a version-label change | Detect code-basis change; conservatively recompute. |
| BR08 | Development | Deliver the same source correction twice | Preserve one logical correction event and original snapshot. |
| BR09 | Held out | In-window usage correction changes estimates but not the verdict label | Recompute; identical labels do not establish equal results. |
| BR10 | Held out | Correct an older month outside the selected trailing twelve | Reuse only when qualified scope, including window selection, proves no relevant change. |
| BR11 | Held out | Relevant publication schema/semantic revision changes; values identical | Revalidate applicability rather than relying on source equality. |
| BR12 | Held out | A required prior basis reference is absent or cannot be resolved | Refuse a reuse claim; retain explicit unknown basis and recompute. |

For every case, fully execute the existing assessment and trace path against the
same frozen post-change inputs, contract and verifier revision in isolated state.
This reference is independent of candidate skip decisions, reused outputs and
repair artifacts. Evaluate the candidate in a second isolated state and compare
assessment, missingness, snapshot preservation and lifecycle effects. Always run
the full reference, including cases the candidate would reuse, and the cheap checks
required for this scope on both sides. The selector cannot waive those checks.
The twelve-case corpus need not expand to enumerate every shared repository gate.

Expected effects come from the frozen case contract and independent review, not
from the candidate's own dependency declarations. Compare monetary values,
verdicts, reason codes, coverage, affected subjects and deduplication; explicitly
account for changed method/schema references. Only preregistered incidental
metadata may be excluded. Full recomputation is an equivalence baseline, not an
independent proof of the domain formula; retain existing domain assertions.

First verify that the full reference detects the preregistered tariff, missing-
evidence and threshold changes (BR02/BR04/BR06); a reference that misses them
invalidates the run even if candidate/reference parity holds. Separately, reuse
controls BR01/BR05/BR10 prevent blanket invalidation from appearing selective.
Intentionally broken candidates that always reuse or ignore method
changes must fail. Always-recompute remains the correctness baseline and receives
zero avoided-work credit. The denominator is all twelve cases and all declared
observations, including failed, unknown and refused cases. This small corpus is
an engineering qualification, not a statistical reliability claim.

## Acceptance and economics gate

1. No seeded required revalidation is missed, including all held-out method,
   semantic and missing-basis cases. Historical snapshots remain reconstructible.
2. Candidate and baseline agree on the specified result/lifecycle semantics;
   repeated delivery has no duplicate effect. Any mismatch fails qualification.
3. Record unnecessary invalidations and correctly reusable positive controls;
   omitted work is never counted from the candidate's own success labels alone.
4. Measure baseline work, candidate selection/recording overhead and residual
   recomputation under the same frozen inputs/runtime. Preregister repetitions
   and warm/cold conditions; retain raw measurements and failed attempts.
5. Report elapsed time, actual check/assessment counts, storage/read overhead and
   measured operator effort separately. Unknown effort/cost stays unknown. Shadow
   oracle cost is reported separately from projected production-selection cost.
6. A savings claim requires positive measured net benefit after selection and
   basis-maintenance overhead on this real path. Avoided calls alone are not
   savings. If the arithmetic is too cheap, measurements are inconclusive, or
   overhead dominates, retain the correctness finding and stop optimization.
   Do not expand into expensive models or generated assets to rescue a negative
   economic result on this path.

The report ends with continue, narrow, or stop, with evidence and limitations.
Passing this packet does not enable production skipping, deploy changes, widen
data access or authorize household actions. Any later production selection is a
separate scoped decision. Existing reporting-only application reads and household
decision authority remain the boundary throughout the experiment.

## Backlog reconciliation and proposed packets

Existing documented refs: HLA-K01 **#2693**, HLA-K02 **#2694**, HLA-K03 **#2695**,
HLA-K04 **#2696**. These are references, not a statement of current live status.
Reconcile #2694's scope and claims first; extend its existing qualification work
or create linked child/follow-up work only for uncovered scope. Do not duplicate
the delivered source-tracing implementation or reopen completed work by inference.

| Local packet label and proposed title | Native priority | Dependency | Acceptance/deliverable |
|---|---|---|---|
| HLA-BR01 — Freeze source and method basis with twelve preregistered cases | 2 | Reconcile #2694 and inspect current code | Frozen basis/comparison contract, 8/4 split, fixture manifest, reviewer-held variants and declared measurement procedure. |
| HLA-BR02 — Qualify selective revalidation against full recomputation | 2 | HLA-BR01 | Offline comparison runs all twelve cases, positive controls and broken candidates; preserves source/method distinction, unknowns, history and deduplication; no production skips. |
| HLA-BR03 — Decide whether assessment reuse earns its cost | 3 | HLA-BR02 | Evidence-backed correctness/economics report with complete denominators, raw observations, net overhead, and continue/narrow/stop outcome; no unmeasured savings claim. |

Owner follow-through scope and acceptance stay in the linked
[VU-BR1](https://github.com/bayleafwalker/vuoro/blob/main/docs/plans/2026-10-30-agent-substrate-integration.md#planning-backlog),
[SC-BR1](https://github.com/bayleafwalker/sprintctl/blob/main/docs/plans/2026-10-25-evidence-guided-completion.md#planning-backlog)
and [AO-BR1](https://github.com/bayleafwalker/agentops/blob/main/docs/plans/agentops/2026-10-25-evidence-guided-agent-workflows.md#2026-11-14-refinement-basis-tracked-revalidation) addenda.

These labels are packet references, not tracker IDs. Reuse existing matching work
where present. Dispatch posture is planning/fixture freeze for BR01, then bounded
experiment implementation for BR02 and evidence review for BR03. Keep this work
in backlog until selected; the live household gates do not block synthetic
qualification, and synthetic qualification cannot complete those live gates.

**Registration pending:** on 2026-11-14 the served read returned
`workspace-ambiguous` because the caller assertion names multiple repositories;
the tool exposes no workspace selector and no scoped CLI credential was available.
The coordinator must read live items/claims and register only missing scope when
that route is available. No live status, claim, completion or snapshot is inferred
from this planning landing; do not hand-edit the sprint snapshot.

## Implementation and verification handoff

Confine the experiment to fixture/verification support and its report. Do not
change production fingerprint semantics or add a generic dependency service.
Record the exact baseline and candidate revisions, runner commands and environment
in the eventual evidence bundle. Preserve all failed and superseded attempts.

Existing regression entry point:

```bash
make test-target TEST="tests/test_energy_contract_decision.py tests/test_decision_evidence_trace.py tests/test_decision_commitment_lifecycle.py -x --tb=short"
```

Add focused experiment tests when implementing BR02; the command above does not
claim to exercise the new qualification. For this documentation landing run
`make verify-docs` and link/diff checks. Follow the repo's `make verify-fast` gate
before a PR or CI-triggering push. Record actual execution separately from the
planned commands; nothing in this packet claims a test run or completed experiment.
