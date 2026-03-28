# Sprint And Knowledge Operations

## Purpose

This runbook defines how the repository uses `sprintctl` for live sprint state and `kctl` for durable knowledge capture.

The goal is to keep the operational database local, the shared repo artifacts explicit, and the workflow consistent across planning, implementation, handoff, and sprint close.

For repo-wide startup order, source-of-truth precedence, done criteria, and session-note policy, use `runbooks/project-working-practices.md`.

## System Roles

### `sprintctl`

`sprintctl` is the live operational control plane for sprint execution.

Use it to:
- register sprints and work items
- update item status during execution
- claim work in parallel agent workflows
- log decisions, blockers, and lessons as structured events
- render the committed sprint snapshot
- produce local export or handoff bundles when needed

### `kctl`

`kctl` is the knowledge pipeline layered on top of `sprintctl` events.

Use it to:
- preflight sprint health before extraction
- extract knowledge candidates from sprint events
- review and triage those candidates
- publish approved knowledge entries
- render the committed knowledge base

## Repo Artifacts

### Local-only state

These stay machine-local and gitignored:
- `.sprintctl/sprintctl.db`
- `.kctl/kctl.db`
- `sprint-*.json`
- `handoff-*.json`

### Committed shared artifacts

These are the repo-facing outputs:
- `docs/sprint-snapshots/sprint-current.txt`
- `docs/knowledge/knowledge-base.md`

Treat these files as the canonical shared view. Do not treat the SQLite databases as repo state.

## Operating Model

### 1. Scope accepted work

When scope is accepted and needs execution tracking:
- follow the new scope registration loop in `runbooks/project-working-practices.md`
- use the `sprint-packet` skill
- create or update the sprint in `sprintctl`
- register work items by meaningful repo slices or stage tracks

### 2. Execute work

During implementation:
- follow the resume existing sprint item and implementation loops in `runbooks/project-working-practices.md`
- load `.envrc` before using either CLI
- move items through `pending`, `active`, `done`, or `blocked`
- use claims when multiple agents may touch the same sprint DB, with a strong live identity per agent or worktree: `runtime_session_id`, `instance_id`, and `claim_token`
- for Codex, prefer `CODEX_THREAD_ID` as `runtime_session_id` when it is available and mint a separate `instance_id` once per live client or process start
- include workspace metadata on claims when available: branch, worktree, commit SHA, PR reference
- treat workspace metadata as advisory context, not as claim ownership proof
- if an exclusive claim already exists and its identity does not clearly match the current live claim identity, do not heartbeat or reuse it; hand off the work or choose a different item first
- use `sprintctl claim handoff` when an active claim's ownership itself changes; use `sprintctl handoff` only for broader sprint context because it does not move `claim_token`
- add `sprintctl event` records when decisions, resolved blockers, or lessons happen, including reusable process corrections and coordination rules discovered during the sprint

For kctl-ready event capture during execution:
- use `decision` for durable design or workflow choices that should survive the sprint
- use `lesson-learned` for process corrections, coordination failures, or heuristics you want future agents to avoid repeating
- use `blocker-resolved`, `pattern-noted`, or `risk-accepted` when they better fit the event
- treat system-emitted `claim-handoff`, `claim-ownership-corrected`, `claim-ambiguity-detected`, and `coordination-failure` events as extractable coordination history when ownership behavior itself matters later
- include `summary`, `detail`, `tags`, and `confidence` so sprint-close extraction yields useful candidates instead of noise

### 3. Keep shared sprint state current

When sprint state materially changes:
- refresh the snapshot only after the live state change exists in `sprintctl`
- run `sprintctl render`
- write the output to `docs/sprint-snapshots/sprint-current.txt`
- keep snapshot commits separate from unrelated feature work when committed

### 4. Close the sprint cleanly

At sprint close:
- follow the sprint close loop in `runbooks/project-working-practices.md`
- run `sprintctl maintain check`
- use `carryover` for unfinished items that belong in the next sprint
- close the sprint when the execution state is correct
- run `kctl extract`
- review candidates to approved or rejected

### 5. Publish durable knowledge intentionally

If the task includes knowledge publication:
- use `kctl publish` for approved entries that belong in repo memory
- render to `docs/knowledge/knowledge-base.md`
- keep knowledge-base updates separate from unrelated feature work

## Structured Output Guidance

Prefer JSON output when another agent or script needs machine-readable state.

Recommended structured-state commands:
- `sprintctl item list --json`
- `sprintctl item show --json`
- `sprintctl claim list-sprint --json`
- `sprintctl claim resume --json`
- `sprintctl handoff --output <path>`
- `kctl review list --json`
- `kctl status --json`

Do not rely on `sprintctl sprint show --detail --json` until the current upstream crash is fixed.

## Recovery And Portability

If a local DB is lost:
- treat `docs/sprint-snapshots/sprint-current.txt` as the source of truth for current sprint state
- recreate the relevant sprint and items manually in `sprintctl`
- use local `sprintctl export` files only as advisory convenience inputs, not as canonical repo state

## Skills Boundary

Use the runbook for repo-wide operating rules.

Use skills for task-specific execution:
- `sprint-packet` for turning accepted but not-yet-registered scope into tracked sprint work
- `sprint-resume` for safely resuming an already-registered sprint item, including claim identity checks and handoff behavior
- `sprint-snapshot` for refreshing the committed sprint snapshot after live sprint state changes
- `kctl-extract` for sprint-close extraction and knowledge publication
