# In-process signals and out-of-process semantic research

Status: **operator-requested implementation experiments**, 2026-10-25.
Companion to Agentops
[AE-11/AE-12](https://github.com/bayleafwalker/agentops/blob/main/docs/plans/agentops/2026-10-25-evidence-guided-agent-workflows.md).
This refines the existing [agentic UX/Vuoro alignment](
2026-10-agentic-ux-and-vuoro-alignment.md) and
[household evidence/outcome loop](household-outcome-evidence-decision-plan.md).
No source connector, model-backed production path, policy authority or
actual live dataset is established by this document.

## Why these are two different lanes

**In-process signals** operate near a data refresh, reporting read, or
decision view. They must be cheap, short, bounded, and recoverable. Source
quality and published reporting contracts decide whether a metric or
recommendation is usable. A model may highlight a suspicious pattern but
cannot overwrite qualified facts or actuate a device.

**Out-of-process research** can afford batches, source retrieval, semantic
deduplication, contradictions and stronger weekly synthesis. It should
consume a reproducible collection with rights, provenance, timestamps and
known missing sources. Neither lane needs its own general agent platform.

HLA keeps landing immutable source data, transformation responsible for
normalized/fresh state, and reporting responsible for consumption. All new
agent reads stay within qualified reporting publications. The existing
proposal queue and permissions are authoritative *for that HLA domain*;
Vuoro work/acceptance and Auditctl are not replacements for them. No
agent may turn a draft policy into enabled behavior.

## HLA-S1 — fast typed observation from a qualified reporting snapshot

Choose a bounded real household/reporting question with a named publication,
declared period, source trust/freshness and expected negative cases.
The baseline is a deterministic query over reporting values and quality
flags, not an LLM. Proposed experiment:

```text
reporting publication + trust/freshness
    -> deterministic feature extraction and contract guard
    -> optional cheap choice/typed extraction over a closed question
    -> read-only finding with exact source/revision and method
    -> existing proposal surface if a separately authorized action is desired
```

Test a local small decision model, a typed hosted extractor if data export
is authorized, and no-model baseline under identical fixtures. Avoid
production model calls until privacy, cost, p95 and missing evidence are
qualified. Never feed secrets, internal identifiers, raw household activity
or sensitive records to an external API without the owner's explicit data
permission. Local-only policy must fail closed instead of falling through
to another supplier.

**Acceptance:** measured p50/p95 and throughput under short/long inputs;
source-lineage, key, freshness and unknown coverage retained; one seeded
stale/incomplete fact yields `insufficient_evidence`, one false positive
does not create a real policy/effect, and deleting the model route leaves the
reporting/deterministic answer intact. Any model finding is an inference,
not an observed measurement. Build/release/deployment/field data remain
separate milestones.

## HLA-S2 — reusable source-linked semantic observations

On a frozen permitted event/report set, compare direct downstream source
reads, deterministic extraction, and cheap generative/typed extraction.
Store only a replaceable derived projection with source digest, model/profile,
source and interpretation timestamps, logical input revision, expiry or
supersession, and explicit `source-observed` / `inferred` distinction.
Two *real* independent consumers must use the same observation: e.g. a
household change brief and a retrospective decision-impact analysis.
Do not import an unverified model claim as accepted work evidence.

Measure actual reused reads, false/omitted critical facts, recall of
contradictory inputs, cost including retries/repair, and total reviewer
burden. Prefer the existing reporting/lineage and evidence contracts; do
not add a parallel PostgreSQL history database or Auditctl acceptance writer.

**Acceptance:** stale source corrections invalidate the derived current view
without deleting historical sources; missing collector does not become zero
events, and the multi-consumer path improves a real outcome against direct
retrieval. Stop if most observations are consumed once or semantic
processing introduces material factual loss.

## HLA-S3 — weekly state-of-agent-systems research, out of process

Use a *separate, explicitly permitted* research source inventory such as
engineering blogs, release notes, papers, community discussions and relevant
public Git/issue history. Do not automatically harvest private connected
accounts, employees' information, other owners' credentials or proprietary
work logs. Source terms, robots/usage constraints and access policy are
part of each connector's admission. Each collected item carries URL, author,
retrieved/publication time, license/reuse rights, content digest, source
availability and correction history.

Start with one domain: agent-system execution, tool use, identity, governance
and evaluation. Freeze a representative historical week and compare:

- direct one-off premium-model research over the same source set;
- deterministic ingestion, duplicate detection and change tracking plus
  premium synthesis;
- bounded cheap extraction/clustering plus a premium interpretation pass.

Distinguish **state of the art** (credible advanced research), **state of the
edge** (working but brittle/experimental implementations), and **state of the
commons** (ordinary production practice). An LLM may propose these labels
with source citations; it cannot certify that a vendor announcement is an
independent production proof. Archive disagreement and unknowns; never
invent source coverage or report freshness.

**Acceptance:** same frozen corpus, three clearly sourced tiered summaries,
novelty/change evidence, citation integrity and a separate list of missing or
unretrievable items; actual API/retrieval/storage cost and human correction
time measured against the one-off baseline. A useful weekly recurring feed
requires an explicit scheduler owner and rate/retention controls; this plan
does not create a background task or an autonomous agent.

## HLA-S4 — integrate safely or retire

No new HLA-specific data authority. Existing publication contracts, proposal
draft/approval permissions, and realized-outcome records retain their
meaning. The personal narrative operator may **read** approved HLA findings
through published interfaces, but gets neither proposal resolver credentials
nor device-actuation scope from this programme.

Qualify stale source correction, missing publisher, schema version drift,
duplicate item ingestion, provider timeout, local GPU unavailable, outbound
privacy refusal and restart/rebuild of derived indexes. Record denominators
for each source/consumer; unknown counts are unknown.

**Rollback:** turn off AI projection/aggregation jobs, revert to deterministic
reporting and direct approved-source reads, preserve original landing and
lineage, and clear/rebuild only disposable indexes. All action proposals and
human decisions remain in the existing HLA owner ledger. Reconcile HLA-S1..4
with existing served work before creating new tasks; plan IDs are not work
item IDs. At implementation, follow `make verify-fast` and the repo
requirements/status process.
