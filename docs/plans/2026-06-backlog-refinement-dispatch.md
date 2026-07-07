# Homelab-analytics backlog refinement dispatch — June 2026

**Date:** 2026-06-05  
**Classification:** CROSS-CUTTING  
**Status:** dispatch-ready refinement notes; remote `sprintctl` access verified after configuring local `SPRINTCTL_URL`.

## 1. Current-state read

Remote `sprintctl` state now supersedes the committed snapshot. As of 2026-06-05, the live homelab-analytics state shows:

- Active sprint `#354` `policy-truth-boundary` has four done items and one blocked item: `#718` remove deprecated `/ingest/subscriptions` and `/ingest/contract-prices`.
- `keel-ledger-bond`, `semantic-seam-forge`, `transform-dispatch-forge`, and `ha-seam-close` are closed.
- Backlog sprints `#360` through `#363` already cover the frontend waves: `shell-token-pulse`, `brief-flow-mark`, `console-grid-rise`, and `board-watch-wire`.
- Backlog sprint `#356` already covers contract compatibility extraction.
- Backlog sprint `#357` already covers the default-versus-retro web surface decision.
- Older `pack-loop-harbor` and `surface-glass-bridge` backlog records are closed; do not re-register them from the April plan.

The next refinement should therefore avoid duplicate sprint registration and should focus on selecting from the already-planned backlog or resolving the active blocked item.

## 2. Dispatch posture

Use `dispatch-plan` for the first pass of each candidate below when the item still needs a boundary decision. Use `dispatch-build` only after the sprint item has a written acceptance contract and live `sprintctl` claim.

Do not open implementation dispatch until the selected item is claimed in live remote `sprintctl`. This repo rejects `SPRINTCTL_BACKEND=local`.

## 3. Recommended next backlog

### Active cleanup: sprint `#354` `policy-truth-boundary`

**Objective:** Decide and unblock `#718`, the deprecated ingest route removal item.

**Dispatch item:**

| Track | Item | Dispatch | Acceptance |
|---|---|---|---|
| roadmap-truth | Remove deprecated `/ingest/subscriptions` and `/ingest/contract-prices` | `dispatch-plan` if sunset policy is unclear; otherwise `dispatch-build` | Deprecated routes are removed or the blocker is explicitly converted into a dated deferral with rationale. Tests and docs reflect the chosen path. |

**Verification path:** route/API tests covering ingestion endpoints, architecture contract tests if route policy changes, and docs/runbook checks for deprecated command references.

### Sprint `contract-compat-extract`

**Objective:** Move contract compatibility tooling from API-owned code into `packages/platform/contract_compat/` without changing release behavior.

**Dispatch items:**

| Track | Item | Dispatch | Acceptance |
|---|---|---|---|
| extraction | Platform package extraction | `dispatch-build` | Artifact loading, OpenAPI comparison, publication/UI descriptor comparison, schema diffing, report writing, and release bundle packaging move under `packages/platform/contract_compat/`. |
| compatibility | Thin API entrypoint preservation | `dispatch-build` | `apps/api/contract_artifacts.py`, Make targets, generated artifact names, and summary JSON/Markdown shapes remain stable. |

**Verification path:** `pytest tests/test_contract_artifacts.py -x --tb=short` plus lint/type checks for changed Python files.

### Sprint `shell-token-pulse`

**Objective:** Land shared frontend primitives and Operating Picture v2 before larger new surfaces.

**Dispatch items:**

| Track | Item | Dispatch | Acceptance |
|---|---|---|---|
| primitives | Shared tokens and primitives | `dispatch-build` | `Pill`, `Spark`, `NumMono`, `Eyebrow`, motion rules, and stories land without a new state library. |
| operating-picture | Operating Picture v2 refactor | `dispatch-build` | Existing data fetches stay intact; freshness is rendered once; page snapshot story covers the revised layout. |

**Verification path:** targeted web tests, Storybook build if available, and `make verify-fast` before PR/push.

## 4. Parked for this refinement

- `pack-loop-harbor` and `surface-glass-bridge`: already closed in live sprintctl state.
- `transform-dispatch-forge` and `ha-seam-close`: already closed in live sprintctl state.
- Home Assistant add-on polish, marketplace activation/rollback, repo split, and generic cross-backend query abstraction remain rejected or parked per the April backlog refinement.

## 5. Sprintctl registration posture

Do not create new sprints from this packet unless live `sprintctl sprint list --include-backlog --json` shows the candidate is absent. The June-ready work already exists as remote backlog records.

## 6. Environment note

Local access is configured through ignored `.env.sprintctl.local`, populated from the `vscode/sprintctl-cnpg-main-app` Secret and rewritten to the LAN LoadBalancer host `192.168.20.220:5432`. The in-cluster Secret host `sprintctl-cnpg-main-rw.vscode` is valid inside `vscode-shell` but not resolvable from this Codex shell.
