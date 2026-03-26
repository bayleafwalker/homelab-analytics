---
name: code-change-verification
description: Use after repo-tracked code or docs change and local verification must be selected, run, or reported before review or handoff. Do not use for planning-only tasks or when nothing repo-tracked changed.
---

## Goal

Standardize how this repo chooses, runs, and reports verification before review, handoff, PR, or push.

## Inputs

- The changed files or diff.
- The relevant local test, lint, typecheck, docs, contract, Docker, or Helm targets.
- Whether the change is headed to review, PR, or a branch push that will trigger CI.

## Steps

1. Map the changed surfaces to the smallest useful checks first.
2. Run targeted verification for the affected area before broader repo gates.
3. If the change is going to PR or a CI-triggering push, run `make verify-fast`.
4. Record exact commands run, their result, and any checks you could not run locally.
5. State whether the change is ready for review or still has verification debt.

## Output contract

- A verification summary listing commands actually run.
- Explicit pass/fail status for each command.
- A clear note on residual gaps, skipped checks, or blockers.

## Do not

- Do not imply a check passed if it was not run.
- Do not skip `make verify-fast` before PR or CI-triggering push.
- Do not substitute generic reassurance for actual command results.
