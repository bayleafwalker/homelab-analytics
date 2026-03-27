# Agent Guidance

- Preserve the layer split: `landing` is immutable raw payloads plus validation, `transformation` is reusable normalized models plus SCD handling, and `reporting` is dashboard/API-facing marts.
- Before opening a pull request or pushing a branch that will trigger CI, run `make verify-fast`.
- When changing architecture or stack choices, update the relevant docs under `docs/`.
- When changing or adding requirements, update the relevant file under `requirements/` and keep status and phase fields current.
- Behavior changes must update or add tests in the same change.
- When adding a source connector, define its landing contract, validation checks, and canonical mapping target.
- When adding a dimension, decide whether it needs SCD handling in transformation and a current snapshot in reporting.
- App-facing reporting paths must use reporting-layer models when configured; do not add new landing-to-dashboard shortcuts.

Mode guides: `docs/agents/planning.md`, `docs/agents/implementation.md`, `docs/agents/review.md`, `docs/agents/release-ops.md`.
Workflow skills: `.agents/skills/`.

## Sprint and knowledge tooling

Sprint state is managed via `sprintctl` and knowledge extraction via `kctl`. Both are installed as user tools (`uv tool`) and scoped to this project via `.envrc` (loaded by direnv).

- `SPRINTCTL_DB` and `KCTL_DB` point to `.sprintctl/sprintctl.db` and `.kctl/kctl.db` respectively — both gitignored.
- The committed source of truth for sprint state is `docs/sprint-snapshots/sprint-current.txt` (output of `sprintctl render`).
- Use `sprintctl item status --id <n> --status <active|done|blocked>` to advance work items. Status transitions are enforced.
- Use `sprintctl event add --sprint-id <id> --type <type> --actor <name>` to log decisions, blockers, and notable events during implementation.
- Use `sprintctl maintain check [--sprint-id N]` for a health report (stale items, track health, overrun risk).
- Use `sprintctl maintain sweep [--sprint-id N] [--auto-close]` to mark stale active items as blocked.
- Use `sprintctl maintain carryover --from-sprint N --to-sprint M` to move unfinished items at sprint close.
- Use `kctl extract` after a sprint closes to surface decisions and lessons into the knowledge pipeline, then `kctl review approve` or `kctl review reject` per candidate.
- Use the `sprint-snapshot` skill to render and commit a snapshot. Use the `kctl-extract` skill at sprint close.

### DB portability and recovery

Both `.sprintctl/sprintctl.db` and `.kctl/kctl.db` are machine-local and gitignored. If the DB is lost or needs to be seeded on a new machine:
- Use `docs/sprint-snapshots/sprint-current.txt` (the committed `sprintctl render` output) as the source of truth for current sprint state.
- Recreate sprints and items manually from that snapshot using `sprintctl sprint create` and `sprintctl item add`.
- Mark all completed/historical sprints closed immediately via `sprintctl sprint status --id <n> --status closed`.
- There is no automated import path; the snapshot is the rehydration baseline.

### sweep warning

`sprintctl maintain sweep` marks stale active items as `blocked`. **Do not use `--auto-close` by default** — once blocked, items cannot be unblocked and must be recreated. Run sweep without `--auto-close` to get a report of stale items, then decide manually whether to block or advance them.
