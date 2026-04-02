# Category Governance — Architecture

**Classification:** PLATFORM

**Status:** implemented baseline; broader cross-domain adoption remains open
**Stage:** 1 semantic-domain governance
**Tracker:** `CategoryGovernancePhase2Tests` in `tests/test_household_complete_integration.py`

## Current state

`dim_category` is now the platform-owned shared category dimension for finance and
budget flows.

The current baseline includes:

- category rules and overrides for transaction-side categorisation
- SCD-safe backfill of current `dim_counterparty` categories
- the full `dim_category` contract shape, including `domain`,
  `is_budget_eligible`, and `is_system`
- startup seeding of system categories through `packages/pipelines/category_seed.py`
- budget ingestion and marts keyed by `category_id`, not free-text category names
- operator category routes through `GET /api/categories` and `POST /api/categories`

## Contract boundary

Category identity is shared at the platform layer because more than one domain
needs the same canonical concept.

The contract rules are:

- `category_id` is the stable natural key
- system categories are immutable seeded slugs
- operators may add non-system sub-categories
- transaction rules and overrides assign categories before reporting marts refresh
- budgets and spend-facing marts join on canonical `category_id`

This keeps finance categorisation and budget attribution on the same semantic
surface instead of relying on text matching.

## What remains open

The category baseline does not imply that every repeated label should become a
shared dimension.

Remaining Stage 1 governance work is to:

- document shared-dimension promotion rules for future candidates such as
  `dim_household_member`
- keep provider identity attribute-level until multiple domains require a true
  shared provider dimension
- decide where utilities, homelab, and future planning models should reference
  categories directly instead of carrying domain-local labels
- add better operator-facing remediation for ambiguous category mapping if that
  becomes a product requirement

## Guardrails

- Do not fork `dim_category` into per-domain copies.
- Do not bypass `category_id` with free-text joins in new reporting logic.
- Do not treat provider strings as proof that a new shared dimension is needed.
- Keep app-facing reads on reporting-layer outputs and current-dimension views.
