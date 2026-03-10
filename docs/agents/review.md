# Review Mode

## Purpose

Review code with a bias toward bugs, regressions, missing tests, and architectural drift.

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

## Required output shape

- Findings first, ordered by severity, with file references.
- Open questions or assumptions second.
- A brief summary only after the findings.

## Stop and escalate

- Stop if the change cannot be reviewed accurately without missing files or generated artifacts.
- Stop if the change introduces a new product decision without a corresponding requirements update.
- Stop if the review would require executing destructive or mutating commands.
