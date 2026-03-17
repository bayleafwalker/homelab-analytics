# Core product design workflow

**Status:** Proposed  
**Owner:** Juha  
**Decision type:** Process / product planning workflow  
**Applies to:** Product design, capability-pack planning, feature intake, ADR supplementation

---

## 1. Purpose

This workflow supplements the ADR process.

Use it to keep the project anchored to user value before, during, and after architectural work.

The intent is simple:

- ADRs explain how the system should be structured
- product design documents explain what the system should become worth using for

---

## 2. When to use this workflow

Use this workflow when any of the following is true:

- introducing a new domain or capability pack
- proposing a major new publication set
- expanding a control-plane or admin surface
- proposing a new ingestion path that affects product scope
- considering extension or registry work that claims product value
- deciding whether a feature belongs in core or should be deferred

Do not skip this workflow just because the implementation can be made elegant.

---

## 3. The sequence

### Step 1 — Name the user problem
Write the problem in user-facing terms.

Examples:

- I cannot quickly tell why household cash flow changed this month.
- I do not know whether an electricity contract should be reviewed.
- I do not notice homelab backup drift until it becomes a problem.

Reject proposals framed only as:

- make the platform more extensible
- support more generic renderer flexibility
- expose a new registry hook

Those may be valid support goals, but they are not product problems.

### Step 2 — Define the questions to answer
Write the exact questions the slice must answer.

Good examples:

- Which subscriptions are active and what changed?
- Which current costs are materially above recent baseline?
- Which backup targets are stale right now?

### Step 3 — Define the user-visible outputs
List the publications, views, and insight types that answer those questions.

At this step, do not start with route names, worker commands, or registry wiring.
Start with outputs.

### Step 4 — Define source realism
Document what source classes will feed the slice and whether they are realistic, available, and maintainable.

Ask:

- is the data available in practice
- is onboarding feasible
- can validation failures be made understandable
- is the update cadence realistic

### Step 5 — Define product-grade acceptance criteria
State what must be true for the slice to be useful, not merely implemented.

Examples:

- reruns are idempotent
- primary publications are discoverable
- at least one representative dataset can be onboarded without code edits
- the resulting view supports a clear user decision or follow-up action

### Step 6 — Map to architectural guardrails
Only after the product slice is clear, map it into the platform model.

Document:

- which domain capability pack owns the behavior
- which application use-cases orchestrate it
- which platform services are required
- which adapter surfaces need to expose it
- whether an ADR is needed because architectural constraints change

### Step 7 — Decide core, supporting, or deferred
Classify the work:

- **Core product work** directly improves a core household question
- **Supporting work** improves reliability, maintainability, or operability of a core slice
- **Deferred work** preserves optionality but does not materially improve product value now

### Step 8 — Define what not to do
Every slice should include explicit non-goals.

This prevents a useful pack from quietly turning into a general-purpose framework.

---

## 4. Required outputs from the workflow

A completed product-design pass should produce:

1. a short problem statement
2. a list of user questions
3. a first publication set
4. a first insight set
5. source realism notes
6. product-grade acceptance criteria
7. non-goals
8. architectural mapping notes
9. a delivery priority recommendation

---

## 5. Interaction with ADRs

### A product design document should trigger an ADR when:

- new package or boundary rules are required
- the runtime or dependency composition model must change
- publication, auth, storage, or execution contracts must change
- external loading or extension semantics change materially
- a new adapter type or entrypoint changes the system shape

### An ADR should trigger a product document update when:

- it changes which product slices are feasible next
- it changes the cost or complexity of a domain pack
- it risks shifting effort away from core household outcomes

---

## 6. Review questions

Every proposal should be reviewed with these questions:

1. What household question becomes easier to answer?
2. Which core view improves: Overview, Money, Utilities, or Operations?
3. What publication becomes more useful or newly possible?
4. What user action or decision becomes better because of this work?
5. Is this direct product work, or supporting work?
6. If this were deferred by three months, what user value would actually be lost?
7. What is the smallest complete slice that still feels useful?

---

## 7. Failure modes to avoid

### 7.1 Architecture-first drift
The proposal spends most of its energy on flexibility, boundaries, registries, or adapters while the user-visible value remains vague.

### 7.2 Metrics without decisions
The proposal adds data and charts but does not help the user decide anything.

### 7.3 Domain dilution
A slice is broadened until it stops answering a coherent family of questions well.

### 7.4 Admin-surface substitution
Operator tooling begins to stand in for actual end-user product value.

### 7.5 Optionality theater
A feature is justified mainly because it may enable something later, without a clear near-term product improvement.

---

## 8. Recommended cadence

For any substantial new slice:

1. write or update a product document first
2. confirm whether an ADR is needed
3. plan implementation against both
4. review the result against product-grade criteria, not only architecture cleanliness

---

## 9. Current default recommendation

Until the first cross-domain operating picture feels solid, default priority should favor:

- finance improvements
- utilities improvements
- overview composition
- focused homelab operations visibility

The project should become unreasonably useful at a few things before it becomes broadly extensible at many things.
