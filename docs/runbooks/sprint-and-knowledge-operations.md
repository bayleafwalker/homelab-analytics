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
- `.sprintctl/claims/claim-<item_id>.token`
- `.kctl/kctl.db`
- `sprint-*.json`
- `handoff-*.json`
- `handoff-*.txt`

### Committed

These are the shared repo artifacts:
- `docs/sprint-snapshots/sprint-current.txt`
- `docs/knowledge/knowledge-base.md`

Curated session-derived training docs under `docs/training/` are also committed shared artifacts, but they are authored manually rather than rendered from `sprintctl` or `kctl`.

Treat the committed files as the shared repo view. The SQLite databases are local execution state.
This repo does not use a separate committed coordination artifact such as `docs/knowledge/knowledge-base-ops.md`.
When approved coordination candidates are intentionally promoted into durable repo knowledge, publish and render them into `docs/knowledge/knowledge-base.md`.
Leave ad hoc renders or experimental alternate outputs local-only unless the docs are updated first.

## Daily Use

### 1. Start from the project-scoped DB

- load `.envrc` before using either CLI
- confirm `SPRINTCTL_DB` and `KCTL_DB` point at the repo-local DBs, not home-directory defaults

### Tool refresh from source

`sprintctl` and `kctl` are private source-installed user tools. They are not installed from PyPI.

When the command is missing, or when local source changes need to be reflected in the executable, reinstall from the source checkouts:

```bash
uv tool install --force --reinstall /projects/dev/sprintctl --python python3
uv tool install --force --reinstall /projects/dev/kctl --python python3
```

Use `/workspace/dev/...` only on environments where that is the actual checkout root. The commands install into the user tool directory, normally `~/.local/bin`, and do not alter `.sprintctl/sprintctl.db` or `.kctl/kctl.db`.

After reinstalling, verify the active command and scoped state:

```bash
source .envrc
command -v sprintctl
command -v kctl
sprintctl sprint list
kctl status --kind all
```

### 2. Register or resume work

- use `sprint-packet` when accepted scope is not yet represented in `sprintctl`
- use `sprint-resume` when the work item already exists
- choose or resume sprint work from live `sprintctl` state first, then use docs as implementation context

### Repo-local wrapper targets

The repo now ships a small wrapper layer for the canonical sprint and knowledge flows.
These targets source `.envrc`, use the repo-local DB paths, and keep repeated command shapes out of ad hoc shell history.

- `make sprint-resume [ITEM=<item-id>]` wraps `sprintctl claim resume --json` using `SPRINTCTL_INSTANCE_ID` when available, otherwise `SPRINTCTL_RUNTIME_SESSION_ID` or `CODEX_THREAD_ID`
- `make claim-recover ITEM=<item-id>` wraps `sprintctl claim recover --item-id <item-id> --json`
- `make claim-heartbeat CLAIM_ID=<claim-id> CLAIM_TOKEN=<claim-token> [ACTOR=<actor>] [CLAIM_TTL=300]` wraps the long-item heartbeat flow
- `make item-verify-auth PY_FILES="path1 path2" TESTS="tests/test_a.py tests/test_b.py"` runs item-scoped `ruff`, `mypy`, targeted `pytest`, and `tests/test_architecture_contract.py`
- `make snapshot-refresh [SPRINT_ID=<sprint-id>]` renders `docs/sprint-snapshots/sprint-current.txt` for the active sprint or the explicit sprint id
- `make knowledge-publish CANDIDATE=<id> CATEGORY=<decision|pattern|lesson|risk|reference> BODY="..." [TITLE="..."] [TAGS='[\"workflow\"]'] [COORDINATION=1]` publishes an approved entry and re-renders `docs/knowledge/knowledge-base.md`

Use the raw `sprintctl` and `kctl` commands when you need a flow the wrappers do not cover.

### 3. Follow the claim lifecycle

- `sprintctl agent-protocol --json` is the authoritative claim-lifecycle reference
- prefer `sprintctl claim start --item-id <id> ...` to claim + set `active` in one step
- for sessions that need explicit control, use `claim create` then `item status --status active`
- during execution, refresh ownership with `claim heartbeat`
- when finishing an item, prefer `item done-from-claim` (or `item status --status done` + `claim release` when needed)
- hand off with `claim handoff` or release with `claim release` before shutdown
- ownership proof is `claim_id` plus `claim_token`
- treat the claim token as a secret and persist it immediately after `claim start` to `.sprintctl/claims/claim-<item_id>.token`
- keep the token in session memory during normal execution; treat the file as crash recovery only
- when reattaching after context loss, read `.sprintctl/claims/claim-<item_id>.token` before deciding whether to resume the live claim
- remove `.sprintctl/claims/claim-<item_id>.token` after successful `claim release` or `item done-from-claim`
- attach `runtime_session_id` and `instance_id` on claims; for Codex, let `CODEX_THREAD_ID` populate the runtime session id when available or set `SPRINTCTL_RUNTIME_SESSION_ID` explicitly, and keep `SPRINTCTL_INSTANCE_ID` stable for the live process
- attach branch, worktree, commit SHA, and PR reference when available, but treat them as advisory metadata
- if an active exclusive claim does not clearly belong to the current session, stop and resolve a handoff or choose different work before editing repo files

### 4. Capture events while work is happening

- log `decision`, `lesson-learned`, `blocker-resolved`, `pattern-noted`, or `risk-accepted` events when the fact is discovered, not only at sprint close
- use `--payload` JSON with `summary`, `detail`, `tags`, and `confidence` so extraction yields useful candidates instead of noise

### 5. Refresh the shared sprint snapshot after live changes

- run `sprintctl render --output docs/sprint-snapshots/sprint-current.txt`
- do this only after the DB state is already correct
- render when the workflow needs a new shared artifact now or a natural batch boundary has been reached; do not treat every item close as a mandatory snapshot commit
- keep snapshot-only commits separate from unrelated feature work

## Sprint Close

- run `kctl preflight --sprint-id <id>` or `sprintctl maintain check --sprint-id <id>`
- run `pytest tests/test_architecture_contract.py -x --tb=short` as the sprint-close fast gate
- move unfinished work with `sprintctl maintain carryover --from-sprint <id> --to-sprint <next-id>`
- close the sprint with `sprintctl sprint status --id <id> --status closed`
- treat the full suite as an ad-hoc, operator-initiated task rather than a blocking sprint-close requirement
- run `kctl extract --sprint-id <id>` (it runs preflight unless `--no-preflight` is set)
- use explicit `--event-types ...` when you need deterministic filtering instead of the default event set
- review candidates with `kctl review list`, `kctl review show`, `kctl review approve`, and `kctl review reject` (use `--kind all` when coordination stream candidates matter)
- publish intentionally with `kctl publish ...`; use `kctl publish --coordination ...` when an approved coordination candidate should become durable workflow knowledge, then render the committed artifact with `kctl render --output docs/knowledge/knowledge-base.md`
- do not create or commit a separate `docs/knowledge/knowledge-base-ops.md` unless the shared-artifact policy above is changed first

## Useful Structured Surfaces

Prefer JSON output when another agent or script needs machine-readable state.

- `sprintctl sprint show --detail --json`
- `sprintctl item list --sprint-id <id> --json`
- `sprintctl item show --id <item-id> --json`
- `sprintctl claim list --item-id <item-id> --json`
- `sprintctl claim list-sprint --sprint-id <id> --json`
- `sprintctl claim resume --instance-id <id> --json`
- `sprintctl claim start --item-id <item-id> --actor <name> --json`
- `sprintctl item done-from-claim --id <item-id> --claim-id <claim-id> --claim-token <claim-token> --json`
- `sprintctl usage --context --json`
- `sprintctl agent-protocol --json`
- `sprintctl handoff --format json --output <path>`
- `kctl preflight --sprint-id <id> --json`
- `kctl review list --json`
- `kctl review show --id <candidate-id> --json`
- `kctl status --kind all --json`

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
- `workflow-artifact-capture` for turning `.agents/sessions/` source notes into curated committed training artifacts when the lasting value is narrative workflow guidance rather than only structured knowledge
