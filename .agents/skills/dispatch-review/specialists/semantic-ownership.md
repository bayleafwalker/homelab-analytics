---
specialist: semantic-ownership
model: sonnet
---

## Scope

Identify semantic intent regressions and ownership mismatches that pass mechanical
contract tests but violate the domain model or semantic contract rules. Specifically:

1. Code that reads or writes a canonical fact or dimension but lives in the wrong package
   per the domain model (e.g., a shared dimension maintained by a pack that doesn't own it).
2. New domain-local fields that should be promoted to a shared semantic contract per the
   rules in semantic-contracts.md.
3. Ad-hoc category handling that bypasses `category_id` governance (free-text joins,
   hardcoded category strings, new category columns outside `dim_category`).
4. Contract changes that are mechanically compatible but semantically meaningful — field
   whose units, nullability convention, or trust source changes without the contract
   version being bumped.

## Reference docs

- `docs/architecture/semantic-contracts.md` — shared vs domain-local dimension rules,
  promotion criteria, bridge field policy
- `docs/architecture/domain-model.md` — canonical facts, dimensions, ownership, and
  governance notes
- `docs/architecture/category-governance.md` — `category_id` as stable key, system
  categories, operator sub-categories, budget/spend attribution rules

## Does NOT duplicate

`tests/test_publication_contract_exports.py` checks column types, scalar type mapping,
and required reporting relations. `tests/test_capability_pack_contract.py` checks field
completeness and publication ownership. This specialist targets **semantic intent**:
units, nullability conventions, trust sources, and governance bypass — all invisible to
structural contract tests.

## Severity guidance

- **blocker**: Semantic regression that changes meaning without a version bump, or new
  code bypassing `category_id` governance in a path that feeds reporting marts.
- **advisory**: New domain-local field that looks promotable; existing bridge field
  expanded without documenting a removal plan.
- **watchlist**: Pre-existing governance gap noted in semantic-contracts.md that is
  unchanged in this scope.

## Output schema

Return a JSON array. `line` is the most relevant line number, or null for file-level.

```json
[
  {
    "specialist": "semantic-ownership",
    "severity": "blocker | advisory | watchlist",
    "file": "packages/domains/finance/pipelines/scenario_service.py",
    "line": null,
    "finding": "Cross-domain scenario projection references mart tables via direct import rather than shared semantic contract",
    "evidence": "Scenario service builds projections using homelab and utilities mart constants imported directly",
    "recommendation": "Define a shared scenario-input contract or route through the overview pack's cross-domain mart access layer",
    "blocker": false
  }
]
```

Return `[]` if no findings.
