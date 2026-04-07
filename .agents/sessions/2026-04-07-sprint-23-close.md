# Session: Sprint #23 Close-out — 2026-04-07

**Model:** claude-sonnet-4-6  
**Branch at start:** main (`d986f0f`)  
**Branch at end:** main (`7276b2f`)  
**Duration:** ~75 minutes (dominated by 57-minute full test suite run)

---

## Context handed in

The prior session (which reset mid-flight) had completed all sprint #23 implementation work:

- Items 120–125 all marked done; sprint had zero pending items
- Review pass (dispatch-review subagent) ran against the batch; blocker + 4 warnings fixed in `2549137`
- RendererRouter (item 125) committed in `3abb4dd`
- Claims released; snapshot refreshed in `d986f0f`

The reset left three untracked artifacts on disk that were never committed:
- `.agents/skills/dispatch-build/SKILL.md`
- `.agents/skills/dispatch-plan/SKILL.md`
- `.agents/skills/dispatch-review/SKILL.md`
- `opencode.json`

---

## Prompts

**1.** *(Session open, state summary pasted)*  
> "Anything left pending action wise?"

**2.**  
> "Close out sprint, collect knowledge artifacts and also session usage for review of new workflows."

**3.**  
> "Can you land session prompt artifacts in worktree for me to pass on."

**4.**  
> "By session artifacts I mean prompts, raised thoughts and agents, resulting changes. E.g. this chat session."

---

## What was done

### Step 1 — Test gate

Ran `python -m pytest tests/` against the full suite. Two failures found:

**Failure 1:** `tests/test_architecture_contract.py::test_architecture_docs_are_classified_as_platform_or_cross_cutting`  
`docs/architecture/adapter-governance.md` was missing its `**Classification:** PLATFORM` header. Added in `ef81f75`.

**Failure 2:** `tests/test_architecture_contract.py::test_request_auth_policy_covers_all_non_public_api_routes` and `test_request_permission_and_scope_policy_covers_protected_api_routes`  
Eight `/adapters/*` routes added during sprint #23 had no entries in either auth function. Added to three places in `packages/platform/auth/scope_authorization.py`:
- `required_role_for_request` → GET: `UserRole.READER`, POST: `UserRole.OPERATOR`
- `required_permission_for_request` → GET: `PERMISSION_REPORTS_READ`, POST: `PERMISSION_ADMIN_WRITE`
- `required_service_token_scope_for_request` → GET: `SERVICE_TOKEN_SCOPE_REPORTS_READ`, POST: `SERVICE_TOKEN_SCOPE_ADMIN_WRITE`

Final result: **1573 passed, 0 failed** (57 minutes).

### Step 2 — Sprint close

```
sprintctl sprint status --id 23 --status closed
# active → closed
```

Snapshot refreshed, all three changes committed together as `ef81f75`.

### Step 3 — Knowledge extraction

`kctl extract --sprint-id 23` produced 10 candidates: 7 durable, 3 coordination.

| ID | Kind | Decision |
|---|---|---|
| 104 | durable | **Rejected** — scope accounting (what was built, not a decision) |
| 105 | durable | **Approved → Published #80** — Adapter trust levels as primary safety boundary |
| 106 | durable | **Approved → Published #81** — Registration/activation lifecycle decoupling |
| 107 | coordination | **Approved (not publishable)** — claim-token handoff lesson |
| 108 | coordination | **Rejected** — duplicate of 107 |
| 109 | coordination | **Rejected** — duplicate of 107 |
| 110–113 | durable | **Rejected** — scope accounting (delivery notes pointing to commits) |

Knowledge base rendered to `docs/knowledge/knowledge-base.md` (81 entries), committed as `7276b2f`.

### Step 4 — Session artifacts

Worktree `session/dispatch-skills-and-opencode` created at `/workspace/dev/homelab-analytics-session-artifacts` with the three dispatch skills, `opencode.json`, and this document.

---

## Commits landed this session

| Commit | Message |
|---|---|
| `ef81f75` | chore: close sprint #23 iron-grove-atlas — test fixes and final snapshot |
| `7276b2f` | docs: publish sprint #23 knowledge extracts (entries 80-81) |
| `20f537a` | chore: land session prompt artifacts for review *(this branch only)* |

---

## New workflow artifacts

### dispatch-plan (`.agents/skills/dispatch-plan/SKILL.md`)

Spawns an **Opus** subagent in read-only planning mode. Returns a decision-complete implementation brief before any repo edits. Trigger: request involves architecture decisions, new scope, or layer-boundary questions not already settled in code.

Key constraints:
- No repo mutations during planning pass
- If scope is already a live sprintctl item, skip to `dispatch-build` or `sprint-resume`
- Plan must be user-confirmed before implementation begins

### dispatch-build (`.agents/skills/dispatch-build/SKILL.md`)

Spawns one or more **Haiku** subagents to execute approved, spec-complete items. Keeps frontier token spend on decisions, not mechanical production.

Key constraints:
- Claim ownership via `sprintctl claim start` before dispatching
- **Do not pass the claim token to the subagent** — keep it in the orchestrating session
- Independent items: `run_in_background=true`, parallel dispatch
- Overlapping files: `isolation=worktree`
- Each item closes with `item-done`, not batched

### dispatch-review (`.agents/skills/dispatch-review/SKILL.md`)

Spawns a **Sonnet** subagent in read-only review mode. Returns findings-first output ordered by severity with file:line references.

Key constraints:
- No repo mutations during review
- If blockers found, routes to `dispatch-build` for fixes before proceeding

### opencode.json

Configures the `opencode` build agent to use `claude-haiku-4-5-20251001` at `temperature=0`. Pairs with `dispatch-build` — sets the model for the build agent tier.

---

## Raised thoughts and observations

### 1. Claim token lost on session reset (highest-risk gap)

The prior session reset while claims were live, expiring claim #144. The workaround (re-claim + `done-from-claim`) worked, but the pattern is fragile. The same failure recurred on item #224: a new subprocess had the same actor name but a different `instance_id` and no token — producing three coordination failure events (`missing-claim-proof`, `invalid-claim-proof` × 2).

**Root cause:** The claim token is generated at `claim start` and lives only in the session that started it. A new session or subprocess attempting to close or hand off the claim has no way to retrieve it.

**Options worth considering:**
- `sprintctl claim start` writes the token to a local temp file (`.sprintctl/claim-<id>.token`) that survives session resets
- `sprint-resume` emits the active claim token automatically when reattaching to a live item
- `dispatch-build` note already says "do not pass the claim token to the subagent" — that implies the orchestrating session must remain live for the full item lifecycle

### 2. Full test suite takes ~57 minutes

`python -m pytest tests/` runs sequentially. The sprint close gate blocks on this. Two implications:
- The close sequence is effectively a multi-hour operation if several fix cycles are needed
- The architecture contract tests (`tests/test_architecture_contract.py`, ~88 tests, ~2s) are the right early-warning check for new routes and docs — worth running immediately after adding routes or arch docs, not waiting for full-suite gate

**Suggestion:** Separate the sprint close gate into two tiers: (1) targeted contracts check on changed files, (2) full suite as a post-close CI confirmation rather than a blocking pre-close step.

### 3. New routes not covered by auth policy at merge time

The `/adapters/*` routes (8 total) landed in the sprint without corresponding entries in `scope_authorization.py`. The architecture contract tests catch this, but only if someone runs them. The `dispatch-build` skill instructs subagents to run targeted tests on changed files — but auth policy coverage tests are in a separate file from the route implementations.

**Suggestion:** Add to the implementation mode guide (`docs/agents/implementation.md`) or `dispatch-build` skill: after adding any new API route, run `pytest tests/test_architecture_contract.py -x --tb=short` as part of local verification.

### 4. Background task output files unreliable

Multiple `run_in_background` bash invocations wrote to output files that appeared empty when polled via `tail`. Workaround was explicit shell redirection to `/tmp/test_results.txt`. This is a tooling behaviour note, not a project issue — but it means the background-polling pattern for long-running commands is unreliable in this environment.

### 5. Coordination candidates are approved but unpublishable

`kctl publish` only accepts durable candidates. The coordination lesson from the claim-token failures (#107) is approved and visible in `kctl status` but cannot be promoted to the knowledge base. This means coordination learnings that are genuinely durable (like "always preserve the claim token") can't enter the same pipeline as architectural decisions.

**Suggestion:** Either a `kctl publish --coordination` flag, or a convention to re-log coordination lessons as durable `decision` events on the next sprint so they can be extracted and published normally.

---

## Open actions

| Item | Owner | Notes |
|---|---|---|
| Merge dispatch skills + opencode.json to main | Dev | Review this worktree first |
| Claim token persistence across session resets | Dev | See §1 above |
| Add arch contract check to `dispatch-build` verification step | Dev | See §3 above |
| Re-log claim-token lesson as durable event on next sprint | Agent | So it can enter knowledge base |
