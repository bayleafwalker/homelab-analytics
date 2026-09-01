# Kotona Operating Picture — implementation brief (rev 4)

**Status:** approved for Stages A1–A2. Stages B–F dispositioned, not pre-approved.
**Source of record:** the rendered brief, <https://claude.ai/code/artifact/e3719cb2-0303-4f4f-b013-413941029887>.
**Date:** 2026-08-31 (rev 3 content), Kotona Labs identity folded in at rev 4.
**Provenance:** rev 1 was a 13-agent workflow synthesis; revs 2–3 folded owner reviews in verbatim.

This file exists because the brief's governing text previously lived only in the
rendered artifact and a session transcript, while the work it authorises was
being implemented against the repo. Stage A2's scope and acceptance criteria in
particular were not committed anywhere. Sections below are reproduced verbatim
from the brief; commentary is marked as such.

Stage A1 shipped as sprint `ember-rule-keel` (#554, closed 2026-09-01). Its
implemented behaviour is documented in
`docs/architecture/policy-and-automation.md` and in the Stage 5 status of
`docs/plans/household-operating-platform-roadmap.md`; that detail is not
duplicated here.

---

## Stage A2 — operator surface

*Approved, follows A1.*

- New `apps/web/frontend/app/control/policies/` page following existing
  control-page patterns: list with builtin/operator/template distinction and
  enabled state; create/edit with a rule-kind-aware form for the three shipped
  kinds; preview; enable/disable/delete; latest evaluation result and reason per
  policy; authority-mode indicator.
- **Template discipline (replaces rev 1's placeholder rule):** a disabled
  template is *parameterized, not misleading*. Required inputs are marked
  explicitly; enablement is refused until they are supplied; the UI shows the
  publication field, unit, and comparison being evaluated; no
  semantically-different-field approximations (subscription variance is not
  approximated by another field); templates the current rule language cannot
  express honestly are omitted, not faked.
- Ship only honestly expressible templates from existing rule kinds and
  registered publications (candidates: negative-monthly-cashflow,
  utility-cost-above-threshold, stale-critical-source — each verified
  expressible during A2, dropped if not).
- Typed via the committed OpenAPI export flow; UI tests consistent with existing
  `web-ui-test` coverage; codegen checks green.

**A2 acceptance:** an operator authors, enables, and disables a policy entirely
in the UI; it fires through the production path and its verdict is visible with
its reason; a template with missing required inputs cannot be enabled; no policy
appears twice.

The morning-brief design doc (B1 preparation) may proceed independently but does
not block A1/A2 closure.

---

## Decisions in force

- **Scope of approval:** A1 and A2 are approved with the corrections above.
  Stages B–F are dispositioned but not pre-approved; each activates on its
  stated gate. The six-stage roadmap of rev 1 is not ratified as commitment.
- **Strategy is a hypothesis:** indispensable household operating picture first;
  side-business decision support as an experiment; generalization only under
  measured pressure from a real second context.
- **Authority:** last-known-good snapshot model; code built-ins are
  bootstrap-only after activation; degraded and unavailable states are explicit
  and visible.
- **Seed lifecycle** is versioned, hashed, concurrent-safe, and never overwrites
  operator-owned state; rollout is shadow-compared and reversible.
- **Publication evaluation** uses one snapshot boundary per cycle, validated
  references, attached revision/freshness/confidence, explicit unavailable, and
  idempotent proposal creation.
- **Ontology is non-normative;** no CI tripwire, no entity-scope reservation,
  until a second operating context produces a real conflict. Layering and
  publication-contract enforcement continue unchanged.
- **Deterministic before conversational:** B1's morning brief and lineage drill
  precede any LLM surface; B2 runs on opencode when it comes.
- **Policies stay declarative-only;** actions stay approval-gated; actuation
  ships disabled by default in any distributed artifact.
- **Platform layer stays closed;** new work lands as domain packs, storage
  backends, use-cases, or surfaces.
- **Standing hard non-goals:** no invoicing/document workflow, no payroll, no
  double-entry ledger, no tax filing, no row-level multi-tenancy, no hosted
  SaaS, no public marketplace. Any requires a new architecture pass, not a
  sprint item.
- **Deployment** is one-stack-per-operator via the existing Helm chart,
  indefinitely.
- **Assistant runtime:** OpenCode as the first adapter, never as the domain
  interface. Stage B consumers target a narrow internal contract —
  `AssistantRuntime: start(context, policy, tools) → Session`,
  `continue(session, input) → EventStream`, `cancel(session)`,
  `exportEvidence(session) → EvidenceSet` — with `OpenCodeRuntime` as the first
  implementation. OpenCode's coding-agent session, permission, credential, and
  server-lifecycle semantics must not leak into the household assistant domain.
  The boundary is where redaction, tool permissions, provenance, cost
  accounting, and evidence capture live.

### Identity

An endorsed Kotona family — never mechanical prefixing. Brand architecture must
not accidentally become dependency architecture.

| Role | Public form | Purpose |
|---|---|---|
| House/publisher | Kotona Labs | OSS, research, experiments, project portfolio |
| Household product | Kotona Operating Picture | homelab-analytics successor — "Household operations, explainable and kept at home" |
| Agent product | Vuoro by Kotona Labs | distinct product; keeps its name and vuoro.cloud service domain |
| Technical projects | HostProto, ActionQ, sprintctl… | "A Kotona Labs project," not separately branded products |
| Finance domain | Talous | optional pack/surface inside the operating picture |

"Kotona Analytics" is rejected — it says dashboard where the plan says operating
loop. **No code renames:** repository, Python package, and deployment
identifiers stay as they are; renaming for branding is theatre. First move is
publisher metadata and site navigation only. Clearance caveats stand: bare
Kotona is not commercially clean (A-lehdet's kotona.com); proper search precedes
any commercial mark.

### Commercial posture

An option, not a roadmap. A license split is viable only if current copyrights
and dependency licenses permit: server/core AGPL-3.0, HA integration Apache-2.0,
SDK/schemas/example packs Apache-2.0, name and visual identity under trademark
policy. Managed hosting is not "zero multi-tenancy work" — it requires a
multi-customer operational control plane. Revisit only after two independent
installations or explicit recurring demand; until then build no billing, fleet
management, certification machinery, or hosting automation.
