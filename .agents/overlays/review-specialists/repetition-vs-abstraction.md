---
specialist: repetition-vs-abstraction
---

## Scope

Identify duplicated behavior that should become a shared helper. Prioritize parallel
SQLite/PostgreSQL adapter implementations under `packages/storage/`, additions to the
legacy `packages/pipelines/` re-export facade, and copy-pasted blocks of ten or more
lines across product packs or surface modules.

## References

- `docs/architecture/pipeline-ambiguity-classification.md`
- Existing helpers in `packages/shared/` and `packages/platform/`

Structural import tests do not detect behavioral duplication. Flag new near-identical
backend methods without a backend-agnostic extraction, new star re-exports, or imports
from a legacy re-export rather than a canonical implementation path.

## Severity guidance

- `blocker`: a new `from ... import *  # noqa: F403` in the facade cluster, or
  new code depends on a known re-export path.
- `advisory`: a parallel backend pair grows without extraction, or duplicate logic
  crosses pack boundaries.
- `watchlist`: unchanged pre-existing duplication.

Return `[]` when no findings apply.