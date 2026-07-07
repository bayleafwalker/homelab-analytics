# Implementation Session Plan — July 2026 Backfill Roadmap

**Date:** 2026-07-07
**Source of scope:** `docs/plans/2026-07-architect-scope-and-backfill-roadmap.md`
**Dispatch posture:** each session below maps to a specific backlog sprint in remote `sprintctl` (`SPRINTCTL_BACKEND=local` is rejected; use the configured `SPRINTCTL_URL`).

## 1. How to use this plan

Each session is a discrete Claude Code / Codex working session. A session is entered by claiming a specific sprint item in remote `sprintctl` and exited when the item is done and committed. Sessions are grouped into three waves that respect the dependency graph in the architect roadmap §8.

- **Wave 1** unblocks the semantic delivery and lineage foundations that later waves consume.
- **Wave 2** builds pack lifecycle, adapter maturation, and Stage 9 governance surfaces on top of Wave 1.
- **Wave 3** delivers the agentic surface and the operational readiness work that lets external agents and cluster deployment consume the platform.

Backfill work (domain marts, backup, self-observability) runs in parallel to each wave because it does not depend on the architectural spine.

Dispatch rules:
- Use `dispatch-plan` for any session whose acceptance contract is not yet written into the sprint item at claim time.
- Use `dispatch-build` only after the item has a written acceptance contract and a live remote `sprintctl` claim.
- Do not batch sprints across sessions. Each sprint has enough scope for one focused session; interleaving them defeats the point of the boundaries.

## 2. Session ordering

### Wave 1 — Semantic and lineage foundations

| Session | Sprint | Enter when | Exit when |
|---|---|---|---|
| S1 | #391 `render-semantic-atlas` | Current `#356 extract-contract-compat` is closed | `/api/semantic-index` returns typed semantic hints for every publication; Accept-header + `X-Publication-Version` negotiation implemented; targeted tests green |
| S2 | #394 `lineage-graph-lantern` | Independent — can run in parallel with S1 | `/api/lineage/publication/{key}` returns transitive graph; web-shell viewer reachable from a publication tile; targeted tests green |
| S3 | #389 `veil-secret-loom` | Independent | `SecretResolver` protocol shared by HA + Prometheus + export renderer; `EntityCorrelationContract` covers two-adapter case in tests |

### Wave 2 — Pack lifecycle and governance surfaces

| Session | Sprint | Enter when | Exit when |
|---|---|---|---|
| S4 | #392 `pack-manifest-forge` | S1 done (semantic index shape stable) | Unified `PackManifest` in place; `PackCompatibilityChecker` rejects a broken pack; contract-test harness runs in CI |
| S5 | #390 `prom-ingest-second` | S3 done (credential + correlation available) | Prometheus federation `IngestAdapter` lands `fact_cluster_metric`; typed health surfaces at `/api/adapters/*/status` |
| S6 | #395 `confidence-canvas-glow` | S2 done (lineage graph API available) | Confidence dashboard lists every publication with freshness/completeness/verdict; scenario projections expose assumption sets |
| S7 | #393 `pack-lifecycle-loom` | S4 done | Pack registry supports install/activate/upgrade/deactivate/rollback with pre-upgrade contract check that blocks incompatible upgrades |

### Wave 3 — Agentic surface and operations readiness

| Session | Sprint | Enter when | Exit when |
|---|---|---|---|
| S8 | #397 `agent-surface-mcp` | S1 and S2 done (semantic index and lineage graph available) | LLM semantic index served under a stable endpoint; MCP tools cover retrieval + scenario proposal + policy proposal; ActionProposal generalizes HA approval queue |
| S9 | #399 `appservice-first-deploy` | Independent | Helm chart reconciled with `docs/notes/appservice-cluster-integration-notes.md`; first live deploy to `appservice` cluster with OIDC + Postgres passes smoke |
| S10 | #400 `self-observ-canvas` | S9 done (live cluster to observe) | SLOs + error budget declared; alert rules generated; self-observability Grafana dashboard committed and referenced from operations runbook |

### Backfill track — runs in parallel to any wave

| Session | Sprint | Enter when | Exit when |
|---|---|---|---|
| BF1 | #398 `domain-marts-fillout` | Independent | Ten planned marts implemented across infra, home-auto, assets, and finance tracks; each mart appears in `/api/semantic-index` after S1 |
| BF2 | #396 `portability-anchor` | Independent | Worker backup/restore round-trips the sample dataset; `docs/runbooks/backup-and-restore.md` published and referenced |

## 3. Session-by-session entry checklist

For every session:

1. `source .envrc` and confirm `SPRINTCTL_DB` and `SPRINTCTL_URL` (the harness rejects local backend).
2. Read the sprint via `sprintctl sprint show --sprint-id <ID>` and confirm the item list matches the architect roadmap §7.
3. Read only the files named in the acceptance contract before claiming — do not pre-explore.
4. Claim the first item on the sprint's primary track via `sprintctl claim start`.
5. Register the session via `sprintctl session` if the harness expects it.
6. Run `make verify-fast` **before** any code change to confirm a clean baseline.

## 4. Session-by-session exit checklist

For every session:

1. Run the targeted tests named in the acceptance contract and confirm all pass.
2. Run `make verify-fast` and confirm a clean tree apart from the intended change.
3. Commit at the smallest reviewable scope boundary. If the session closed one item on a multi-item sprint, commit that item's changes without touching the other items.
4. Close the item via `sprintctl item done-from-claim` gated on the exit tests.
5. Capture knowledge events on the item before closing — anything surprising or non-obvious about the seam that was crossed.
6. Refresh `docs/sprint-snapshots/sprint-current.txt` only when the sprint itself closes or reaches a shared-review milestone.

## 5. Wave transition gates

The following gates are hard. A wave does not begin until its predecessor gate is met.

- **W1 → W2**: `/api/semantic-index` and `/api/lineage/publication/{key}` are live in `main`; the extract-contract-compat sprint is closed; two of the three Wave 1 sessions are done.
- **W2 → W3**: `PackCompatibilityChecker` rejects broken packs in CI; confidence dashboard is reachable through the web shell; at least one non-HA adapter is registered.

Backfill sprints (`#398`, `#396`) do not gate wave transitions.

## 6. Non-goals for this plan

- No new sprint registration inside a session. If a session discovers scope that does not fit its current sprint, capture it as a knowledge event and defer to the next architect pass.
- No production data migrations. Every new mart, adapter, and pack manifest lands with a migration under `migrations/postgres/` or the appropriate store; migrations are additive and follow the migration-authoring rules in `CLAUDE.md`.
- No CI freeze. The sequencing above respects the existing `verify-fast` posture; each session must leave the tree green.
- No marketplace, no repo split, no cross-backend query abstraction, no multi-tenant work. Any of these requires a new architect pass.

## 7. Reference

- Architect roadmap: `docs/plans/2026-07-architect-scope-and-backfill-roadmap.md`
- Household operating platform roadmap: `docs/plans/household-operating-platform-roadmap.md`
- Adapter governance: `docs/architecture/adapter-governance.md`
- Contract governance: `docs/architecture/contract-governance.md`
- Cluster integration notes: `docs/notes/appservice-cluster-integration-notes.md`
