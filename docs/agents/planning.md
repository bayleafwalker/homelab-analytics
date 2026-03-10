# Planning Mode

## Purpose

Turn a request into a decision-complete implementation plan before code changes begin.

## Allowed actions

- Read code, docs, requirements, tests, and local configuration.
- Run non-mutating checks that reduce ambiguity.
- Compare implementation options against repo constraints and requirements.

## Required inputs

- The relevant user goal and success criteria.
- Current repository state from direct inspection.
- A list of requirements or architecture docs affected by the work.

## Required verification

- Confirm the target layer boundaries before proposing implementation details.
- Confirm whether requirements docs, architecture docs, or AGENTS docs need updates.
- Identify the local verification path that will prove the work end-to-end.

## Required output shape

- A concise summary of scope and intent.
- A concrete implementation outline with tests and verification steps.
- Explicit assumptions where the repo does not already decide the outcome.

## Stop and escalate

- Stop if the request would collapse landing, transformation, and reporting responsibilities.
- Stop if the plan depends on undocumented product decisions or a missing canonical contract.
- Stop if the plan would require reverting unrelated user changes.
