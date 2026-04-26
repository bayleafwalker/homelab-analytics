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

## Acceptance

The pilot is successful when:

- `homelab-analytics` can migrate sprintctl state to remote mode and keep routine sprintctl commands working.
- Audit events for git hooks and manual events land in `/projects/dev/_artifacts/homelab-analytics/audit/` when `AUDITCTL_ARTIFACTS_ROOT=/projects/dev`.
- Agent-cockpit can display this repo's active sprint state, takeup state, actionq session liveness, and audit outcomes from the canonical sources.
- The repo can roll back or pause the pilot without losing local project work.
