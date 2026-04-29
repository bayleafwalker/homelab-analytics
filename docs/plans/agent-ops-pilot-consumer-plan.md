# Homelab Analytics Agent-Ops Pilot Consumer Plan

`homelab-analytics` is the first pilot consumer for the agent-ops substrate described in `/projects/dev/agentops/docs/plans/agentops/agent-ops-substrate-plan.md`.

This repo should validate the substrate in real use, but it should not own the implementation of sprintctl remote mode, auditctl, actionq, the agentops/agent-cockpit operator surface, or appservice deployment manifests.

## Pilot Scope

What belongs in this repo:

- Remote-mode migration rehearsal and rollback notes for this repo's sprintctl state.
- Repo-local `.envrc` and marker-file changes needed to opt into remote sprintctl once workstream B ships.
- Audit hook rollout for this repo once auditctl workstream D ships.
- Test data and operator feedback for agent-cockpit views that read `homelab-analytics` sprint, audit, and knowledge artifacts.
- Bug reports or follow-up requirements discovered during the pilot.

What does not belong in this repo:

- Core sprintctl remote-mode implementation.
- auditctl package implementation.
- actionq server or daemon implementation.
- agent-cockpit frontend implementation.
- Kubernetes deployment source of truth for sprintctl Postgres, actionq, or agent-cockpit.

## Current State

Migrated to remote mode on 2026-04-29.

- Sprint state migrated from local SQLite to `sprintctl-postgres` (CNPG) in the appservice cluster.
- Local SQLite archived at `.sprintctl/.sprintctl.db.frozen-20260429T153118Z`.
- Backend marker written to `.sprintctl/backend.json` (`remote`, repo_id `homelab-analytics`).
- `.envrc` updated with `SPRINTCTL_BACKEND=remote`; `SPRINTCTL_URL` is expected from injected session environment or a local secret, not committed in-repo.
- `homelab-analytics` now appears in the cockpit `/cockpit/api/repos` response with active sprint `#365 semantic-seam-forge`.
- Active sprint is `5/5` items done, `0` active claims.
- Migration required two fixes to `sprintctl`: `--remap-ids` CLI flag (shared postgres has conflicting global integer IDs), and correct FK column name for `dep` table (`item_id` not `work_item_id`).
- Audit artifact path is live: `/projects/dev/_artifacts/homelab-analytics/audit/events-2026-04-26.ndjson`.

## Pilot Readiness Gates

The pilot should not be treated as the place where substrate unknowns are solved ad hoc.

- ✅ Workstream B: `sprintctl` remote backend and migration path — shipped.
- ✅ `appservice`: `sprintctl-postgres` deployment — live.
- The actionq integration surface is explicit enough for cockpit claims/session enrichment and eventual dispatch.
- The rollout plan states whether migration happens between sprints or mid-sprint and how rollback is handled for this repo.

## Acceptance

The pilot is successful when:

- `homelab-analytics` can migrate sprintctl state to remote mode and keep routine sprintctl commands working.
- Audit events for git hooks and manual events land in `/projects/dev/_artifacts/homelab-analytics/audit/` when `AUDITCTL_ARTIFACTS_ROOT=/projects/dev`.
- Agent-cockpit can display this repo's active sprint state, takeup state, actionq session liveness, and audit outcomes from the canonical sources.
- The repo can roll back or pause the pilot without losing local project work.
