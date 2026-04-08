# Review Mode

## Purpose

Review code with a bias toward bugs, regressions, missing tests, and architectural drift.

Use `docs/runbooks/project-working-practices.md` for the review loop and the applicable change-class done checklist.
For stable code-bearing scopes in coordinator workflows, this review pass is required before final handoff, reviewer summary, or PR preparation.

## Allowed actions

- Read code, tests, requirements, and docs.
- Run non-mutating verification or static checks.
- Summarize findings and residual risks.

## Required inputs

- The diff or files under review.
- The relevant requirements, architecture sections, and local tests.
- The expected user-facing behavior and failure modes.

## Required verification

- Check that requirements and implementation traceability still align.
- Check that tests cover the behavior that changed.
- Check that app-facing reporting does not bypass reporting-layer models.
- Check that the change satisfies the relevant done criteria for its change class.

## Required output shape

- Findings first, ordered by severity, with file references.
- Open questions or assumptions second.
- A brief summary only after the findings.

## Stop and escalate

- Stop if the change cannot be reviewed accurately without missing files or generated artifacts.
- Stop if the change introduces a new product decision without a corresponding requirements update.
- Stop if the review would require executing destructive or mutating commands.
