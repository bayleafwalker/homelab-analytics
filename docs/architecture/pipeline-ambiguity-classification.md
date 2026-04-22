# Pipeline Ambiguity Classification

**Classification:** CROSS-CUTTING
**Status:** accepted
**Last updated:** 2026-04-22

This note closes WP-1e for the current seam pass by classifying the remaining
ambiguous files still living under `packages/pipelines/`.

## Current classification

| File | Classification | Rationale |
| --- | --- | --- |
| `packages/domains/finance/pipelines/asset_models.py` | APP (moved) | Defines household asset dimensions and marts. Moved from `packages/pipelines/` in sprint #56 (WP-1a); shim retired in sprint #57. |
| `packages/domains/finance/pipelines/asset_register.py` | APP (moved) | Normalizes household asset payloads. Moved in sprint #56; shim retired in sprint #57. |
| `packages/domains/finance/pipelines/asset_register_service.py` | APP (moved) | Service wrapper over household asset registration. Moved in sprint #56; shim retired in sprint #57. |
| `packages/domains/finance/pipelines/transformation_assets.py` | APP (moved) | Asset-domain transform/load path. Moved in sprint #56; shim retired in sprint #57. |
| `packages/pipelines/contracts.py` | JUSTIFIED-MIXED | Small reusable contract-id helper still shared by multiple domain modules; kept in `packages/pipelines/` until a dedicated domain-neutral home is selected. |

## Working rule

The APP files above have completed their migration to `packages/domains/finance/pipelines/`
and their compatibility shims have been removed. Future boundary work should:

1. move any remaining APP files in `packages/pipelines/` into the appropriate domain package, or
2. move JUSTIFIED-MIXED helpers into a domain-neutral shared/kernel location.
