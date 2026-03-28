# Implementation Mode

## Purpose

Execute an approved plan while preserving architectural boundaries and keeping verification close to the code change.

Use `docs/runbooks/project-working-practices.md` for startup order, change-class done criteria, and close-out expectations.

## Allowed actions

- Edit repo-tracked files.
- Add or update tests with the implementation.
- Run local verification needed to prove the change.

## Required inputs

- The approved plan or a request with clear local intent.
- The live `sprintctl` item and claim state when the request is sprint-scoped.
- The existing contracts, fixtures, and extension points for the target layer.
- The local verification targets that must pass before close-out.

## Required verification

- Keep landing, transformation, reporting, and application logic in their intended layers.
- Follow the implementation loop and the applicable change-class checklist from `docs/runbooks/project-working-practices.md`.
- Use live `sprintctl` state to decide which existing sprint item is being executed; do not derive active task selection from sprint docs alone when the DB is available.
- Record material item-state changes in `sprintctl` and refresh the shared sprint snapshot when that state changes.
- Update requirements or architecture docs when behavior or scope changes.
- Add or update focused tests and at least one integration path for new behavior.

## Required output shape

- Implement the change end-to-end where feasible.
- Report what changed, what was verified, and any residual gaps.
- Reference the verification commands or test targets that were run.

## Stop and escalate

- Stop if the required design choice is not decided by code, docs, or user instruction.
- Stop if the implementation would rely on route-specific heuristics instead of source-asset configuration.
- Stop if a necessary change conflicts with unexpected user edits.
