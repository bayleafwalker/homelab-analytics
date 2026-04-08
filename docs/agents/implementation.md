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
- Confirm that any existing exclusive claim either belongs to the current live claim identity or has been handed off before editing repo files.
- Record material item-state changes in `sprintctl` and refresh the shared sprint snapshot when the workflow needs a new shared artifact or reaches a natural batch boundary.
- Update requirements or architecture docs when behavior or scope changes.
- Add or update focused tests and at least one integration path for new behavior.
- **Commit at the enclosing reviewable scope boundary. A scope may contain one sprint item or multiple tightly related items that should be reviewed together. Do not batch unrelated scopes into a single commit.**
- **For changed Python files, run file-scoped static checks before close-out: `ruff check <changed-python-files>` and `mypy <changed-python-files>`.**
- **Run targeted tests only — `pytest <changed-test-files> -x --tb=short` — foreground and blocking. Never background pytest for sequential verification. Full suite (`make test`) is a CI gate, not an in-session gate.**
- **After adding or modifying any API route, auth policy, scenario policy mapping, or architecture doc, run `pytest tests/test_architecture_contract.py -x --tb=short`.**
- **Gate `sprintctl` done transitions on targeted test exit code: `pytest <files> -x --tb=short && sprintctl item done-from-claim ...`**
- **For stable code-bearing scopes, run `dispatch-review` before final handoff, reviewer summary, PR prep, or CI-triggering push, and resolve blockers before calling the scope complete.**
- A repo change is not complete just because implementation verification passed; review and any sprint/kctl closeout steps must be requested or explicitly reported as blocked.
- **If tests fail after a change, diagnose the root cause, fix, and re-run — up to 5 cycles — before escalating. Only escalate if still failing after 5 attempts or if a design decision is required.**

## Required output shape

- Implement the change end-to-end where feasible.
- Report what changed, what was verified, and any residual gaps.
- Reference the verification commands or test targets that were run.
- If any non-obvious decision was made during implementation, log it as a `sprintctl` event before closing the item. Do not defer to sprint close — log while context is hot.

## Stop and escalate

- Stop if the required design choice is not decided by code, docs, or user instruction.
- Stop if the implementation would rely on route-specific heuristics instead of source-asset configuration.
- Stop if a sprint-scoped item has an exclusive claim that does not clearly belong to the current live claim identity and no handoff has been produced.
- Stop if a necessary change conflicts with unexpected user edits.
