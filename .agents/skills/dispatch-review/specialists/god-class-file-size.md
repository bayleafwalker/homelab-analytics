---
specialist: god-class-file-size
model: haiku
---

## Scope

Detect files, classes, and functions that are too large to review safely. Produce two
outputs: (a) findings for files/classes/functions that **grew in this scope** and crossed
a threshold; (b) a **watchlist** of pre-existing top offenders that must appear on every
run so subsequent runs can detect growth.

Thresholds:
- File: 600 LOC
- Function: ~80 lines
- Class: >15 methods, OR methods that import from >3 distinct packages

## Reference inventory (calibration anchors)

Production files already over 600 LOC — include all of these in the watchlist on every run
even if they did not change:

`packages/domains/finance/pipelines/scenario_service.py` 1,631 |
`packages/pipelines/transformation_service.py` 1,484 |
`packages/demo/bundle.py` 1,384 |
`packages/storage/sqlite_execution_control_plane.py` 1,154 |
`packages/storage/postgres_execution_control_plane.py` 989 |
`packages/storage/sqlite_source_contract_catalog.py` 939 |
`packages/domains/overview/pipelines/transformation_overview.py` 880 |
`packages/storage/control_plane.py` 838 |
`packages/demo/seeder.py` 732 |
`packages/storage/sqlite_asset_definition_catalog.py` 734 |
`packages/shared/external_registry.py` 775 |
`packages/domains/utilities/pipelines/transformation_utilities.py` 685 |
`packages/storage/postgres_source_contract_catalog.py` 741 |
`packages/storage/postgres_asset_definition_catalog.py` 671 |
`packages/domains/homelab/pipelines/ha_bridge_ingestion.py` 658 |
`packages/domains/finance/pipelines/transformation_transactions.py` 650 |
`packages/platform/publication_contracts.py` 617

## Does NOT duplicate

No existing test enforces file size, function length, or class complexity thresholds.
This specialist is entirely uncovered by the test suite.

## Severity guidance

- **blocker**: File grew in this scope AND is now the largest file in its package by >2x.
- **advisory**: File grew in this scope and crossed 600 LOC, or a function crossed 80
  lines in new code added in this scope.
- **watchlist**: Pre-existing offender listed above that did not change in this scope.

## Output schema

Return a JSON array. For file-level findings, `line` is null.

```json
[
  {
    "specialist": "god-class-file-size",
    "severity": "blocker | advisory | watchlist",
    "file": "packages/domains/finance/pipelines/scenario_service.py",
    "line": null,
    "finding": "File is 1,631 LOC — 2.7x over the 600 LOC threshold",
    "evidence": "wc -l output or line count from read",
    "recommendation": "Split scenario computation into focused modules; candidate split: projection engine vs. service orchestration",
    "blocker": false
  }
]
```

Return `[]` if no findings. The watchlist section must never be empty if any of the
calibration anchors above exist in the repo.
