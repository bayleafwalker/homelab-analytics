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
- use claims when multiple agents may touch the same sprint DB
- include workspace metadata on claims when available: branch, worktree, commit SHA, PR reference
- add `sprintctl event` records when decisions, resolved blockers, or lessons happen

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
- `sprint-snapshot` for refreshing the committed sprint snapshot after live sprint state changes
- `kctl-extract` for sprint-close extraction and knowledge publication
