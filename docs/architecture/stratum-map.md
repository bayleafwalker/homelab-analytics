# Stratum Map

**Classification:** CROSS-CUTTING
**Status:** living
**Last updated:** 2026-04-14

This map records the current best-effort assignment of `packages/` directories to the
four stability strata defined in `docs/architecture/data-platform-architecture.md`.
It is a living review resource, not a load-bearing runtime contract. The stratum-coherence
and repetition-vs-abstraction review specialists use it as their primary classification
reference. When strata assignments change, update this file first.

---

## Strata

| Stratum | Description |
|---|---|
| **Kernel** | Runtime, config, auth primitives, control-plane stores, scheduling, capability/publication/UI descriptor types, extension loading, audit and lineage primitives. Should still make sense if every product pack vanished. |
| **Semantic engine** | Canonical facts and dimensions, ingestion-to-promotion orchestration, transformation registries, publication materialization, reporting access contracts, scenario storage and compute, policy evaluation primitives. |
| **Product packs** | Finance, utilities, homelab, and overview. Source definitions, pack workflows, publication definitions, pack-local transformation/reporting rules, heuristics, and optional UI descriptors. |
| **Surfaces** | API, worker, web, Home Assistant, exports, Prometheus, admin views. Thin: accept requests, auth/authz, call use-case entrypoints, serialize/render/publish. |

---

## Directory-to-stratum assignment

| Package | Stratum | Notes |
|---|---|---|
| `packages/platform/` | Kernel | Auth primitives, permission registry, capability/publication/UI descriptor types, OIDC provider. |
| `packages/shared/` | Kernel | Settings, external registry, extensions, function registry, shared auth helpers. |
| `packages/storage/` | Kernel | Control-plane stores (SQLite + Postgres), provenance, scheduling, dispatch claiming, audit. |
| `packages/adapters/` | Kernel (contracts/registry/runtime) + Surfaces (adapter implementations) | `contracts.py`, `registry.py`, `renderer_router.py`, `compatibility.py` are kernel-level. Concrete HA adapters are surface-facing. |
| `packages/domains/finance/` | Product pack | Finance source definitions, transformation, scenarios, OP contract parsers, invoice PDF parsers. |
| `packages/domains/utilities/` | Product pack | Utilities source definitions, transformation, contract prices, tariff models. |
| `packages/domains/homelab/` | Product pack | Homelab source definitions, HA bridge ingestion, homelab models. |
| `packages/domains/overview/` | Product pack | Cross-domain composition and reporting. Overview is the one product pack that intentionally imports from sibling packs; all other sibling-pack cross-imports are violations unless routed through overview or a shared contract. Includes `scenario_models_overview.py` (cross-domain result types) and `scenario_service_overview.py` (homelab cost/benefit and tariff-shock scenario builders). |
| `packages/application/` | Surfaces | Use-case entrypoints (`run_ingestion`, `promote_run`, `publish_outputs`, `compute_scenario`, etc.). Mandatory orchestration seam between semantic engine/product packs and surfaces. |
| `packages/pipelines/` | **Transitional** | See `docs/architecture/pipeline-ambiguity-classification.md`. The classified files (APP, JUSTIFIED-MIXED) are assigned to product-pack or kernel strata individually. The legacy re-export cluster (`from ... import * # noqa: F403`) is a seam-reduction-in-flight hot spot, not an architectural stratum. New files added here must carry an explicit classification before they are merged. |
| `packages/analytics/` | **Ambiguous / scaffold** | 52 LOC total. `cashflow.py` imports `CanonicalTransaction` from finance domain internals, which makes it behave like finance-pack-internal code. However, the package name suggests cross-cutting intent. This ambiguity is unresolved. Do not add new code here without first deciding whether this package belongs in the semantic engine (cross-cutting kernel helper) or in the finance product pack (pack-internal). The stratum-coherence specialist will flag any addition until the ambiguity is resolved. |
| `packages/connectors/` | **Ambiguous / scaffold** | README-only scaffold with no Python source. Not yet assigned to any stratum. Do not add code here without registering the package purpose and stratum assignment in this file. |
| `packages/demo/` | Out-of-band | Demo and seeding utilities. Not part of the production stratum model. |

---

## Known violations tracked by specialists

The following cross-pack imports violate the product-pack isolation rule (sibling packs should
not import each other directly except through `packages/domains/overview/` or a shared semantic
contract). They pre-date this map and are flagged as watchlist items on every review pass.

| File | Violation |
|---|---|
| `packages/domains/utilities/pipelines/transformation_utilities.py` | Imports `packages.domains.finance.pipelines.contract_price_models` directly. Historical ownership mismatch — contract prices appear in the utilities pack manifest but the model lives under finance. |
| `packages/analytics/cashflow.py` | Imports `CanonicalTransaction` from finance domain internals. Stratum ambiguity unresolved. |

---

## How to update this map

1. When a new `packages/` directory is created, add a row here in the same PR.
2. When a package moves from ambiguous to an assigned stratum, update the row and remove it from the
   "Ambiguous / scaffold" stratum, and remove the blocker note from the stratum-coherence specialist's
   first-run guidance.
3. When a known violation is remediated, remove it from the violations table above.
4. Classification changes require at minimum an ADR or a note in the relevant decision doc.
