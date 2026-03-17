# Core product: Household Operating Picture

**Status:** Proposed  
**Owner:** Juha  
**Decision type:** Product direction / scope framing  
**Applies to:** Finance, utilities, homelab, publications, dashboard and admin priorities

---

## 1. Executive summary

The platform exists to answer a small set of recurring household questions reliably.

The first product goal is not "be a flexible analytics platform." The first product goal is to become the most useful place to answer:

- what is happening to household money
- what is happening to utilities and contracts
- what is happening in the homelab that affects cost, reliability, or operational risk

This product shape is called the **Household Operating Picture**.

It is delivered through:

1. a cross-domain overview
2. a finance capability pack
3. a utilities capability pack
4. a homelab capability pack

The platform, runtime, publication model, and replaceable presentation adapters exist to support this outcome.

---

## 2. Product north star

A user should be able to open the platform and quickly answer:

1. **Money** — What changed in cash flow, spend, recurring costs, and upcoming obligations?
2. **Utilities** — What am I paying now, what changed, and is any contract or tariff worth reviewing?
3. **Homelab** — What is drifting, failing, filling up, costing too much, or becoming a quiet operational risk?
4. **Overview** — What are the few things that deserve attention right now across all domains?

If a proposed feature does not improve one of those outcomes, it is not core product work.

---

## 3. Product principles

### 3.1 Answer real household questions first
The platform should prioritize useful answers over configurable machinery.

### 3.2 Publications are product surfaces
A publication is not just an internal reporting artifact. It is a product contract that powers dashboards, APIs, automation, and future presentation adapters.

### 3.3 Explainability beats novelty
Insights should be clear, reproducible, and traceable to source data and transformation lineage.

### 3.4 Domain slices should feel complete
A domain capability pack should not exist only as a technical registration mechanism. It should answer a coherent family of user questions end to end.

### 3.5 Admin is supporting infrastructure
Operator-facing control-plane and admin surfaces matter, but they are not the primary product. They exist to support trustworthy ingestion, publication, and operation.

---

## 4. Product scope

### In scope for the initial core product

- household money visibility
- utility and contract visibility
- homelab operational visibility
- cross-domain overview and attention surfaces
- repeatable ingestion with validation, lineage, and rerunnable promotion
- stable publications consumable by multiple presentation adapters

### Not in scope for the initial core product

- full personal-finance planning suite
- generalized observability platform for every homelab metric
- polished plugin ecosystem or extension marketplace
- UI abstraction for its own sake
- broad workflow composition not tied to a product question
- speculative domain packs without a clear user problem

---

## 5. Core views

### 5.1 Overview
The overview is the default product surface.

It should answer:

- what needs attention now
- what changed recently
- which costs or risks moved materially
- which follow-up actions are worth considering

Typical content:

- current month cash-flow summary
- subscription changes or anomalies
- utility cost or tariff alerts
- backup freshness and service health alerts
- a short list of recent significant changes

### 5.2 Money
The money view should answer:

- where money came from
- where money went
- what changed vs recent history
- what spend is recurring
- what upcoming fixed costs exist
- what transactions are new, unusual, or large

### 5.3 Utilities
The utilities view should answer:

- what contracts and tariffs exist now
- what the effective current price is
- how costs changed over time
- whether a contract or tariff deserves review
- whether usage and price are interacting in an unusual way

### 5.4 Operations
The operations view should answer:

- what services are unhealthy or degraded
- whether backups are stale
- whether storage risk is rising
- what workloads or infrastructure are costly or noisy
- whether any operational baseline drifted enough to deserve action

---

## 6. Product outcomes

The initial product should become trusted for four kinds of output:

1. **Visibility** — clear, stable summaries of current state
2. **Change detection** — what is materially different from normal or recent history
3. **Operational recommendations** — simple flags such as review, renew, investigate, or clean up
4. **Reliable publication** — the same answer should be consumable by dashboards, APIs, and automation without custom per-surface logic

---

## 7. Product-grade acceptance criteria

A core product slice is not complete when the code is merely well-structured.

A slice is product-grade when:

- onboarding a representative dataset is straightforward
- validation failures are understandable
- reruns are idempotent where expected
- published outputs are stable and discoverable
- the resulting view answers a real recurring question
- the user can tell what changed and why
- the answer is trustworthy enough to act on

---

## 8. Litmus test for future work

Every proposed feature should answer:

1. Which core view does this improve: Overview, Money, Utilities, or Operations?
2. Which household question becomes easier or faster to answer?
3. What publication or insight becomes better because of this work?
4. Is this support work, or is it direct product work?

If the main answer is "it preserves flexibility later," the work may still be valid, but it is not core product work.

---

## 9. Relationship to the platform ADR

The platform-first modular monolith remains the chosen architectural direction.

This document does not replace that decision. It supplies the missing product target inside those architectural guardrails:

- the platform core owns how execution, auth, lineage, storage, scheduling, and publication lifecycle work
- the domain capability packs own the domain questions and outputs that the user actually cares about
- the presentation adapters remain replaceable because the product is defined by stable outputs, not one privileged frontend

---

## 10. Immediate recommendation

The default development priority should be:

1. strengthen the finance capability pack
2. strengthen the utilities capability pack
3. introduce a focused homelab capability pack
4. deliver a cross-domain overview that composes those outputs into a single operating picture

That is the shortest path to a product that feels necessary rather than merely well-architected.
