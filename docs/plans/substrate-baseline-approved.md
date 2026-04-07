# Substrate Baseline: Platform Kernel and Household App Realignment Plan

**Status:** Approved baseline for repository realignment  
**Owner:** Juha  
**Classification:** CROSS-CUTTING  
**Date:** 2026-03-30  
**Supersedes:** proposed baseline draft  

---

## 1. Purpose

This document defines the approved baseline for realigning `homelab-analytics` around two things sharing one repository for now:

1. a reusable self-hostable data platform substrate (kernel)
2. a first-party household app / flagship capability built on top of that substrate

This is a seam-definition and boundary-enforcement plan.
It is **not** a framework rewrite plan.
It is **not** a repo-splitting plan.
It is **not** a proposal to pause the household app indefinitely while building a generic platform in the abstract.

The goal is to make the kernel and household app **architecturally, operationally, testably, and documentationally separable** while remaining in one repo.

For future backlog planning, treat this kernel-vs-app seam as the outer boundary and use a four-strata stability model inside it: kernel, semantic engine, product packs, and surfaces. The semantic engine is the reusable middle layer that is still too blurred inside mixed pipeline and orchestration code today.

**Guiding rule:** design for extraction, do not extract for design.

---

## 2. Framing

`homelab-analytics` exists because there is no open, self-hostable, long-term-reliable data platform for homelab users that plays the role Databricks or Snowflake play in the cloud: a general substrate for ingesting, modeling, storing, and serving many personal or household domains under local control.

The repository should therefore be judged primarily as:

- a self-hostable platform substrate for personal / household / homelab domains
- plus a first-party household application built over that substrate

The repository should **not** primarily drift into:

- a better budgeting app
- a prettier dashboard suite
- a generic Home Assistant add-on
- a pile of disconnected ETL jobs
- a fake-generic framework invented for hypothetical future consumers

---

## 3. Confidence and verification status

This document contains three kinds of statements:

### A. Mechanically observed
These are based on direct repo inspection from the review pass and should be treated as the most trustworthy category.
Examples:
- specific package relationships
- specific import directions
- specific files currently in `packages/pipelines/`
- specific runtime/container fields

### B. Inferred from current code shape
These are architectural conclusions drawn from the observed structure.
Examples:
- which areas are substrate-like
- which areas are app-like
- which seam is currently the most valuable to harden

### C. Proposed but not yet proven
These are recommended next moves that still need to be validated through implementation.
Examples:
- exact target home for some ambiguous files
- whether a second container type is actually needed
- whether a future route-extension hook is worth introducing

When in doubt, prefer implementation evidence over elegance.

---

## 4. Executive summary

The repo is already **substantially on the way** to being a platform kernel with a sewn-in flagship household app.
The capability pack model, publication contract system, `packages/platform/` structure, and existing architecture tests all show real platform intent.

The current biggest architectural problem is that `packages/pipelines/` is still doing double duty: it contains both platform-generic pipeline infrastructure, the reusable semantic engine, and a large amount of household domain logic. That package, plus platform runtime imports into it, is the main reason the kernel/app seam is blurry.

The approved direction is:

1. treat `packages/pipelines/` as the primary surgical target
2. separate platform-generic pipeline infrastructure from household-domain pipeline logic
3. remove household-shaped assumptions from the runtime/container composition path
4. enforce the seam with tests, docs, and workflow rules
5. remain in one repo until there is real evidence that extraction is warranted

**Single most important move:** start separating `packages/pipelines/` incrementally, domain by domain, beginning with the highest-confidence household-specific files.

---

## 5. Boundary rules

These rules govern future work:

1. Platform/kernel concerns must be understandable without household vocabulary.
2. Household/app concerns must not be promoted into platform unless at least two plausible non-household apps/domains would need them.
3. Cross-cutting items must be called out explicitly rather than quietly smuggled into platform.
4. Avoid rewriting things into fake-generic abstractions unless repeated pain is clearly visible in code, docs, or tests.
5. Prefer validating an explicit composition/registration seam over launching a broad IoC rewrite.
6. Household-specific vocabulary in platform code is a **smell test**, not an absolute law.
7. Do not flatten useful typed app/publication surfaces into vague generic query APIs just to look more platform-like.
8. Prefer small, boring, enforceable changes over sweeping architecture reinvention.

---

## 6. Current-state separation assessment

### 6.1 Already substrate-like

The following areas appear substantially kernel-like already:

- capability pack types and registry
- auth subsystem
- storage layer
- shared infrastructure
- landing / ingestion primitives
- publication field semantics and pack validation
- extension / plugin loading
- most database infrastructure
- architecture test infrastructure

### 6.2 Clearly household-app logic

The following areas are clearly flagship household-app concerns:

- finance, utilities, overview, and homelab manifests
- source contracts for household data sources
- budgets, loans, tariffs, subscriptions, utility bills, HA-specific behaviors
- household scenario types and derived metrics
- household-specific UI screens and workflows
- HA-specific integration surfaces and automations

### 6.3 Mixed / ambiguous / leaky

The main mixed areas are:

- `packages/pipelines/` as a flat mixed package
- platform runtime/container code that directly reaches into household-oriented services
- platform files that contain household-specific dimension or publication assumptions
- shared utilities that still import domain manifests directly
- docs that describe the household app as though it were the platform itself

### 6.4 Existing structural advantages

The split is easier because the repo already has:

- `packages/domains/` with domain manifests
- `packages/platform/` with real generic contracts
- shared entrypoint/container building
- architecture tests that can be extended to enforce boundaries
- explicit capability-pack bootstrapping in the app entrypoints

These are real assets. This is not a blank-slate framework exercise.

---

## 7. Primary seam and approved refactoring target

### 7.1 Primary seam

The approved primary seam is:

**platform-generic pipeline infrastructure**  
vs  
**household-domain pipeline logic**

### 7.2 Main surgical target

The main surgical target is:

**`packages/pipelines/`**

This package currently carries too much mixed responsibility. The approved realignment effort should focus first on making that boundary explicit and enforceable.

### 7.3 What not to do

Do **not** respond to this by:

- extracting a new generic framework repo
- inventing a universal household ontology
- flattening APIs into fake-generic metric/query endpoints
- introducing heavyweight orchestration/catalog systems because the words sound grown-up

The right move is smaller and duller: separate mixed code, then enforce the boundary.

---

## 8. Boundary leak summary

The following leak classes are accepted as the main current problems to address:

### High-severity leak classes

1. **Platform runtime importing mixed pipeline modules**  
   Problem: the kernel composition path cannot be reasoned about without household pipeline code present.

2. **`packages/pipelines/` mixing platform engine code and household-domain code**  
   Problem: there is no reliable architectural seam inside a flat mixed package.

3. **Household-specific dimension/publication assumptions living in platform code**  
   Problem: household vocabulary is being treated like universal substrate vocabulary.

### Medium-severity leak classes

4. **Shared-layer utilities importing domain manifests directly**  
   Problem: lower layers depend on app-level configuration.

5. **Container/runtime shapes typed around household services**  
   Problem: platform composition is household-shaped.

6. **Docs and naming that disguise app-specific content as “builtin” or platform-wide**  
   Problem: architectural confusion gets reinforced by language.

### Low-severity leak classes

7. **API composition paths that still directly name app-specific integrations**  
   Problem: not fatal, but noisy and misleading.

---

## 9. Backlog priorities

### 9.1 Platform / kernel priorities

Approved priorities:

- separate platform-generic pipeline infrastructure from household-domain pipeline logic
- clean household-specific assumptions out of runtime/container composition
- move household-specific contract instances out of platform-level locations
- invert remaining platform dependencies on household-oriented pipeline modules
- promote genuinely generic logic currently stranded in household packages
- add enforcement tests to keep the seam from re-collapsing

### 9.2 App / household priorities

Approved priorities:

- receive household-specific transforms, models, services, and registrations into domain-local homes
- make household publication/registration ownership explicit rather than pretending household content is “builtin” platform content
- keep household-specific routes, workflows, and integrations app-local unless a real shared seam is proven

### 9.3 Cross-cutting priorities

Approved priorities:

- import-boundary tests
- pack-free/minimal-kernel boot proof
- ADR/doc tagging and contribution classification rules
- doc restructure into platform vs household-app areas

### 9.4 Deferred / not-yet-justified items

Still deferred:

- repo splitting
- separate deployable kernel image
- framework extraction into a standalone package
- generic route-extension protocol unless proven necessary
- marketplace/versioning logistics for capability packs
- heavy orchestration/catalog/distributed systems

---

## 10. Approved work packages

### WP-1a: Split finance-domain pipeline logic out of `packages/pipelines/`

**Type:** platform + app (incremental boundary move)  
**Goal:** establish the first real code seam using the highest-confidence household files  
**Scope:** move clearly finance-specific transforms/models/services into `packages/domains/finance/`  
**Why first:** finance has the clearest household-specific vocabulary and the highest chance of yielding immediate boundary clarity  
**Validation:** tests pass; imports updated; no platform package imports finance-domain pipeline modules directly  
**Confidence:** high

### WP-1b: Split utilities-domain pipeline logic out of `packages/pipelines/`

**Type:** platform + app  
**Goal:** continue the seam with another clearly domain-specific cluster  
**Validation:** tests pass; imports updated; utility-specific logic lives under `packages/domains/utilities/`  
**Confidence:** high

### WP-1c: Split homelab/HA-domain pipeline logic out of `packages/pipelines/`

**Type:** platform + app  
**Goal:** relocate HA and homelab-specific logic into domain-local ownership  
**Validation:** imports updated; platform packages no longer reach into HA-specific code  
**Confidence:** medium-high

### WP-1d: Split overview-domain pipeline logic out of `packages/pipelines/`

**Type:** platform + app  
**Goal:** finish the obvious household/domain moves  
**Validation:** overview-specific files no longer live in mixed pipeline space  
**Confidence:** medium

### WP-1e: Resolve ambiguous pipeline files

**Type:** cross-cutting  
**Goal:** classify and relocate the remaining ambiguous files only after the obvious moves are complete  
**Validation:** each ambiguous file is classified as kernel, app, or still temporarily mixed with written justification  
**Confidence:** medium/variable

### WP-2: Remove household-typed fields from the platform container

**Type:** platform  
**Goal:** make the core container platform-shaped rather than household-shaped  
**Approved approach:** first remove domain-typed fields and move domain-service construction upward into composition logic; do **not** introduce a second container abstraction unless the simpler approach becomes clearly awkward  
**Validation:** minimal kernel/container build succeeds without domain services  
**Confidence:** medium-high

### WP-3: Move household-specific contract instances out of platform-level locations

**Type:** cross-cutting  
**Goal:** keep contract *shapes* in platform and contract *instances* in domain/app ownership where appropriate  
**Validation:** platform package no longer contains obviously household-specific contract definitions  
**Confidence:** high

### WP-4: Clean shared-layer imports of domain manifests

**Type:** cross-cutting  
**Goal:** lower layers should not directly depend on domain manifests  
**Validation:** import-boundary tests pass  
**Confidence:** high

### WP-5: Remove remaining platform dependency inversions into mixed pipeline code

**Type:** platform  
**Goal:** ensure platform contracts/builders consume registration input instead of importing household-oriented pipeline modules  
**Validation:** platform has no direct dependency on app-specific pipeline registrations  
**Confidence:** medium

### WP-6: Promote genuinely generic freshness logic if still generic after review

**Type:** platform  
**Goal:** move obviously generic freshness logic into a platform/shared home only if it remains generic after re-check  
**Validation:** other domains can use it without importing finance  
**Confidence:** medium

### WP-7: Add import-boundary enforcement tests

**Type:** boundary enforcement  
**Goal:** make future leaks fail loudly  
**Validation:** CI fails on intentional violations  
**Confidence:** high

### WP-8: Add minimal-kernel boot smoke test

**Type:** boundary enforcement  
**Goal:** prove the kernel can boot in a narrow, meaningful sense  
**Approved success criteria:**
- platform imports cleanly
- container/composition builds with zero capability packs
- health/readiness endpoints respond
- no domain pack registration is required

This is **not** a hollow “demo app” requirement. It is a narrow proof of substrate independence.  
**Confidence:** medium-high

### WP-9: Rename misleading “builtin” household files where appropriate

**Type:** cross-cutting  
**Goal:** stop disguising household-app content as universal platform infrastructure  
**Validation:** names better reflect ownership; no architectural behavior change required  
**Confidence:** high

### WP-10: Add doc classification tags and split documentation by concern

**Type:** docs/process  
**Goal:** make the seam visible in docs and daily workflow  
**Validation:** ADRs/docs tagged as PLATFORM / APP / CROSS-CUTTING; top-level docs distinguish kernel vs household app  
**Confidence:** high

### WP-11: Add contributor/agent decision guide

**Type:** docs/process  
**Goal:** future contributors can classify work before touching code  
**Validation:** example changes can be classified correctly using the guide  
**Confidence:** high

### WP-12: Revisit route-extension/composition hooks only after seam cleanup

**Type:** deferred/platform candidate  
**Goal:** only introduce a pack-based route extension mechanism if hard-coded route composition becomes a real pain after the primary seam cleanup  
**Validation:** evidence of repeated pain exists before implementation  
**Confidence:** intentionally deferred

---

## 11. Execution order

### Recommended first moves

1. **WP-4** — clean shared-layer manifest imports (quick, high-confidence)  
2. **WP-10** — add documentation classification tags (quick, high-confidence)  
3. **WP-1a** — split finance-domain pipeline logic  
4. **WP-2** — remove household-typed container assumptions once the first seam is visible  
5. **WP-7** — add import-boundary enforcement after the first seam cleanup lands

### Execution principle

Do not do one giant “realign the universe” PR.
Prefer domain-by-domain seam proof.
Each step should make the repo slightly more enforceable, not merely more renamed.

### What not to combine in one sprint

- do not combine all `WP-1*` moves into one giant refactor unless the repo is quiet and you explicitly want the blast radius
- do not mix structural seam cleanup with speculative new extension protocols
- do not add enforcement tests before at least the first structural fixes exist

---

## 12. Roadmap

### Near-term: seam definition and enforcement

**Objective:** make the kernel/app boundary visible and enforceable in code  
**Done-enough condition:** first domain splits land; import-boundary tests exist; minimal-kernel boot proof passes or is clearly within reach

### Mid-term: runtime, documentation, and workflow separation

**Objective:** make platform vs app ownership obvious to humans and tooling  
**Done-enough condition:** docs are split by concern; contributors can classify work reliably; remaining runtime/container assumptions are reduced

### Later: extraction-readiness only if earned

**Objective:** be able to extract later if real evidence appears  
**Done-enough condition:** a second credible consumer exists, or the kernel is repeatedly used beyond the household app

### Extraction evidence required

Do not pursue extraction unless at least one is true:

- a second non-household app/domain is actively using the kernel
- an external consumer wants the kernel without the household app
- the monorepo’s CI/release/package friction becomes materially painful
- the minimal-kernel proof and boundary tests remain stable across multiple sprints

---

## 13. Documentation realignment

### Approved doc structure direction

Target structure should evolve toward:

- `docs/platform/` for kernel/substrate concerns
- `docs/apps/household/` for flagship household-app concerns
- `docs/adr/` or existing decision docs with explicit classification tags

### Documentation rules

- platform docs must not quietly assume household semantics as universal
- household docs must stop pretending they describe the whole platform
- each significant design/ADR doc should be tagged as `PLATFORM`, `APP`, or `CROSS-CUTTING`

### First docs to update

1. add classification tags to existing decision/architecture docs  
2. add a short kernel identity document  
3. add a short household-app identity document  
4. update root README to explicitly distinguish kernel vs flagship app  
5. add a contributor/agent decision guide

---

## 14. Do-not-do-yet list

Do not do the following unless later evidence clearly forces it:

1. split into multiple repos
2. extract a standalone kernel framework/package
3. replace typed app/publication surfaces with vague generic query APIs
4. perform ontology-heavy rewrites to sound more platform-like
5. introduce Airflow / Dagster / Prefect / catalog systems / distributed queues without proven need
6. use the household app as the sole proof that the kernel is already general
7. build capability-pack marketplace/versioning machinery
8. build multiple deployment images for kernel vs app

These are classic ways to make a repo look more sophisticated while making it harder to run.

---

## 15. Final recommendation

### Should the repo remain one repo?

**Yes.** Unequivocally.

### What should the seam be called?

Use these exact terms:

- **platform kernel**
- **household app**

### What is the single most important next move?

**Start the incremental `packages/pipelines/` split, beginning with finance-domain pipeline code.**

Not because finance is spiritually special, but because it is the clearest high-confidence boundary and the least ambiguous place to start making the seam real.

### What would justify future extraction?

Only real evidence:

- second credible consumer
- external interest in the kernel alone
- stable minimal-kernel proof over time
- meaningful monorepo friction

Until then, extraction is premature optimization in a nicer shirt.

---

## 16. Relationship to prior baseline

This approved version keeps the strategic core of the earlier baseline while tightening execution discipline:

- the main seam remains the same
- the surgical target remains `packages/pipelines/`
- the monorepo-first conclusion remains unchanged
- the anti-pattern warnings remain in force

The main changes are:

- the primary pipeline refactor is now explicitly **incremental**
- the container change is **softened** to avoid premature new abstractions
- the minimal-kernel boot proof is **narrowly defined**
- confidence/verification status is made explicit

That is the approved posture going forward.
