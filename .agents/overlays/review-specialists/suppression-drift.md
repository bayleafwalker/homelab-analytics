---
specialist: suppression-drift
---

## Scope

Detect new `# type: ignore`, `# noqa`, and `# pragma: no cover` annotations. Every new
suppression needs a rationale on the same or preceding line; otherwise report it.

Treat new suppressions in `packages/pipelines/`, `apps/worker/runtime.py`, and
`packages/storage/` as higher-risk because those areas already carry known suppression
clusters.

## Severity guidance

- `blocker`: a new unexplained suppression in a hot spot, or a bare
  `# type: ignore` without an error code anywhere in the diff.
- `advisory`: a new explained suppression in a hot spot, or a new coverage
  suppression outside abstract or protocol code.
- `watchlist`: an unchanged existing suppression cluster.

Return `[]` when no findings apply.