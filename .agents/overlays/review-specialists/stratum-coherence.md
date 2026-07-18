---
specialist: stratum-coherence
---

## Scope

Evaluate whether the diff respects the kernel, semantic-engine, product-pack, and
surface strata. Flag code crossing strata without an ADR or classification note,
semantic logic leaking into surfaces, product packs reaching kernel internals, and new
files in ambiguous, scaffold, or transitional packages without resolving their status.

## References

- `docs/architecture/stratum-map.md`
- `docs/architecture/data-platform-architecture.md`

`tests/test_architecture_contract.py` checks selected layer direction and imports. This
review covers placement and unresolved package ambiguity beyond those checks.

## Severity guidance

- `blocker`: new code in an ambiguous package without resolving its stratum, or
  a clear unapproved stratum violation introduced by the diff.
- `advisory`: an existing transitional package grows without a classification note.
- `watchlist`: unchanged stratum ambiguity.

Return `[]` when no findings apply.