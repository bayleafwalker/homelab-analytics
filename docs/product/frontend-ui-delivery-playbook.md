# Frontend UI Delivery Playbook

**Status:** Proposed  
**Owner:** Juha  
**Decision type:** Process / UI delivery workflow  
**Applies to:** `apps/web/`, alternate renderers, component/state review, visual regression checks

---

## 1. Purpose

Frontend work in this repo is a control loop, not a prose-only prompt.

Use this sequence:

`intent brief -> style baseline -> primitives -> scenarios/stories -> implementation -> automated checks -> human approval`

The goal is not frontend purity. The goal is to preserve taste, keep review fast, and stop agent-generated UI from improvising new rules halfway through the work.

---

## 2. Optimize for

- taste preservation
- fast review without reading JSX first
- bounded iteration instead of whole-shell rewrites
- publishable-enough output that is coherent, testable, and defensible

Do not optimize for:

- generic design-system maximalism
- prose-driven one-shot page generation
- visual novelty that ignores product density and operator use

---

## 3. Contract layers

Every substantial UI direction should define three contracts.

### Style contract

This defines how the UI should feel:

- color system
- typography
- spacing scale
- radius and border language
- motion rules
- layout principles
- icon style
- content tone

Agents may propose the style baseline, but they do not get to freestyle around it afterward.

### Primitive contract

This defines the reusable semantic parts of the UI:

- `MetricCard`
- `TrendPanel`
- `EntityTable`
- `FilterBar`
- `StatusBadge`
- `AlertRail`
- `TimelinePanel`
- `DetailDrawer`

Each primitive should specify:

- purpose
- props or data contract
- required states
- accessibility expectations
- interaction notes
- visual do and do-not notes

### Scenario contract

This defines what must be shown, exercised, and tested.

For each primitive and screen, require scenarios such as:

- default
- loading
- empty
- error
- overflow or extreme data
- keyboard interaction
- narrow-width or mobile
- light/dark variants when the direction actually supports both

---

## 4. Roles

### Human responsibilities

- define the intent brief
- approve or reject the baseline
- approve primitives and anti-goals
- review story, screenshot, and browser outputs
- decide when the result is good enough to publish

### Agent responsibilities

- turn the brief into tokens and layout rules
- derive primitive contracts
- generate stories, fixtures, and scenario coverage
- implement from approved contracts instead of reinterpreting the brief
- repair failures without drifting away from the approved baseline

### Tool responsibilities

- prove state coverage
- prove interaction behavior
- catch semantic and accessibility drift
- catch curated visual regressions

---

## 5. Required artifacts

For every publish-lane frontend direction or renderer mode, keep these three files in repo-tracked form:

1. `intent.md`
2. `baseline.tokens.json`
3. `ui-contract.yaml`

The canonical skeleton bundle lives under `docs/examples/ui-contracts/`.

`intent.md` is the human-written taste source.  
`baseline.tokens.json` is the agent-generated, human-approved style baseline.  
`ui-contract.yaml` defines primitives, required states, screen scenarios, and validation expectations.

Do not jump directly from a prompt such as "make it retro" to finished screens when these artifacts do not yet exist for publish-lane work.

---

## 6. Delivery lanes

Use two lanes.

### Draft lane

Use this for fast, disposable exploration.

Minimum expectations:

- intent brief
- rough baseline
- primitive sketch
- screenshots or quick browser output for review

Draft work may move quickly, but it is not treated as the final contract for a stable product surface.

### Publish lane

Use this for stable product-facing surfaces.

Required before broad implementation or merge-ready polish:

- approved `intent.md`
- approved `baseline.tokens.json`
- approved `ui-contract.yaml`
- explicit primitive and scenario coverage
- validation surfaces and curated automated checks

Promotion from draft to publish means freezing the baseline and scenario contract first, not polishing ad hoc output.

---

## 7. Workflow

### Phase 1: Define intent

The human writes a brief that captures:

- audience or mode
- mood and reference adjectives
- density
- motion level
- important screens
- anti-goals

This is the only place where vague taste language should lead.

### Phase 2: Freeze the baseline

An agent proposes tokens and layout principles from the brief. Human approval freezes the baseline. Downstream work uses that baseline instead of repeatedly reinterpreting the original prose.

### Phase 3: Derive primitives

Agents define semantic primitives from the baseline and domain needs. Prefer meaningful names such as `MetricCard` over generic buckets such as `CardA`.

### Phase 4: Derive scenarios

Agents produce the scenario matrix for each primitive and screen. The scenario contract is the review surface, not an afterthought.

### Phase 5: Implement

Implementation consumes:

- the approved baseline
- primitive contracts
- scenario coverage
- reusable mock data

### Phase 6: Validate

Validate both correctness and intention:

- style compliance
- state coverage
- interaction behavior
- accessibility
- curated visual regression

### Phase 7: Human review

Human review can then approve, reject, or request targeted refinement without reopening the entire design direction.

---

## 8. Validation stack

The target publish-lane stack is:

- DTCG-style design tokens plus Style Dictionary or equivalent token export
- Storybook for primitive and screen review surfaces
- Storybook play functions for interaction scenarios
- MSW for reusable mock handlers and fixtures
- Playwright for interaction, screenshot, and ARIA snapshot checks
- axe-core for accessibility automation

This is a target workflow contract, not a claim that every part is already wired in this repo today. Do not report publish-lane automation as complete until the actual toolchain exists and passes locally.

---

## 9. What style tests mean here

A style test is not "an AI judged this attractive."

In this repo, style tests mean:

- token compliance
- primitive usage compliance
- anti-goal enforcement
- screenshot comparison against approved states
- semantic and accessibility conformance

Boring checks are the point. Together they are much harder for generated UI to dodge than a vague taste prompt.

---

## 10. Guardrails

- Do not let agents jump from prose alone to full screens for publish-lane work.
- Do not treat Storybook states or browser screenshots as optional once a surface is meant to be stable.
- Do not add raw visual values outside the approved baseline without changing the baseline itself.
- Do not confuse a disposable experiment with a publishable UI contract.
- Do not pretend every small UI tweak deserves full ceremony; use the draft lane when the work is exploratory and disposable.

---

## 11. Repo use

Use this playbook with:

- `docs/product/core-product-design-workflow.md` for product intent
- `apps/web/README.md` for current frontend runtime and backend-boundary rules
- `docs/runbooks/project-working-practices.md` for implementation and verification loop expectations

When a UI direction becomes durable enough to guide future agent work, promote it into repo-tracked artifacts rather than leaving it in chat history.
