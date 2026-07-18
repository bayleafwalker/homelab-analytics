---
specialist: pack-boundary
---

## Scope

Detect direct imports between sibling product packs that bypass allowed crossing points:
`packages/domains/overview/`, `packages/shared/`, or `packages/platform/`. Also flag
pack-internal types exposed through another pack's public surface and pack-specific
utilities added to `packages/shared/`.

## References

- `docs/decisions/household-platform-adr-and-refactor-blueprint.md`
- `docs/architecture/data-platform-architecture.md`

`tests/test_architecture_contract.py` covers selected import bans. This review covers
sibling product-pack crossings that those tests do not express.

## Severity guidance

- `blocker`: a new sibling-pack import in the diff.
- `advisory`: an existing violation was touched or made worse.
- `watchlist`: an unchanged pre-existing violation.

Return `[]` when no findings apply.