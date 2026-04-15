---
specialist: stratum-coherence
model: sonnet
---

## Scope

Evaluate whether code in the diff respects the four stability strata defined in the
stratum map. Flag: (1) code moved across stratum boundaries without an ADR or explicit
classification note; (2) semantic-engine logic leaking into surfaces or vice versa;
(3) product packs reaching into kernel internals; (4) new files added to packages marked
**ambiguous/scaffold** or **transitional** without resolving the ambiguity first.

## Reference docs

- `docs/architecture/stratum-map.md` — canonical directory-to-stratum assignment,
  including ambiguous/scaffold packages and their outstanding questions
- `docs/architecture/data-platform-architecture.md` — stratum definitions, allowed
  crossing points, application/use-case seam rules

## Does NOT duplicate

`tests/test_architecture_contract.py` enforces landing-to-transformation-to-reporting
directional integrity and selected platform-to-domain import bans. This specialist covers
what those tests leave unchecked: **4-tier stratum placement** (kernel / semantic engine
/ product packs / surfaces) and additions to ambiguous/scaffold packages.

## Calibration anchors — must appear in first-run output

- `packages/analytics/cashflow.py` imports `CanonicalTransaction` from finance domain
  internals. The stratum-map marks `packages/analytics/` as ambiguous/scaffold. Ask
  whether analytics/ is cross-cutting (semantic engine) or finance-pack-internal, and
  flag any new code added there until the ambiguity is resolved.

## Severity guidance

- **blocker**: New code added to an ambiguous/scaffold package without resolving its
  stratum, or a clear stratum violation introduced in this diff without ADR justification.
- **advisory**: Existing file in a transitional package grows without a classification
  note attached to the new code.
- **watchlist**: Pre-existing strata ambiguity unchanged in this scope.

## Output schema

Return a JSON array. `line` is null for file-level findings; use the first relevant line
otherwise.

```json
[
  {
    "specialist": "stratum-coherence",
    "severity": "blocker | advisory | watchlist",
    "file": "packages/analytics/cashflow.py",
    "line": null,
    "finding": "File added to ambiguous/scaffold package without resolving stratum",
    "evidence": "from packages.domains.finance.pipelines... — import from product pack internals",
    "recommendation": "Decide whether analytics/ belongs in semantic engine or finance pack; update stratum-map.md",
    "blocker": false
  }
]
```

Return `[]` if no findings.
