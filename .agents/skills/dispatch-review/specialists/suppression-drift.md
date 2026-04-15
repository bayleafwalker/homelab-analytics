---
specialist: suppression-drift
model: haiku
---

## Scope

Detect new `# type: ignore`, `# noqa`, or `# pragma: no cover` annotations added in the
scope under review, especially near or inside existing suppression clusters. Each new
suppression must either: (a) have a rationale comment on the same line or the preceding
line, OR (b) be flagged as a finding.

## Known suppression clusters (highest-risk locations)

New suppressions near these locations are automatically advisory or higher:

- `packages/pipelines/` — legacy re-export cluster uses `# noqa: F403` throughout.
  New `# noqa` here extends the facade rather than reducing it.
- `apps/worker/runtime.py` — three `# type: ignore[return]` around runtime repository
  accessors. New additions suggest the runtime container typing compromise is spreading.
- `packages/storage/postgres_provenance_control_plane.py` — three `# type: ignore`
  around row dict coercions. New additions suggest schema typing friction is growing.
- `packages/pipelines/publication_confidence_service.py` — two `# type: ignore` on
  freshness/confidence value coercions.
- `packages/domains/finance/contracts/op_gold_invoice_pdf_v1.py` — one unscoped
  `# type: ignore` on `pdfplumber` optional import.

## Does NOT duplicate

No existing test counts or audits suppression annotations. This specialist is entirely
uncovered by the test suite.

## Severity guidance

- **blocker**: New suppression added inside an existing hot-spot cluster without a
  rationale comment, or a bare `# type: ignore` (no error code) added anywhere in the
  diff scope.
- **advisory**: New suppression added with a rationale comment but still inside a
  known cluster; new `# pragma: no cover` added to non-abstract/non-protocol code.
- **watchlist**: Pre-existing suppression cluster that was not changed in this scope.

## Output schema

Return a JSON array. `line` is the line number of the new suppression annotation.

```json
[
  {
    "specialist": "suppression-drift",
    "severity": "blocker | advisory | watchlist",
    "file": "apps/worker/runtime.py",
    "line": 87,
    "finding": "New # type: ignore added to runtime repository accessor without rationale",
    "evidence": "return self._stores[key]  # type: ignore",
    "recommendation": "Add a typed protocol for the store registry, or add a rationale comment explaining why the type ignore is necessary",
    "blocker": false
  }
]
```

Return `[]` if no findings.
