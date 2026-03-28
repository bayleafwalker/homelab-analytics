# Planning Mode

## Purpose

Turn a request into a decision-complete implementation plan before code changes begin.

Use the source-of-truth stack and working loops in `docs/runbooks/project-working-practices.md` to decide how the task should start.

## Allowed actions

- Read code, docs, requirements, tests, and local configuration.
- Run non-mutating checks that reduce ambiguity.
- Compare implementation options against repo constraints and requirements.

## Required inputs

- The relevant user goal and success criteria.
- Current repository state from direct inspection.
- Current `sprintctl` state when the request is scoped as sprint work or asks for the next item.
- A list of requirements or architecture docs affected by the work.

## Required verification

- Confirm the target layer boundaries before proposing implementation details.
- Confirm which working loop applies first: new scope registration, resume existing sprint item, or direct implementation.
- Confirm whether the work already exists in `sprintctl` or whether new scope registration via `sprint-packet` is needed.
- Confirm whether an existing exclusive claim clearly belongs to the current live claim identity before planning implementation under that item.
- Confirm whether requirements docs, architecture docs, or AGENTS docs need updates.
- Identify the local verification path that will prove the work end-to-end.

## Required output shape

- A concise summary of scope and intent.
- A concrete implementation outline with tests and verification steps.
- Explicit assumptions where the repo does not already decide the outcome.

## Stop and escalate

- Stop if the request would collapse landing, transformation, and reporting responsibilities.
- Stop if the plan depends on undocumented product decisions or a missing canonical contract.
- Stop if a sprint-scoped item is already exclusively claimed and ownership cannot be proven to match the current live claim identity.
- Stop if the plan would require reverting unrelated user changes.
