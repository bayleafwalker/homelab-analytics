# homelab-analytics — Platform Credibility Plan Overview

## Theme

**From promising household platform to credible operating system for household decisions.**

The repo now has enough architectural structure, domain coverage, and product surface that the next meaningful question is no longer _what else can it do?_ The question is:

**In what way does the platform become unmistakably credible?**

This planning set frames three different but related paths toward that outcome:

1. **Trustworthy Core** — credibility through semantic integrity, lineage, freshness, and operational honesty.
2. **Fast User Value** — credibility through sharp onboarding, quick wins, and a first-week operator experience that feels coherent.
3. **Real Extension Platform** — credibility through adapters, renderers, and pack contracts that prove the platform can grow beyond a single household implementation.

These are not three random themes. They are three different ways to prove the same thing:

- the platform tells the truth,
- the platform is usable,
- the platform is extensible.

## How to use these plans

Each path document is written as a standalone plan and can be used in one of three ways:

- as a dedicated sprint/epic brief,
- as an architecture guidance document for an agent or pair of agents,
- as a comparison tool to choose the next strategic emphasis.

Each document contains:

- the strategic intent,
- what would count as weak/good/impressive execution,
- scope and non-goals,
- a concrete implementation shape,
- workstreams,
- deliverables,
- verification gates,
- risks and anti-patterns,
- recommended stop conditions.

## Recommendation

If only one path is pursued next, start with **Path 1: Trustworthy Core**.

Reason:

- It reduces the most structural risk.
- It makes later user-facing work more credible.
- It prevents integrations and assistant features from becoming polished nonsense.

If two paths are pursued in parallel, combine:

- **Path 1** as the architecture/control-plane stream, and
- **Path 2** as the operator experience stream.

Only push **Path 3** aggressively once the platform’s semantic spine and onboarding flow are solid enough that extension does not just export instability to new surfaces.

## Suggested sequencing

### Option A — sequential

1. Trustworthy Core
2. Fast User Value
3. Real Extension Platform

This is the safest sequence and best matches the repo’s current maturity.

### Option B — paired delivery

Run two adjacent tracks:

- **Track A:** semantic closure, lineage, freshness, confidence, runtime symmetry
- **Track B:** onboarding flow, source health UX, first useful answer workflow

Then use the resulting contracts to formalize adapters/renderers/packs.

### Option C — demo-first gamble

Lead with a polished onboarding and household operating picture, while doing only minimal hardening.

This may produce a more immediately impressive demo, but it also increases the chance of building a beautiful liar.

## Selection criteria

Choose the path based on what you want to prove next.

### Choose Path 1 if you want to prove:

- the system can be trusted,
- simulations/recommendations are auditable,
- the platform survives growth without semantic drift.

### Choose Path 2 if you want to prove:

- the system is already useful,
- onboarding is not a penalty box,
- the project can become a compelling operator product.

### Choose Path 3 if you want to prove:

- the architecture is genuinely platform-shaped,
- Home Assistant is one adapter among many rather than a special-case pet,
- third-party or future modules can plug in without surgery.

## Definition of success across all paths

Regardless of which path is chosen, a successful outcome should make the following statement true:

> A new operator can ingest real data, understand what the platform knows and does not know, trust the outputs enough to act on them, and see how the same core contracts support multiple surfaces and future extensions.

## Documents in this set

- `01-path-trustworthy-core.md`
- `02-path-fast-user-value.md`
- `03-path-real-extension-platform.md`

