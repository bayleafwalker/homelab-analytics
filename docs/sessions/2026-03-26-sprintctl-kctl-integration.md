# Session: sprintctl + kctl integration
**Date:** 2026-03-26
**Commits:** `33450a5`, `d6e3352`

---

## Requests

**Request 1:**
> Take https://github.com/bayleafwalker/sprintctl and https://github.com/bayleafwalker/kctl in use for the project. Consider migration of sprint docs to this format, additions to gitignore where needed, changes to agents files and local skills to support using this tooling.

**Request 2** (after sprintctl Phase 2 shipped):
> Commands now available: `sprintctl sprint status`, `sprintctl maintain check/sweep/carryover`. Update sprintctl.

**Request 3:**
> Create an output of this session documenting: requested actions, what you considered, steps taken, and outcomes.

**Request 4** (follow-up updates):
> Update the tools again, check for any needed changes to align with new tooling, and define a canonical committed `kctl` render path.

**Request 5** (follow-up refresh):
> Update sprintctl and kctl again, then check for any repo changes needed to align with the new tooling.

**Request 6** (repo refactor):
> Refactor the guidance and consider the high-level utilization of sprintctl and kctl in the repo.

---

## Request 1 — Integrate sprintctl and kctl

### Considered

- Fetched both repos to understand what they are before touching anything. Key findings:
  - **sprintctl** is a SQLite-backed CLI for agent-driven sprint state. It enforces status transitions, records structured events, and renders plain-text sprint docs. It is not a project management tool — it replaces drifting markdown files with a schema-backed source of truth.
  - **kctl** is a companion tool that reads sprintctl's event table (read-only) and extracts durable knowledge (decisions, patterns, resolved blockers) into a review pipeline before sprints go stale.
  - Both tools are installed as user-level tools (pipx / uv tool), not project dependencies.
  - Per-project scoping uses direnv: `SPRINTCTL_DB=$PWD/.sprintctl/sprintctl.db`, `KCTL_DB=$PWD/.kctl/kctl.db`.
  - The committed artifact is `sprintctl render` output — not the SQLite DB.

- Reviewed the existing project state: `docs/sprints/TRACKER.md` holds the full sprint history and backlog. It is gitignored (local planning only). The `.agents/skills/` directory has four existing skills. `AGENTS.md` has agent guidance.

- Decided the migration approach:
  - TRACKER.md stays as-is (gitignored, human-readable); sprintctl becomes the machine-readable counterpart.
  - Historical sprints go into sprintctl as a single closed sprint (sprint #1) with all completed items marked `done`.
  - The active backlog becomes sprint #2 (Sprint J — HA Phase 6) with all backlog items as `pending` items, organised by stage track.
  - The committed snapshot (`docs/sprint-snapshots/sprint-current.txt`) replaces the role that a committed markdown tracker would play.

### Build failures encountered

**Failure 1:** `pipx` not available in the environment. `uv tool` is the equivalent — used that instead.

**Failure 2:** sprintctl's `pyproject.toml` used `build-backend = "setuptools.backends.legacy:build"` but did not declare `setuptools` in `build-system.requires`. Build failed with `ModuleNotFoundError: No module named 'setuptools.backends'`. Reported to user; fixed in sprintctl repo.

**Failure 3:** After the first fix, setuptools auto-discovery failed because the repo root contains a `sessions/` directory alongside the `sprintctl/` package, causing `Multiple top-level packages discovered in a flat-layout`. Reported to user; fixed in sprintctl repo (added `[tool.setuptools] packages = ["sprintctl"]`).

### Steps taken

1. Fetched both repos via subagent (README, key source files, schemas).
2. Attempted install via `uv tool install` — hit two upstream build issues, both fixed in sprintctl.
3. Installed both tools successfully: `sprintctl==0.1.0`, `kctl==0.1.0`.
4. Added `.sprintctl/` and `.kctl/` to `.gitignore`.
5. Created `.envrc` with `SPRINTCTL_DB` and `KCTL_DB` scoped to `$PWD`.
6. Initialized sprintctl DB:
   - Sprint #1: all 23 completed sprints from TRACKER.md added as `done` items across stage tracks (`stage-0` through `stage-9`).
   - Sprint #2 "Sprint J — HA Phase 6: approval-gated device control" (2026-03-26 to 2026-04-09): 18 backlog items as `pending` across stage-1, stage-3, stage-4, stage-5, stage-6, stage-9.
   - Note: `sprintctl sprint status` did not exist in Phase 1 CLI — sprint #1 could not be closed yet.
7. Wrote committed snapshot: `sprintctl render --sprint-id 2 > docs/sprint-snapshots/sprint-current.txt`.
8. Updated `AGENTS.md` with sprintctl/kctl usage conventions and skill references.
9. Updated `.agents/skills/sprint-packet/SKILL.md`: added step 6 to register sprint + items in sprintctl after packet is agreed.
10. Created `.agents/skills/sprint-snapshot/SKILL.md`: render + commit sprint state as a standalone `chore:` commit.
11. Created `.agents/skills/kctl-extract/SKILL.md`: sprint-close knowledge extraction and review workflow.
12. Updated `.agents/skills/README.md` with new skill entries.
13. Committed (`33450a5`) and pushed.

### Outputs

| Output | Location |
|--------|----------|
| `.gitignore` additions | `.sprintctl/`, `.kctl/` |
| `.envrc` | `$PWD/.sprintctl/sprintctl.db`, `$PWD/.kctl/kctl.db` |
| sprintctl DB — sprint #1 | 23 items, all `done`, sprint `active` (close pending Phase 2) |
| sprintctl DB — sprint #2 | 18 items, all `pending`, sprint `active` |
| Committed sprint snapshot | `docs/sprint-snapshots/sprint-current.txt` |
| AGENTS.md | Added sprintctl/kctl section |
| Updated skill | `.agents/skills/sprint-packet/SKILL.md` |
| New skill | `.agents/skills/sprint-snapshot/SKILL.md` |
| New skill | `.agents/skills/kctl-extract/SKILL.md` |
| Updated skill index | `.agents/skills/README.md` |

---

## Request 2 — Upgrade sprintctl, apply new commands

### Considered

- Phase 2 of sprintctl added `sprint status`, `maintain check`, `maintain sweep`, and `maintain carryover`.
- Sprint #1 needed to be closed now that `sprint status` is available.
- `maintain check` and `maintain sweep` are operational commands agents should know about — added to AGENTS.md.
- `maintain carryover` is relevant at sprint close — already covered by the kctl-extract skill context; added to AGENTS.md for completeness.

### Steps taken

1. `uv tool upgrade sprintctl` — upgraded from `2f5b1b9` to `6a8f7ef`.
2. `sprintctl sprint status --id 1 --status closed` — historical sprint closed (`active → closed`).
3. `sprintctl maintain check --sprint-id 2` — confirmed sprint #2 health: 13 days remaining, 18 pending items, 0 active, 0 stale.
4. Added `maintain check/sweep/carryover` references to AGENTS.md.
5. Refreshed `docs/sprint-snapshots/sprint-current.txt`.
6. Committed (`d6e3352`) and pushed.

### Outputs

| Output | Detail |
|--------|--------|
| sprintctl upgraded | `2f5b1b9` → `6a8f7ef` |
| Sprint #1 closed | `active → closed` via `sprint status` |
| AGENTS.md | `maintain` command references added |
| Sprint snapshot | Refreshed |

---

## State at session end

- `sprintctl` and `kctl` installed and operational.
- Sprint #1 (history) closed. Sprint #2 (Sprint J — HA Phase 6) active with 18 pending backlog items.
- `.envrc` ready for direnv; `SPRINTCTL_DB` and `KCTL_DB` will be set on `cd` into the project.
- Agent skills cover the full workflow: `sprint-packet` → work → `sprint-snapshot` → close → `kctl-extract`.
- Canonical committed `kctl` render path: `docs/knowledge/knowledge-base.md`. Agents should render repo knowledge artifacts only to that path.
- No TRACKER.md changes needed; it remains the human-readable planning doc and sprintctl is the machine-readable counterpart.

---

## Request 4 — Refresh to latest upstream tooling and align repo guidance

### Considered

- `sprintctl` advanced from `506bd59` to `54ff569`.
  - New repo-relevant surface: `sprintctl handoff` for machine-readable sprint handoff bundles.
  - Item inspection and claim-management improvements landed upstream, but they do not require new repo policy beyond the existing claim guidance.
- `kctl` advanced from `f649e80` to `dceba4a`.
  - New repo-relevant surface: `--json` output on `kctl review list` and `kctl status`, which matters for agent-to-agent or scripted automation.
  - Preflight behavior now reports cleanly for the current sprint state instead of the earlier stale warning path.
- The repo already had a canonical committed knowledge render path after the previous update: `docs/knowledge/knowledge-base.md`. The remaining alignment work was to teach agents when to use structured output and when to keep handoff artifacts uncommitted.

### Steps taken

1. Ran `uv tool upgrade sprintctl kctl`.
2. Verified new install revisions:
   - `sprintctl`: `506bd59` → `54ff569`
   - `kctl`: `f649e80` → `dceba4a`
3. Inspected the updated CLIs:
   - `sprintctl --help`
   - `sprintctl handoff --help`
   - `kctl review list --help`
   - `kctl status --help`
4. Updated `AGENTS.md` to document:
   - `sprintctl handoff` as the machine-readable handoff path, kept uncommitted by default
   - `kctl review list --json` and `kctl status --json` for structured agent consumption
5. Updated `.gitignore` to ignore the default local JSON artifact names produced by the tooling:
   - `sprint-*.json`
   - `handoff-*.json`
6. Updated `.agents/skills/kctl-extract/SKILL.md` and `.agents/skills/README.md` to reflect structured JSON usage in agent workflows.
7. Re-rendered `docs/knowledge/knowledge-base.md` via `kctl render --output docs/knowledge/knowledge-base.md`.

### Outputs

| Output | Detail |
|--------|--------|
| `sprintctl` upgraded | `506bd59` → `54ff569` |
| `kctl` upgraded | `f649e80` → `dceba4a` |
| AGENTS.md | Added `sprintctl handoff` and `kctl ... --json` guidance |
| `.gitignore` | Ignores default `sprint-*.json` and `handoff-*.json` local artifacts |
| `kctl-extract` skill | Added JSON-output guidance for agent/script consumption |
| Knowledge base render | Refreshed at `docs/knowledge/knowledge-base.md` |

---

## Request 5 — Refresh tooling again and align only what changed

### Considered

- `sprintctl` advanced from `54ff569` to `6259425`.
  - New repo-relevant behavior: more JSON-capable state surfaces are now available (`item list --json`, `item show --json`, `claim list-sprint --json`), and claim records now carry richer workspace metadata fields.
  - Observed regression: `sprintctl sprint show --detail --json` crashes with `UnboundLocalError` on the current install, so the repo should not recommend that path yet.
- `kctl` did not advance from `dceba4a` during this refresh. Existing `review list --json` and `status --json` guidance still matches the live CLI.
- The safest alignment change was to document the JSON surfaces that work today and explicitly avoid adopting the broken one.

### Steps taken

1. Ran `uv tool upgrade sprintctl kctl`.
2. Verified installed revisions:
   - `sprintctl`: `54ff569` → `6259425`
   - `kctl`: unchanged at `dceba4a`
3. Inspected and exercised the updated CLIs:
   - `sprintctl item list --json`
   - `sprintctl claim list-sprint --json`
   - `sprintctl handoff --sprint-id 2 --output /tmp/sprintctl-handoff.json`
   - `kctl review list --json`
   - `kctl status --json --sprint-id 2`
4. Verified live behavior:
   - `kctl preflight` returned `Preflight OK.`
   - `sprintctl item list --json` and `claim list-sprint --json` worked
   - `sprintctl handoff` wrote a bundle with `active_claims`
   - `sprintctl sprint show --detail --json` failed with `UnboundLocalError`
5. Updated `AGENTS.md` to:
   - recommend the working structured-state JSON commands
   - encourage workspace metadata on claims
   - avoid recommending the broken sprint-detail JSON path

### Outputs

| Output | Detail |
|--------|--------|
| `sprintctl` upgraded | `54ff569` → `6259425` |
| `kctl` status | unchanged at `dceba4a` |
| AGENTS.md | Added safe `sprintctl` JSON guidance and richer claim metadata guidance |
| Upstream bug note | `sprintctl sprint show --detail --json` currently crashes and is not adopted in repo guidance |

---

## Request 6 — Refactor to a higher-level repo operating model

### Considered

- The repo's `sprintctl`/`kctl` guidance had grown across `AGENTS.md`, skills, tests, and this session note. The top-level agent file was becoming a command catalog rather than a stable rule set.
- The right split is:
  - `AGENTS.md` keeps the few rules that are costly to forget
  - skills keep task-specific execution details
  - a dedicated runbook owns the repo-level operating model
- The repo already has two committed artifacts with different responsibilities:
  - `docs/sprint-snapshots/sprint-current.txt` for shared sprint execution state
  - `docs/knowledge/knowledge-base.md` for published durable knowledge
- The refactor should make those roles explicit and keep local DB/export/handoff files clearly out of the repo truth path.

### Steps taken

1. Added `docs/runbooks/sprint-and-knowledge-operations.md` as the repo-level operating model for `sprintctl` and `kctl`.
2. Refactored `AGENTS.md` to point at that runbook instead of carrying the full command-level workflow inline.
3. Kept the task-level details in the existing sprint skills rather than duplicating them in the new runbook.
4. Updated `docs/README.md` to index the new runbook.
5. Updated guidance tests to validate the new high-level doc reference instead of the previous long inline command list.

### Outputs

| Output | Detail |
|--------|--------|
| New runbook | `docs/runbooks/sprint-and-knowledge-operations.md` |
| AGENTS.md | Slimmed to durable top-level rules plus pointers to the runbook and skills |
| Docs index | Lists the new sprint/knowledge operations runbook |
| Tests | Updated to match the refactored guidance contract |
