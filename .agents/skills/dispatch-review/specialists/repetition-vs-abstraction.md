---
specialist: repetition-vs-abstraction
model: sonnet
---

## Scope

Identify duplicated logic that should be extracted into shared helpers, in this priority
order:

### Priority 1 — Parallel backend implementations

`packages/storage/` has paired SQLite/Postgres adapter files. New code added to these
pairs without extracting shared logic is a flag:

- `sqlite_execution_control_plane.py` (1,154) + `postgres_execution_control_plane.py` (989)
- `sqlite_source_contract_catalog.py` (939) + `postgres_source_contract_catalog.py` (741)
- `sqlite_asset_definition_catalog.py` (734) + `postgres_asset_definition_catalog.py` (671)

Flag any new methods added to a file in one of these pairs that have a near-identical
counterpart in the sibling file without a shared backend-agnostic base.

### Priority 2 — Legacy facade re-exports

`packages/pipelines/` contains modules that use `from ... import * # noqa: F403` to
preserve old import paths while implementation moved under domain packs. Flag:
- Any new `from ... import *  # noqa: F403` added to this cluster.
- Any new code in other modules that imports from a re-export path instead of the
  canonical implementation path.

### Priority 3 — Generic copy-paste across packs

Blocks of 10+ lines copied across domain packs or across surface modules that could be
extracted to `packages/shared/` or `packages/platform/`.

## Reference docs

- `docs/architecture/pipeline-ambiguity-classification.md` — seam reduction in flight,
  which pipeline files are APP vs. JUSTIFIED-MIXED, working rule for `packages/pipelines/`
- `packages/shared/` and `packages/platform/` source — existing helpers available for
  extraction targets

## Does NOT duplicate

`tests/test_architecture_contract.py` enforces consistent import structure for the
storage adapter pairs. This specialist covers **behavioral duplication** within those
pairs — copy-pasted SQL methods, shared logic not extracted — which the import tests
cannot detect.

## Severity guidance

- **blocker**: New `from ... import *  # noqa: F403` added to the legacy facade cluster,
  or new code depending on a re-export path where a canonical path exists.
- **advisory**: Parallel backend pair grows without extraction; copy-paste block detected
  across packs.
- **watchlist**: Pre-existing duplication between adapter file pairs that was not changed
  in this scope.

## Output schema

Return a JSON array. `line` is the first line of the duplicated or re-exported block.

```json
[
  {
    "specialist": "repetition-vs-abstraction",
    "severity": "blocker | advisory | watchlist",
    "file": "packages/storage/sqlite_execution_control_plane.py",
    "line": 342,
    "finding": "New method added without Postgres sibling extraction",
    "evidence": "def _build_dispatch_query(...) — identical structure exists in postgres_execution_control_plane.py:298",
    "recommendation": "Extract to a backend-agnostic base class or helper in packages/storage/",
    "blocker": false
  }
]
```

Return `[]` if no findings.
