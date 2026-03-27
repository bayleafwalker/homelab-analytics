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

- Load `.envrc` before using either CLI (`direnv allow`, `source .envrc`, or export the variables manually). Unscoped home-directory DBs are not project state and may drift from the committed snapshot.
- `SPRINTCTL_DB` and `KCTL_DB` point to `.sprintctl/sprintctl.db` and `.kctl/kctl.db` respectively — both gitignored.
- The committed source of truth for sprint state is `docs/sprint-snapshots/sprint-current.txt` (output of `sprintctl render`).
- Use `sprintctl sprint create ... --kind <active_sprint|backlog|archive>` to separate active delivery from parked backlog or archive records when needed.
- Use `sprintctl item status --id <n> --status <active|done|blocked>` to advance work items. Status transitions are enforced.
- Use `sprintctl claim create|heartbeat|release` when concurrent agents are working from the same sprint DB so ownership is explicit and collisions are visible.
- Use `sprintctl event add --sprint-id <id> --type <type> --actor <name>` to log decisions, blockers, and notable events during implementation.
- Use `sprintctl maintain check [--sprint-id N]` for a health report (stale items, track health, overrun risk).
- Use `sprintctl maintain sweep [--sprint-id N] [--auto-close]` to mark stale active items as blocked.
- Use `sprintctl maintain carryover --from-sprint N --to-sprint M` to move unfinished items at sprint close.
- Use `sprintctl handoff --sprint-id <id> --output <path>` when a task explicitly needs a machine-readable sprint handoff bundle. Keep handoff JSON uncommitted unless a repo path is later standardized for it.
- Use `sprintctl export --sprint-id <id>` before risky local DB surgery or machine handoff when you want a portable local backup. Keep exports uncommitted; the snapshot remains the shared repo artifact.
- Use `sprintctl import --file <path>` only for local recovery or transfer. Re-render the snapshot immediately after import if the active sprint changed.
- Use `kctl preflight` before sprint close or knowledge extraction to surface stale-item or health warnings early.
- Use `kctl extract` after a sprint closes to surface decisions and lessons into the knowledge pipeline, then `kctl review approve` or `kctl review reject` per candidate.
- Use `kctl review list --json` and `kctl status --json` when an agent or script needs structured pipeline state instead of human-readable console output.
- Use `kctl status` to confirm whether candidates are still awaiting review or already approved/published.
- The canonical committed knowledge render path is `docs/knowledge/knowledge-base.md`. When a task explicitly includes knowledge publication, use `kctl render --output docs/knowledge/knowledge-base.md` and keep that update separate from unrelated feature work.
- Use the `sprint-snapshot` skill to render and commit a snapshot. Use the `kctl-extract` skill at sprint close.

### DB portability and recovery

Both `.sprintctl/sprintctl.db` and `.kctl/kctl.db` are machine-local and gitignored. If the DB is lost or needs to be seeded on a new machine:
- Use `docs/sprint-snapshots/sprint-current.txt` (the committed `sprintctl render` output) as the source of truth for current sprint state.
- If available, use a recent uncommitted `sprintctl export` JSON as a convenience input for local rehydration, but treat it as advisory rather than canonical.
- Recreate sprints and items manually from that snapshot using `sprintctl sprint create` and `sprintctl item add`.
- Mark all completed/historical sprints closed immediately via `sprintctl sprint status --id <n> --status closed`.
- There is no automated import path; the snapshot is the rehydration baseline.

### sweep warning

`sprintctl maintain sweep` marks stale active items as `blocked`. **Do not use `--auto-close` by default** — once blocked, items cannot be unblocked and must be recreated. Run sweep without `--auto-close` to get a report of stale items, then decide manually whether to block or advance them.

`kctl preflight` can exit non-zero when it finds stale work or sprint-health warnings. Treat that as an advisory operational signal to resolve, not as proof that the sprint DB is corrupted.
