# Pipeline Ambiguity Classification

**Classification:** CROSS-CUTTING
**Status:** accepted
**Last updated:** 2026-04-02

This note closes WP-1e for the current seam pass by classifying the remaining
ambiguous files still living under `packages/pipelines/`.

## Current classification

| File | Classification | Rationale |
| --- | --- | --- |
| `packages/pipelines/asset_models.py` | APP | Defines household asset dimensions and marts consumed by household reporting surfaces. |
| `packages/pipelines/asset_register.py` | APP | Normalizes household asset payloads and identity fields; not a generic kernel primitive. |
| `packages/pipelines/asset_register_service.py` | APP | Service wrapper over household asset registration flows and dataset contracts. |
| `packages/pipelines/transformation_assets.py` | APP | Asset-domain transform/load path for household asset publications. |
| `packages/pipelines/contracts.py` | JUSTIFIED-MIXED | Small reusable contract-id helper still shared by multiple domain modules; kept in `packages/pipelines/` temporarily until a dedicated shared/domain-neutral home is selected. |

## Working rule

Until an `assets` domain package or a stable shared helper module is approved,
the above files may remain in `packages/pipelines/` only under this explicit
classification, and future boundary work should either:

1. move APP files into a domain-local package, or
2. move JUSTIFIED-MIXED helpers into a domain-neutral shared/kernel location.
