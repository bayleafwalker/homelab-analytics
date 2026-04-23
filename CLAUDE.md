# CLAUDE.md — homelab-analytics

Agent and session guidance for this repository. AGENTS.md is the canonical cross-agent reference; this file adds Claude-specific context and workflow rules.

---

## Tech Stack

- **Primary language:** Python. Use `pytest` for all tests.
- **Documentation:** Markdown.
- **Secondary:** JavaScript (frontend under `apps/web/frontend/`).
- **Build/verify:** `make verify-fast` before any PR or push that triggers CI.
- **Package manager:** `uv` (tools installed via `uv tool`).

---

## Environment Setup

Before interacting with any cluster, sprint tooling, or database tooling, read `AGENTS.md` for workspace instructions including correct cluster context, required environment variables, and naming conventions.

### Required environment variables

| Variable | Value | Purpose |
|---|---|---|
| `SPRINTCTL_DB` | `<repo-root>/.sprintctl/sprintctl.db` | Project-scoped sprint DB |
| `KCTL_DB` | `<repo-root>/.kctl/kctl.db` | Project-scoped knowledge DB |

**Load with:** `source .envrc` or `direnv allow` from the repo root.

**Validation:**
```bash
# Confirm env vars point to the project DB, not the home-directory default
echo $SPRINTCTL_DB   # must contain the repo path, not ~/
SPRINTCTL_DB=/projects/dev/homelab-analytics/.sprintctl/sprintctl.db sprintctl sprint list
```

> Using the home-directory DB (`~/`) will silently produce stale or wrong sprint state. Always verify the path before mutating sprint state.

### Cluster context

This application is **not yet deployed** to a cluster. Do not run `kubectl` against live clusters for development work.

- Future deployment target: `appservice` cluster, path `clusters/main/kubernetes/apps/homelab-analytics/`.
- All cluster deployment guidance is in `docs/notes/appservice-cluster-integration-notes.md`.
- If you need to reference a live cluster for any reason, use the `appservice` context explicitly and confirm with the user first.

---

## Development Workflow

1. **Two-tier testing model:**
   - **In-session (blocking, targeted):** Run only the tests covering changed files: `pytest tests/test_foo.py -x --tb=short`. Run foreground and wait — never background `pytest` for sequential work.
   - **Full suite (CI gate only):** `make test` is a merge gate, not a sprint-item gate. Push the branch; let CI run it.
2. Gate done transitions on targeted test exit code: `pytest <files> -x --tb=short && sprintctl item done-from-claim ...`
3. **Never commit with failing tests.**
4. **Commit after each sprint item completes — not at the end of a session.** One item = one commit. Run targeted tests before each commit.
5. Run `make verify-fast` before opening a PR or pushing a branch that will trigger CI.
6. Behavior changes must include updated or new tests in the same commit.

### Self-healing test loop

If tests fail after a change, diagnose the root cause, fix, and re-run — up to **5 cycles** — before escalating to the user. Only escalate if:
- still failing after 5 attempts, or
- a design decision is required that isn't answerable from code, docs, or prior instructions.

---

## Sprint Management

When creating or registering sprints:

1. Check existing sprint IDs and names first: `SPRINTCTL_DB=... sprintctl sprint list`
2. Use the current **word-triplet codename** convention — do **not** use sequential letters.

**Correct examples:** `hearth-lantern-path`, `iron-grove-atlas`, `flint-glass-vow`, `seam-finish-pass`
**Wrong:** `Sprint R`, `Sprint Q`, `sprint-S`

Current sprint state (as of 2026-04-23): **active** — sprint #61 `guided-land-surface`.
Goal: close the guided-upload → ingest-summary → first-answer loop.
11 items: guided-onboarding (5 verify/close), first-answer (3 verify/close),
tests (1 integration test), bugs (2 blocking fixes). 0/11 done.

Sprint workflow:
- Use `sprint-packet` to register scope, `sprint-resume` to pick up existing work, `sprint-snapshot` to refresh the shared artifact.
- Record sprint state in `sprintctl` first; refresh `docs/sprint-snapshots/sprint-current.txt` afterward.

---

## Database & Migrations

### Current migration state (2026-04-03)

| Store | Latest migration | Count |
|---|---|---|
| `migrations/postgres/` | `0007_dim_household_member` | 7 |
| `migrations/duckdb/` | `0008_counterparty_category_id` | 3 (gaps: DuckDB-only subset) |
| `migrations/sqlite/` | `0005_reference_fact` | 5 |
| `migrations/postgres_run_metadata/` | `0001_run_metadata_initial_schema` | 1 |

### Schema versions

- Dimension contracts (`packages/platform/current_dimension_contracts.py`): `schema_version = "1.0.0"`
- External registry manifest (`packages/shared/external_registry.py`): `schema_version = 1` (integer)

### Migration authoring rules

When writing database migrations, ensure:

1. **No duplicate column additions** — if a column is defined in `CREATE TABLE`, do not add it again in a later `ALTER TABLE` in the same migration.
2. **Update schema version assertions** — if any test or code asserts a specific migration count or schema version, update those assertions.
3. **Datetime consistency** — all datetime comparisons must handle naive vs. aware datetimes consistently; do not mix them.
4. **DuckDB migrations are a subset** — not every postgres migration applies to DuckDB. Add DuckDB migrations only when the schema change affects the DuckDB layer.

---

## Architecture

Layer split (must be preserved):

- `landing/` — immutable raw payloads + validation only
- `transformation/` — normalized models + SCD handling
- `reporting/` — dashboard/API-facing marts

App-facing reporting paths must use the reporting layer; do not create landing-to-dashboard shortcuts.

---

## Key references

- Working practices: `docs/runbooks/project-working-practices.md`
- Sprint + knowledge ops: `docs/runbooks/sprint-and-knowledge-operations.md`
- Architecture: `docs/architecture/data-platform-architecture.md`
- Cluster deployment: `docs/notes/appservice-cluster-integration-notes.md`
- Agent mode guides: `docs/agents/` (planning, implementation, review, release-ops)
- Workflow skills: `.agents/skills/`
