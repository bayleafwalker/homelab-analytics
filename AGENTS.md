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
- Use `kctl extract` after a sprint closes to surface decisions and lessons into the knowledge pipeline, then `kctl review approve` or `kctl review reject` per candidate.
- Use the `sprint-snapshot` skill to render and commit a snapshot. Use the `kctl-extract` skill at sprint close.
