# Backend-Owned Contracts Workstream

**Status:** Ready to execute
**Date:** 2026-03-22
**Stage alignment:** Stage 7 foundation work for multi-renderer and semantic delivery, with immediate frontend safety benefits

## Purpose

Complete the transition from "contract-disciplined" to "contract-generated" platform delivery.

The current repository already exports OpenAPI and publication contracts and generates frontend artifacts from them. The remaining work is to remove the last handwritten seams, promote publication contracts from structural metadata to semantic renderer contracts, and make the generated contract surface the only allowed source of truth for web and renderer consumers.

This workstream assumes development time is not artificially constrained. The target state is not "good enough for now"; it is the version you keep when you want the contract boundary to stay correct under churn.

## Fully completed end-state

The workstream is only fully complete when all of the following are true.

### 1. Route contracts are backend-owned and mechanically enforced

- Every FastAPI route exposes explicit request and response models.
- The canonical route export is deterministic OpenAPI produced from backend code.
- The frontend consumes generated route types and generated operation signatures.
- There are no handwritten transport DTO mirrors in protected frontend areas.
- Contract drift between backend and frontend fails in CI before merge.

### 2. The frontend transport boundary is thin and fully typed

- The web transport layer owns auth cookies, CSRF propagation, redirects, cache policy, and error normalization only.
- The transport layer does not return `any`, use `as any`, or accept arbitrary string paths for generated operations.
- Read and mutation helpers are typed from generated OpenAPI operations.
- Raw backend `fetch(...)` is forbidden in protected frontend areas outside deliberately allowed route-handler and browser-local cases.
- Handwritten transformations in the boundary are limited to explicit view-model shaping that is distinct from transport schema.

### 3. Publication contracts are renderer-meaningful

- Publication contracts include structural shape and semantic metadata.
- Each publication declares `schema_version`.
- Each field can declare semantic attributes such as unit, grain, aggregation semantics, filterability, sortability, and description.
- UI descriptors reference publication keys and renderer compatibility, not bespoke page assumptions.
- Renderer-facing contract endpoints expose stable discovery payloads for publications and UI descriptors.

### 4. Old compatibility paths are removed

- Transitional alias payloads are deleted after callers migrate.
- Deprecated helpers, duplicate DTOs, and stale handwritten fetch layers are removed.
- The repo contains one canonical contract path for route and publication consumption.

### 5. More than one renderer proves the model

- The Next.js app consumes generated route and publication contracts.
- At least one second consumer uses the same contract artifacts without special backend-only shapes.
- "Headless platform" is demonstrated by real consumption, not only by architecture language.

### 6. Extension packs participate in the same contract system

- External packs can declare publication schemas and UI descriptors that validate against the same contract model as built-ins.
- Contract exports include eligible extension-pack contracts through one documented path.
- Invalid extension contracts fail validation before activation.

### 7. Governance and release handling are complete

- CI checks stale generated artifacts and breaking contract drift.
- Release artifacts include the exported OpenAPI spec, publication manifest, generated frontend artifacts, and a compatibility summary.
- The repo has a documented deprecation policy for contract changes.
- Operators and contributors can tell when a change is additive, compatible, deprecated, or breaking.

## Definition of done

This workstream is done only when all of these conditions hold simultaneously:

- `make verify-fast` is green with generated artifacts committed and in sync.
- The protected frontend contract boundary contains no `any`-typed transport helpers and no operation calls via `path as any`.
- Publication contracts are semantic enough for renderer selection and display defaults without reverse-engineering page code.
- At least one non-web renderer consumes the same contract system.
- Extension-pack contract validation uses the same rules as built-ins.
- Legacy contract shims and compatibility aliases introduced during migration have been removed or deliberately versioned.

## Non-goals

These are out of scope for this workstream:

- redesigning business domains or publication content that is unrelated to contract ownership
- introducing a new frontend framework
- turning renderer contracts into a marketplace or general plugin economy
- mixing auth-boundary or OIDC refactors into the contract-hardening branch sequence

Those are separate workstreams and should not be bundled into contract-completion branches.

## Branch sequence

The branch order below is the recommended merge order. Each branch is intended to be reviewable and independently valuable.

### Branch 01 — `feat/contracts-01-web-client-hardening`

**Goal:** replace the last weakly typed frontend transport seams with generated-operation typing.

**Scope:**

- replace `backendJson(path: string): Promise<any>` with generated-operation keyed helpers
- remove `path as any` and endpoint helper `: any` parameters in the backend boundary
- type the high-traffic read helpers for runs, reporting, control, and auth
- keep auth/cookie/CSRF/redirect logic centralized in one boundary module
- add enforcement that protected frontend areas do not reintroduce raw backend transport drift

**Acceptance criteria:**

- `apps/web/frontend/lib/backend.ts` contains no `Promise<any>` and no `as any`
- generated operation types are used for the migrated read helpers
- reporting and runs pages compile against generated contracts only
- the protected-area contract test fails on new handwritten raw backend drift
- `npm --prefix apps/web/frontend run typecheck` passes without transport `any`

### Branch 02 — `feat/contracts-02-typed-mutations-and-route-handlers`

**Goal:** extend generated typing to mutation paths and Next route handlers.

**Scope:**

- type request bodies and responses for POST, PUT, PATCH, and DELETE flows
- type Next route handlers and shared request helpers that proxy backend mutations
- remove handwritten mutation DTO mirrors where they are only transport schema copies
- consolidate mutation error handling around generated contract expectations

**Acceptance criteria:**

- protected frontend mutation helpers use generated request and response contracts
- route handlers no longer accept or return transport `any`
- mutation tests catch backend request/response drift through generated types
- no protected mutation code path depends on handwritten request-shape mirrors

### Branch 03 — `feat/contracts-03-route-contract-cleanup-and-legacy-removal`

**Goal:** settle canonical route envelopes and remove migration-era compatibility output.

**Scope:**

- migrate remaining callers from alias payload keys to canonical envelopes
- remove compatibility aliases introduced during the transition
- standardize response envelope rules where appropriate
- delete dead code and obsolete tests tied to legacy contract shapes

**Acceptance criteria:**

- each route exposes one canonical response contract unless explicitly versioned
- compatibility aliases such as migration-era duplicate keys are removed
- no route tests depend on superseded payload names
- frontend consumers use only canonical response shapes

### Branch 04 — `feat/contracts-04-publication-semantic-schemas`

**Goal:** make publication contracts semantic enough for renderer use, not just structural export.

**Scope:**

- add `schema_version` to publication contracts
- extend field contracts with semantic metadata such as unit, grain, aggregation, filterability, sortability, and description
- align capability-pack metadata and publication export logic with the richer semantic model
- document the publication contract model for renderer authors

**Acceptance criteria:**

- publication contracts expose semantic metadata beyond storage columns
- generated frontend publication types include the new semantic fields
- at least representative built-in publications declare meaningful semantic metadata
- tests fail if required semantic metadata is absent for scoped publication classes

### Branch 05 — `feat/contracts-05-web-renderer-discovery`

**Goal:** make the web app behave like a renderer consuming backend-owned discovery contracts.

**Scope:**

- drive appropriate navigation, publication availability, and renderer hints from exported UI descriptor and publication contracts
- reduce duplicated renderer assumptions in page code
- add typed discovery helpers for contract endpoints
- define the web renderer's supported contract expectations explicitly

**Acceptance criteria:**

- web discovery paths consume backend-owned publication and UI descriptor contracts
- renderer assumptions are centralized and typed
- page code does not maintain parallel publication registries for covered surfaces
- UI descriptor and publication discovery tests protect the pattern

### Branch 06 — `feat/contracts-06-secondary-renderer-proof`

**Goal:** prove that the contract layer supports more than the Next.js web shell.

**Scope:**

- implement one second renderer or renderer-adapter consumer
- consume the same publication/UI contract system used by the web app
- avoid backend-only special cases for the second renderer
- document the renderer integration path

**Acceptance criteria:**

- one non-web consumer uses the exported contracts successfully
- the second renderer does not depend on bespoke unpublished backend shapes
- renderer discovery and publication rendering behavior are validated by tests

### Branch 07 — `feat/contracts-07-extension-pack-contract-parity`

**Goal:** move extension packs onto the same contract footing as built-ins.

**Scope:**

- validate extension publication contracts and UI descriptors with the same model
- include eligible extension contracts in export/discovery flows
- fail activation or export on invalid extension contract declarations
- document extension-pack contract authoring expectations

**Acceptance criteria:**

- extension contracts validate through the same publication/UI descriptor rules as built-ins
- extension activation fails fast on invalid contracts
- export and discovery support eligible extension contracts
- tests cover both valid and invalid extension-pack contract cases

### Branch 08 — `feat/contracts-08-contract-governance-and-release`

**Goal:** finish the operational side of contract ownership.

**Scope:**

- add breaking-change detection or compatibility reporting in CI/release flow
- define deprecation and versioning policy for route and publication contracts
- publish release-ready contract artifacts and compatibility notes
- document the operator/developer workflow for regenerating and reviewing contracts

**Acceptance criteria:**

- CI distinguishes stale artifacts from actual contract-breaking changes
- release workflow produces route and publication contract artifacts intentionally
- contract compatibility policy is documented in-repo
- contributors have a clear workflow for additive vs breaking contract changes

## Recommended execution order

Use the branches above in sequence:

1. Branch 01
2. Branch 02
3. Branch 03
4. Branch 04
5. Branch 05
6. Branch 06
7. Branch 07
8. Branch 08

This order front-loads mechanical frontend safety, then converges on semantic renderer contracts, and only then widens to renderer proof and extension parity.

## Immediate starting scope

If only one branch starts now, start Branch 01.

It has the best leverage because it closes the last major gap between "generated artifacts exist" and "the frontend must obey them". It is also the shortest path to forcing backend contract changes to fail in the web build instead of leaking through the last handwritten transport seam.

## Acceptance gate for the workstream

Use these gates across the branch sequence:

```bash
make web-codegen-check
make web-typecheck
make web-build
make verify-fast
```

Add narrower targeted tests per branch, but do not consider the branch complete without the full gate.
