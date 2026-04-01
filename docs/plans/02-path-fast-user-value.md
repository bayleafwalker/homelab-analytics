# Path 2 — Fast User Value

## One-line framing

**Prove that homelab-analytics can turn messy household data into useful answers quickly, with minimal ceremony and clear operator guidance.**

## Strategic intent

This path makes the platform credible by making it feel useful almost immediately.

The target is a first-week operator experience where a user can:

- connect or upload real inputs,
- understand what the platform recognized,
- fix mapping issues without pain,
- get meaningful household insights fast,
- see where the platform is uncertain,
- return later and keep the system alive without dread.

The goal is not “pretty frontend work.”
The goal is a coherent operating flow from onboarding to ongoing household use.

## What weak / good / impressive look like

### Weak

- nicer dashboards,
- better nav,
- some import helpers,
- demo-friendly screenshots but still lots of operator confusion.

### Good

- a guided onboarding flow for key input types,
- a usable source health/remediation flow,
- a reliable first useful answer path,
- a landing page that summarizes household state coherently.

### Genuinely impressive

- upload or connect a few common household data sources and get a coherent household operating picture in one sitting,
- the system proactively points out missing mappings and data quality issues before ingest becomes a later regret,
- the operator gets useful outputs even with imperfect data,
- every next action is obvious: fix this field, upload this month’s statement, review this assumption, acknowledge this anomaly.

## Scope

### In scope

- source onboarding flows for common household inputs
- mapping preview and validation UX
- first useful answer journey
- household operating picture landing page
- ongoing source health and remediation workflow
- demo seed + walkthrough quality
- platform/operator guidance content close to the UI

### Explicit non-goals

- comprehensive renderer diversification
- broad third-party ecosystem packaging
- very advanced simulation science beyond what onboarding can support
- major backend platform rewrites unless required for operator flow

## Implementation shape

### 1. Source onboarding as a product feature

Treat onboarding as one of the platform’s main products.

For each prioritized source type, the operator should see:

- what kind of source this appears to be,
- what core fields were detected,
- what is missing or suspicious,
- what publications this source can activate,
- what additional mapping or assumptions are required,
- what immediate household questions will become answerable.

Priority source types could include:

- account statements / transaction exports
- subscriptions / recurring cost inputs
- utility bills or consumption exports
- loan registry / debt exports
- Home Assistant reference integration data

### 2. First useful answer workflow

Design a structured path from “raw input” to “valuable output.”

A strong flow would look like:

1. upload or connect source
2. detect source type and preview structure
3. validate mappings and data quality
4. ingest and show resulting activated publications
5. render a compact household operating picture
6. highlight the next missing source or remediation step

### 3. Household Operating Picture

Create one landing surface that earns the platform’s name.

This page should summarize:

- current cash position / recent cashflow
- recurring cost baseline
- loan/debt position and ratios
- notable anomalies or surprises
- utilities or home-cost trend view
- source freshness and confidence summary
- recommended next actions

The point is not maximum detail. It is quick orientation.

### 4. Ongoing operator maintenance loop

Make routine maintenance low-friction.

The operator should be able to answer:

- which sources are stale,
- what needs manual upload this month,
- which mappings are unresolved,
- what broke after a source format change,
- which outputs are currently degraded.

Good maintenance UX is one of the biggest hidden differentiators for this kind of platform.

### 5. Demo and seed quality

A platform like this needs a strong “show me” mode.

Ship:

- high-quality demo seed data
- a minimal but sharp walkthrough
- a scripted path that proves the product loop
- screenshots or docs that explain the journey cleanly

## Workstreams

### Workstream A — prioritized source journeys

Choose a small number of high-value source types and build the best path for them.

Suggested first set:

- bank/account transactions
- subscriptions/fixed costs
- loan/debt export
- utilities bill or Home Assistant utilities signal

### Workstream B — onboarding UX and mapping logic

Deliver:

- source type detection and classification
- preview screen
- mapping resolution UX
- validation messages that are actually understandable
- publishable-output preview

### Workstream C — household operating picture

Deliver:

- a dashboard/landing page with a sharp information hierarchy
- a compact trust/freshness strip
- next-actions panel

### Workstream D — source health and remediation

Deliver:

- stale-source list
- unresolved mappings list
- failed ingest history
- remediation workflow from the same surface

### Workstream E — demoability

Deliver:

- polished seed/demo datasets
- scripted walkthrough docs
- screenshot or demo artifact set

## Deliverables

A credible implementation in this path should ship the following:

1. **Guided onboarding flow** for prioritized source types
2. **Mapping preview + validation workflow**
3. **Household Operating Picture** landing page
4. **Source health/remediation** operator flow
5. **First useful answer** documented and demoable end-to-end
6. **Seed/demo package** that makes the platform easy to show and evaluate

## Acceptance criteria

### Minimum bar

- new operator can ingest at least one high-value source without repo spelunking
- resulting outputs are visible quickly
- next steps after ingest are clear

### Strong bar

- multiple key source types share a coherent onboarding pattern
- source health and remediation are integrated into the product flow
- the landing page gives a meaningful household summary without requiring deep drilldown

### Impressive bar

- a user can go from messy raw household inputs to a useful operational summary in one sitting
- the system makes imperfect data still feel productive instead of broken
- the platform clearly communicates both value and uncertainty during the flow

## Verification plan

### Automated

- tests for source detection and mapping validation behavior
- tests for onboarding state transitions
- API/web contract tests for activated publications and next-step hints
- fixture-based tests for common malformed source cases

### Manual/demo

Run a scripted operator journey:

1. start from near-empty state
2. upload a transactions export
3. resolve at least one mapping issue
4. ingest and view cashflow / recurring cost outputs
5. upload a debt/loan source
6. observe updated operating picture
7. allow one source to become stale
8. verify clear remediation instructions

## Risks

- polishing the UI while the flow logic remains confusing
- building too many bespoke source import paths with no shared pattern
- hiding trust/degraded-state info to make the product look smoother than it is
- choosing too many source types and ending with shallow onboarding for all of them

## Anti-patterns to avoid

- “wizard syndrome” where the user clicks through steps but still learns nothing
- mapping screens that assume internal domain knowledge
- a landing page that is broad but not actionable
- demo paths that only work on perfect seed data

## Stop conditions

Stop this path when the following are true:

- a new operator can get to a meaningful household picture quickly
- ongoing upkeep has a clear, low-friction loop
- the platform feels like a product instead of a codebase with an HTTP interface

## Why this path matters

This is the most immediately visible credibility path.

If done well, it answers the simple but brutal question every platform eventually faces:

> Why would anyone actually use this instead of leaving it as an interesting repo?

