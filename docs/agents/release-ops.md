# Release And Ops Mode

## Purpose

Prepare work for repeatable local verification, CI validation, and deployment-oriented handoff.

Use `docs/runbooks/project-working-practices.md` for the release/push loop and handoff expectations.
Use `docs/runbooks/release-governance.md` for branch, tag, and GitHub Release policy.

## Allowed actions

- Edit local runner targets, CI workflows, and deployment scaffolding.
- Run build, lint, type-check, test, Docker, and Helm verification.
- Improve operational docs and release notes.

## Required inputs

- The repository verification targets and their expected outcomes.
- The deployment surfaces affected by the change.
- The secret, auth, and runtime assumptions for the target workload.

## Required verification

- Ensure blocking local and CI gates are updated with the new behavior.
- Ensure the change satisfies the CI/release checklist in `docs/runbooks/project-working-practices.md`.
- Keep secret handling reference-based; do not introduce checked-in secrets.
- Verify Docker and Helm paths when release or runtime behavior changes.

## Required output shape

- The updated local and CI verification path.
- Any new environment, tooling, or deployment assumptions.
- Clear note of which checks are blocking versus advisory.

## Stop and escalate

- Stop if the release workflow would publish artifacts without matching tests.
- Stop if deployment changes require secrets or infrastructure not represented in repo docs.
- Stop if the change would make local verification depend on external services without a local fallback.
