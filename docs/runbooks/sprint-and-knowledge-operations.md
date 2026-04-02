# Sprint And Knowledge Operations

**Classification:** CROSS-CUTTING

## Purpose

This runbook covers the repo's `sprintctl` and `kctl` operating model.

Use `sprintctl` for live sprint execution state. Use `kctl` for extracting, reviewing, publishing, and rendering durable knowledge from sprint events.

For repo-wide startup order, source-of-truth precedence, done criteria, and session-note policy, use `runbooks/project-working-practices.md`.

## Shared State

### Local only

These stay machine-local and gitignored:
- `.sprintctl/sprintctl.db`
- `.kctl/kctl.db`
- `sprint-*.json`
- `handoff-*.json`

### Committed

These are the shared repo artifacts:
- `docs/sprint-snapshots/sprint-current.txt`
- `docs/knowledge/knowledge-base.md`

Treat the committed files as the shared repo view. The SQLite databases are local execution state.

## Daily Use

### 1. Start from the project-scoped DB

- load `.envrc` before using either CLI
- confirm `SPRINTCTL_DB` and `KCTL_DB` point at the repo-local DBs, not home-directory defaults

### 2. Register or resume work

- use `sprint-packet` when accepted scope is not yet represented in `sprintctl`
- use `sprint-resume` when the work item already exists
- choose or resume sprint work from live `sprintctl` state first, then use docs as implementation context

### 3. Follow the claim lifecycle

- `sprintctl agent-protocol --json` is the authoritative claim-lifecycle reference
- the normal flow is `claim create` -> `claim heartbeat` -> `item status` -> `claim handoff` or `claim release`
- ownership proof is `claim_id` plus `claim_token`
- attach `runtime_session_id` and `instance_id` on claims; for Codex, let `CODEX_THREAD_ID` populate the runtime session id when available or set `SPRINTCTL_RUNTIME_SESSION_ID` explicitly, and keep `SPRINTCTL_INSTANCE_ID` stable for the live process
- attach branch, worktree, commit SHA, and PR reference when available, but treat them as advisory metadata
- if an active exclusive claim does not clearly belong to the current session, stop and resolve a handoff or choose different work before editing repo files

### 4. Capture events while work is happening

- log `decision`, `lesson-learned`, `blocker-resolved`, `pattern-noted`, or `risk-accepted` events when the fact is discovered, not only at sprint close
- use `--payload` JSON with `summary`, `detail`, `tags`, and `confidence` so extraction yields useful candidates instead of noise

### 5. Refresh the shared sprint snapshot after live changes

- run `sprintctl render --output docs/sprint-snapshots/sprint-current.txt`
- do this only after the DB state is already correct
- keep snapshot-only commits separate from unrelated feature work

## Sprint Close

- run `kctl preflight` or `sprintctl maintain check --sprint-id <id>`
- move unfinished work with `sprintctl maintain carryover --from-sprint <id> --to-sprint <next-id>`
- close the sprint with `sprintctl sprint status --id <id> --status closed`
- run `kctl extract --sprint-id <id>` for the default knowledge event set: `decision`, `blocker-resolved`, `pattern-noted`, `risk-accepted`, `lesson-learned`
- if coordination history matters too, extend extraction with `--event-types decision,blocker-resolved,pattern-noted,risk-accepted,lesson-learned,claim-handoff,claim-ownership-corrected,claim-ambiguity-detected,coordination-failure`
- review candidates with `kctl review list`, `kctl review show`, `kctl review approve`, and `kctl review reject`
- publish intentionally with `kctl publish ...` and render the committed artifact with `kctl render --output docs/knowledge/knowledge-base.md`

## Useful Structured Surfaces

Prefer JSON output when another agent or script needs machine-readable state.

- `sprintctl sprint show --detail --json`
- `sprintctl item list --sprint-id <id> --json`
- `sprintctl item show --id <item-id> --json`
- `sprintctl claim list --item-id <item-id> --json`
- `sprintctl claim list-sprint --sprint-id <id> --json`
- `sprintctl claim resume --instance-id <id> --json`
- `sprintctl usage --context --json`
- `sprintctl agent-protocol --json`
- `sprintctl handoff --format json --output <path>`
- `kctl review list --json`
- `kctl status --json`

## Recovery

If a local DB is lost:
- treat `docs/sprint-snapshots/sprint-current.txt` as the shared view of the current sprint
- recreate the relevant sprint and items manually in `sprintctl`
- use local export and handoff bundles only as advisory inputs, not as canonical repo state

## Skills Boundary

Use the runbook for the repo-wide operating model.

Use skills for task-specific execution:
- `sprint-packet` for new accepted scope that is not yet registered
- `sprint-resume` for resuming an existing sprint item safely
- `sprint-snapshot` for refreshing `docs/sprint-snapshots/sprint-current.txt`
- `kctl-extract` for sprint-close extraction, review, and optional publication
