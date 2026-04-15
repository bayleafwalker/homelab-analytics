---
specialist: pack-boundary
model: haiku
---

## Scope

Detect direct imports between sibling product packs that bypass the allowed crossing
points (`packages/domains/overview/` or a shared semantic contract in `packages/shared/`
or `packages/platform/`). Also flag pack-internal types leaking through public surfaces
of other packs, and new utilities added to `packages/shared/` that look pack-specific
and should live pack-local instead.

## Reference docs

- `docs/decisions/household-platform-adr-and-refactor-blueprint.md` — modular monolith,
  capability pack isolation rules, headless core design
- `docs/architecture/data-platform-architecture.md` — product pack responsibilities,
  allowed crossing points (overview is the composition pack)

## Does NOT duplicate

`tests/test_architecture_contract.py` enforces `domains → apps`, `domains → adapters`,
`platform → domains`, and `shared → domains` import bans. This specialist covers what
those tests leave unchecked: **sibling product-pack-to-pack imports** (e.g., finance
importing homelab or utilities model internals directly).

## Calibration anchors — must appear in first-run output

- `packages/domains/finance/pipelines/scenario_service.py`: imports
  `packages.domains.homelab.pipelines.homelab_models` and
  `packages.domains.utilities.pipelines.utility_models` directly.
- `packages/domains/utilities/pipelines/transformation_utilities.py`: imports
  `packages.domains.finance.pipelines.contract_price_models` directly.

If neither appears, the prompt is not working correctly.

## Severity guidance

- **blocker**: New sibling-pack import introduced in the diff scope.
- **advisory**: Existing violation touched or worsened (more lines, new symbols).
- **watchlist**: Pre-existing violation unchanged in this scope.

## Output schema

Return a JSON array. One object per finding. `line` is the import statement line number.

```json
[
  {
    "specialist": "pack-boundary",
    "severity": "blocker | advisory | watchlist",
    "file": "packages/domains/finance/pipelines/scenario_service.py",
    "line": 48,
    "finding": "Finance pack imports homelab domain internals directly",
    "evidence": "from packages.domains.homelab.pipelines.homelab_models import ...",
    "recommendation": "Route through packages/domains/overview/ or a shared semantic contract",
    "blocker": false
  }
]
```

Return `[]` if no findings.
