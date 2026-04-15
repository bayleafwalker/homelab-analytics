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

## Internal specialist fan-out

`dispatch-review` implements this mode guide via a parallel specialist fan-out rather than
a single general-purpose pass. Each specialist targets a non-overlapping review concern;
their structured JSON findings are consolidated before the operator-facing report is
produced.

**Specialist roster** (prompts in `.agents/skills/dispatch-review/specialists/`):

| Specialist | Model | Concern |
|---|---|---|
| `pack-boundary` | Haiku | Sibling product-pack imports that bypass overview/shared |
| `stratum-coherence` | Sonnet | Code placement relative to the 4-tier stratum map |
| `semantic-ownership` | Sonnet | Semantic intent regressions invisible to structural contract tests |
| `god-class-file-size` | Haiku | Files/functions/classes exceeding size thresholds |
| `repetition-vs-abstraction` | Sonnet | Parallel backend duplication, legacy re-export growth, cross-pack copy-paste |
| `test-quality` | Haiku | Behavior pinning, mock circularity, god-class test file growth |
| `suppression-drift` | Haiku | New `# type: ignore`, `# noqa`, `# pragma: no cover` without rationale |

**What specialists do NOT cover** (already enforced mechanically):

- Layer integrity (landing/transformation/reporting direction) — `tests/test_architecture_contract.py`
- Pack registration completeness — `tests/test_capability_pack_contract.py`
- Publication contract mechanical compatibility and export shape — `tests/test_contract_artifacts.py`,
  `tests/test_publication_contract_exports.py`
- Auth policy coverage — `tests/test_architecture_contract.py`
- Adapter manifest and runtime status shape — `tests/test_adapter_contracts.py`

**Output structure**: Blockers → Advisories → Watchlist. Blockers and Advisories render
as full finding blocks with evidence and recommendation. Watchlist items render as a
compact table. The operator-facing format is the same findings-first markdown the skill
has always produced; the JSON is an internal consolidation format only.
