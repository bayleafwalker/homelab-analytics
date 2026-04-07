# Project Working Practices

**Classification:** CROSS-CUTTING

## Purpose

This runbook defines the repository's default working practices for how work starts, moves, and closes.

Use it to keep process rules in one tracked place instead of distributing them across sprint docs, session notes, or ad hoc task history.

For sprintctl and kctl command details, use `runbooks/sprint-and-knowledge-operations.md`.

## Source-Of-Truth Stack

When sources disagree, follow them in this order:

1. `sprintctl` live state for execution status, claims, active work, and structured events
2. `docs/sprint-snapshots/sprint-current.txt` for the shared current sprint view when a tracked artifact is needed
3. runbooks, `AGENTS.md`, mode guides, and skills for durable process rules
4. requirements, architecture docs, and product docs for intended behavior and design constraints
5. session notes for local history only

Interpretation rules:
- use live `sprintctl` state to choose or resume sprint work when the local DB is available
- use sprint docs, plans, and session notes to explain work, not to override live execution state
- promote any repeated rule from a session note into a tracked runbook, skill, or guide

## Working Loops

### 1. New scope registration

**Start trigger:** accepted scope needs execution tracking and is not yet represented in `sprintctl`.

**Consult first:** requirements, architecture docs, product docs, and the current sprint/runbook context.

**While in progress:**
- use `sprint-packet` to define goal, scope, deliverables, acceptance, and verification
- load `.envrc` and register the sprint or items in `sprintctl`
- slice items by repo boundary or deliverable, not by vague task labels
- render `docs/sprint-snapshots/sprint-current.txt` after the live sprint state is registered

**Close-out artifacts:** registered sprint/items and refreshed shared sprint snapshot when the state is meant to be shared immediately.

**Primary references:** `AGENTS.md`, `runbooks/sprint-and-knowledge-operations.md`, `.agents/skills/sprint-packet/SKILL.md`

### 2. Resume existing sprint item

**Start trigger:** the request is phrased as continue sprint work, pick up the next sprint item, resume a brief, or otherwise execute already-scoped work.

**Consult first:** live `sprintctl` item state and claims.

**While in progress:**
- load `.envrc` before consulting or mutating sprint state
- inspect item status, active claims, and recent events
- follow the claim lifecycle in `runbooks/sprint-and-knowledge-operations.md` or `sprintctl agent-protocol --json` before repo edits when parallel overlap is possible
- if an exclusive claim already exists, only continue when the current session clearly owns it through `claim_id` plus `claim_token`; otherwise stop repo edits and resolve a handoff or pick different work
- move the item to `active` before implementation when appropriate
- log `decision` or `lesson-learned` events when process, coordination, or design rules are clarified during execution; do not wait until sprint close to capture them
- use sprint docs, requirements, and architecture docs only as implementation context for the selected item

**Close-out artifacts:** updated item state, claim metadata, relevant events, and refreshed snapshot after material state changes.

**Primary references:** `AGENTS.md`, `runbooks/sprint-and-knowledge-operations.md`, `.agents/skills/sprint-resume/SKILL.md`

### 3. Implementation

**Start trigger:** a scoped item or direct request is ready for repo changes.

**Consult first:** the applicable requirements, architecture docs, contracts, fixtures, and extension points for the target layer.

**While in progress:**
- preserve the landing, transformation, and reporting layer split
- for substantial web UI or renderer work, follow `docs/product/frontend-ui-delivery-playbook.md` and freeze repo-tracked `intent.md`, `baseline.tokens.json`, and `ui-contract.yaml` artifacts before broad publish-lane implementation
- update docs or requirements when behavior, architecture, or scope changes
- keep sprint state current if the work is sprint-scoped
- use focused local verification during implementation and broader checks before review or push

**Close-out artifacts:** repo change, matching tests or verification, any required requirements/docs updates, and sprint updates when applicable.

**Primary references:** `docs/agents/implementation.md`, `.agents/skills/code-change-verification/SKILL.md`

### 4. Review

**Start trigger:** the change shape is stable enough to inspect for defects, regressions, and missing coverage.

**Consult first:** diff, relevant requirements and architecture sections, and the applicable change-class checklist below.

**While in progress:**
- review findings before summaries
- check traceability between requirements, implementation, and tests
- confirm layer boundaries still hold
- note residual risk or verification debt explicitly

**Close-out artifacts:** findings-first review summary or reviewer handoff.

**Primary references:** `docs/agents/review.md`, `.agents/skills/pr-handoff-summary/SKILL.md`

### 5. Release or push

**Start trigger:** work is about to move to PR, branch push, CI, or release-oriented handoff.

**Consult first:** the verification path plus the release-governance and release/ops docs affected by the change.

**While in progress:**
- run the smallest useful checks first, then broader repo gates
- run `make verify-fast` before opening a PR or pushing a branch that will trigger CI
- update release, workflow, or deployment docs when the change affects them
- keep secrets reference-based and out of tracked files

**Close-out artifacts:** verification summary with commands actually run, updated release assumptions, and any handoff material required for the next engineer or reviewer.

**Primary references:** `AGENTS.md`, `docs/runbooks/release-governance.md`, `docs/agents/release-ops.md`, `.agents/skills/code-change-verification/SKILL.md`

### 6. Sprint close

**Start trigger:** the sprint is substantially complete or needs formal close-out and carryover decisions.

**Consult first:** live `sprintctl` state, open items, and recent event history.

**While in progress:**
- run `sprintctl maintain check`
- carry over unfinished work that belongs in the next sprint
- close the sprint only after execution state is accurate
- run `kctl extract`, review candidates, and publish knowledge when that output belongs in repo memory

**Close-out artifacts:** correct sprint status, refreshed sprint snapshot, reviewed knowledge candidates, and rendered knowledge base when published.

**Primary references:** `runbooks/sprint-and-knowledge-operations.md`, `.agents/skills/kctl-extract/SKILL.md`

## Done By Change Class

### Docs-only change

Minimum done criteria:
- update the durable doc in the correct tracked location
- update `docs/README.md` when adding a new durable doc category entry that should be discoverable
- run doc-surface verification such as link, grep, or diff checks needed to prove consistency
- do not claim behavior changed unless tests or code changed with it

### Behavior change

Minimum done criteria:
- update or add tests in the same change
- update requirements or product/docs when externally visible behavior or accepted scope changes
- run targeted tests for changed files in-session, foreground, fast-fail: `pytest <files> -x --tb=short`; full suite is a CI gate, not an in-session requirement
- gate `sprintctl` done transitions on targeted test exit code
- keep sprint state current if the work is sprint-scoped

### Architecture change

Minimum done criteria:
- update the relevant architecture or decision docs under `docs/`
- confirm the layer boundaries still hold
- update requirements if architecture changes alter accepted scope or delivery shape
- verify the new boundary through focused tests, contracts, or implementation checks

### CI or release change

Minimum done criteria:
- update workflow, release, or ops docs along with the change
- keep branch, tag, and release behavior aligned with `docs/runbooks/release-governance.md`
- verify the changed local and CI path as far as the environment allows
- run `make verify-fast` before PR or CI-triggering push
- state clearly which checks are blocking and which remain advisory or unrun

### Sprint-state change

Minimum done criteria:
- record live sprint state in `sprintctl` first
- refresh `docs/sprint-snapshots/sprint-current.txt` only after the state change exists in the DB
- keep snapshot updates separate from unrelated feature commits when committed
- add `sprintctl event` or `sprintctl handoff` output when the change materially affects ownership, decisions, blockers, or execution history
- for multi-agent work, keep ownership transfers explicit through matching claim identity or a handoff artifact before another agent resumes implementation

## Multi-Agent Coordination

Use claims and handoff artifacts to coordinate shared sprint work.

For exact CLI steps, use `sprintctl agent-protocol --json`.

Claim before repo edits when:
- the work is already represented as a sprint item and more than one agent or worktree may act on it
- the next task is being selected from live sprint state rather than assigned explicitly by the user
- ownership of the item would otherwise be ambiguous

Required claim identity for multi-agent work when the local workflow supports it:
- ownership proof: `claim_id` plus `claim_token`
- identity metadata: `runtime_session_id`, `instance_id`, actor label, and workspace metadata such as branch, worktree, commit SHA, and PR reference when available

Coordination rules:
- do not infer ownership from sprint docs, plans, or session notes when live `sprintctl` state exists
- do not treat matching actor, workspace token, branch, worktree, or commit SHA by themselves as proof of ownership
- if an exclusive claim already exists and the current session holds its `claim_token` and the identity clearly matches, refresh the heartbeat and continue
- if an exclusive claim already exists and the identity is missing, ambiguous, or points to another live workspace, do not heartbeat it and do not edit repo files until a handoff is produced or a different item is selected
- add `sprintctl event` records when decisions are made or blockers are resolved, not only at close-out
- log reusable workflow corrections and coordination lessons as `decision` or `lesson-learned` events with `--payload` keys `summary`, `detail`, `tags`, and `confidence` at the moment they are discovered
- use `sprintctl claim handoff` when ownership of an active claim moves to another live session
- use `sprintctl handoff --output <path>` when work pauses materially or the next session needs broader machine-readable sprint context
- keep handoff bundles local unless the task explicitly asks for a committed artifact

## Mid-Sprint Breaks and Session Handoffs

Use this practice when pausing mid-sprint — end of session, context crash, or handing to another agent — before all pending items are complete.

### When to write a handoff prompt

Write a handoff prompt file whenever:
- the session is ending with pending items in the current sprint
- a crash or context loss interrupted an active item
- work is being handed to a different agent or worktree

### Where to write it

`.agents/handoffs/<YYYY-MM-DD>-<topic-slug>.md` in the repo root.

This directory is stable, tracked, and the canonical location for human-readable session restart prompts. Use the date and a short topic slug so files are sortable and identifiable.

Example: `.agents/handoffs/2026-04-06-sprint-25-23-resume.md`

### What to include

```
resume

<one-line context: what sprint, what items, what state>

## State
- Which sprint(s) are active and which items are pending vs done
- Any active or recently released claims
- Any uncommitted changes and whether they should be left alone

## Item <id> — <title> (<S/M/L>)
- Files to touch (named)
- What's missing (specific gaps, not vague)
- Any design decisions already made

## Suggested order
<ordered list of items or sub-groups>

<Any agent dispatch notes — dispatch-build / dispatch-review usage>
```

Omit planning that has not yet been done — do not fabricate a plan to fill the template.

### Claim state before pausing

Before closing a session mid-item:
- if the item is incomplete, release the claim with `sprintctl claim release --claim-id <id> --claim-token <token>` so the next session can start cleanly
- if the item is complete but not yet marked done, mark it done first with `sprintctl item done-from-claim`, then commit
- if context was lost before claim state could be confirmed, check `sprintctl claim list --item-id <id>` at the start of the next session; if no claims exist, start a new claim

### Resuming from a handoff prompt

Open the handoff file and paste its contents as the opening message, or say:

> resume — see `.agents/handoffs/<filename>.md`

The next session should run `sprint-resume` first to verify live claim state before touching repo files.

### Relationship to `sprintctl handoff`

`sprintctl handoff --output <path>` produces a machine-readable bundle (JSON) for agent-to-agent ownership transfer. The `.agents/handoffs/` prompt file is the human-readable complement: it captures planning context, item scope, and suggested order that the machine bundle does not carry.

Both can coexist. For solo work or simple session breaks, the prompt file alone is sufficient.

## Session Notes Boundary

Session notes under `docs/sessions/` are local-only artifacts and are gitignored by default.

Use them for:
- local history
- reasoning traces
- rough investigation notes

Do not use them as:
- authoritative process guidance
- the source of truth for active sprint selection
- a substitute for tracked runbooks, skills, requirements, or architecture docs

If a session note captures a rule that should apply again, promote that rule into a tracked runbook, skill, guide, or requirement and then reference the tracked source instead.
