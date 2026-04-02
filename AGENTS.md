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
Working practices: `docs/runbooks/project-working-practices.md`.

## Sprint and knowledge tooling

Sprint state is managed via `sprintctl` and knowledge extraction via `kctl`. Both are installed as user tools (`uv tool`) and scoped to this project via `.envrc` (loaded by direnv).

- Load `.envrc` before using either CLI (`direnv allow`, `source .envrc`, or export the variables manually). Unscoped home-directory DBs are not project state and may drift from the committed snapshot.
- For repo-wide startup order, source-of-truth precedence, working loops, change-class done criteria, and session-note boundaries, use `docs/runbooks/project-working-practices.md`.
- `SPRINTCTL_DB` and `KCTL_DB` point to `.sprintctl/sprintctl.db` and `.kctl/kctl.db` respectively — both gitignored.
- For sprint-scoped work, consult live `sprintctl` state before docs when choosing or resuming work.
- For existing sprint items, inspect item state and claims, then claim or activate the item before editing repo files.
- Use `sprintctl agent-protocol --json` as the exact claim lifecycle reference. Ownership proof is `claim_id` plus `claim_token`; attach `runtime_session_id` and `instance_id`; treat workspace metadata as advisory only. Do not heartbeat or reuse an existing exclusive claim unless that identity clearly matches the current session; otherwise require a handoff or choose different work.
- Record material sprint state in `sprintctl` first and refresh `docs/sprint-snapshots/sprint-current.txt` afterward.
- Log reusable process corrections, coordination decisions, and lessons as structured `sprintctl` events when they happen so `kctl` can extract them at sprint close.
- Repo-level operating model: `docs/runbooks/sprint-and-knowledge-operations.md`.
- The committed sprint artifact is `docs/sprint-snapshots/sprint-current.txt`.
- The committed knowledge artifact is `docs/knowledge/knowledge-base.md`.
- Use `sprint-packet` to register accepted scope, `sprint-resume` to pick up existing scoped work safely, `sprint-snapshot` to refresh shared sprint state, and `kctl-extract` at sprint close.
