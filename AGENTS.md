# Agent Guidance

## Architecture rules

- Preserve the layer split: `landing` is immutable raw payloads plus validation, `transformation` is reusable normalized models plus SCD handling, and `reporting` is dashboard/API-facing marts.
- App-facing reporting paths must use reporting-layer models; do not add landing-to-dashboard shortcuts.
- Before opening a pull request or pushing a branch that will trigger CI, run `make verify-fast`.
- When changing architecture or stack choices, update the relevant docs under `docs/`.
- When changing or adding requirements, update the relevant file under `requirements/` and keep status and phase fields current.
- Behavior changes must update or add tests in the same change.
- When adding a source connector, define its landing contract, validation checks, and canonical mapping target.
- When adding a dimension, decide whether it needs SCD handling in transformation and a current snapshot in reporting.

Mode guides: `docs/agents/planning.md`, `docs/agents/implementation.md`, `docs/agents/review.md`, `docs/agents/release-ops.md`.
Workflow skills: `.agents/skills/`.
Working practices: `docs/runbooks/project-working-practices.md`.

## Environment setup

### Required environment variables

| Variable | Path | Purpose |
|---|---|---|
| `SPRINTCTL_DB` | `<repo-root>/.sprintctl/sprintctl.db` | Project-scoped sprint state |
| `KCTL_DB` | `<repo-root>/.kctl/kctl.db` | Project-scoped knowledge state |

**Load:** `source .envrc` or `direnv allow` from repo root before using `sprintctl` or `kctl`.

**Validate before use:**
```bash
echo $SPRINTCTL_DB   # must contain the repo path, not ~/
SPRINTCTL_DB=/projects/dev/homelab-analytics/.sprintctl/sprintctl.db sprintctl sprint list
```

Using the home-directory default (`~/`) silently produces stale or wrong sprint state.

### Cluster context

This application is **not yet deployed** to a cluster. Do not run `kubectl` against live clusters for development work. All deployment targets and cluster assumptions are documented in `docs/notes/appservice-cluster-integration-notes.md`.

- Target cluster: `appservice`, path `clusters/main/kubernetes/apps/homelab-analytics/`
- Do not assume kubectl access or cluster state is available in any session.

## Development workflow

- Primary language: **Python**. Testing: `pytest` (`make test` or `pytest -q`).
- Run the full test suite after making changes and report pass/fail count before committing.
- **Never commit with failing tests.**
- Run `make verify-fast` before any PR or CI-triggering push.

## Sprint and knowledge tooling

Sprint state is managed via `sprintctl` and knowledge extraction via `kctl`. Both are installed as user tools (`uv tool`) and scoped to this project via `.envrc` (loaded by direnv).

- Load `.envrc` before using either CLI. Unscoped home-directory DBs are not project state and may drift from the committed snapshot.
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

## Sprint naming convention

Sprint names use **three-word hyphenated codenames**, not sequential letters.

| Correct | Wrong |
|---|---|
| `hearth-lantern-path` | `Sprint R` |
| `iron-grove-atlas` | `Sprint Q` |
| `flint-glass-vow` | `sprint-S` |

**Before registering a new sprint:** run `sprintctl sprint list` to check existing IDs and names. Collisions on name or sequential-letter patterns indicate the wrong convention is being used.

Current active sprints (2026-04-03): `#29 hearth-lantern-path phase-2`, `#25 flint-glass-vow`, `#23 iron-grove-atlas`.

## Database migrations

### Current migration state

| Store | Latest migration | File count |
|---|---|---|
| `migrations/postgres/` | `0007_dim_household_member` | 7 |
| `migrations/duckdb/` | `0008_counterparty_category_id` | 3 (DuckDB-only subset — gaps are intentional) |
| `migrations/sqlite/` | `0005_reference_fact` | 5 |
| `migrations/postgres_run_metadata/` | `0001_run_metadata_initial_schema` | 1 |

### Schema versions

- Dimension contracts: `schema_version = "1.0.0"` (string, in `packages/platform/current_dimension_contracts.py`)
- External registry manifest: `schema_version = 1` (integer, in `packages/shared/external_registry.py`)

### Migration authoring rules

1. **No duplicate columns** — if a column is in `CREATE TABLE`, do not re-add it in `ALTER TABLE` within the same migration.
2. **Update version assertions** — if tests assert a migration count or schema version, update them.
3. **Datetime consistency** — do not mix naive and aware datetimes in comparisons.
4. **DuckDB is a subset** — add a DuckDB migration only when the change affects the DuckDB layer; gaps in numbering are intentional.
