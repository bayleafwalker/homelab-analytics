---
specialist: semantic-ownership
---

## Scope

Find semantic intent regressions that pass structural tests but violate ownership rules:

1. Canonical facts or dimensions read or written by the wrong package.
2. Domain-local fields that meet the promotion criteria for a shared semantic contract.
3. Category handling that bypasses `category_id` governance.
4. Meaningful contract changes to units, nullability, or trust source without a version bump.

## References

- `docs/architecture/semantic-contracts.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/category-governance.md`

## Severity guidance

- `blocker`: a semantic regression without a version bump, or a reporting path
  that bypasses `category_id` governance.
- `advisory`: a newly promotable local field or an expanded bridge field without
  a removal plan.
- `watchlist`: unchanged documented governance debt.

Return `[]` when no findings apply.