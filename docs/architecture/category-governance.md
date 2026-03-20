# Category Governance — Architecture

**Status:** Design only — not started
**Stage:** 2 cross-cutting concern (blocks full budget-vs-spend alignment)
**Tracker:** `test_budget_categories_overlap_with_spend_categories` is currently skipped in `tests/test_household_complete_integration.py` pending this work

---

## Problem

`dim_category` currently exists as a per-transaction override table seeded by category enrichment in `category_rules.py`. Budgets reference category names as free-text strings. Spend categories come from transaction enrichment. The two sides can diverge silently:
- A budget for "Groceries" and a transaction tagged "groceries" count as different categories
- There is no canonical category registry that both sides reference by ID
- The cross-domain integration test that checks budget/spend overlap is skipped because categories are NULL without explicit rules

---

## Goal

Promote `dim_category` to a **shared cross-domain dimension** owned at the platform level. All domains (finance, budgets, utilities, homelab) reference categories by canonical ID. Category assignment to transactions happens at promotion time using a priority-ordered rule set.

---

## Canonical `dim_category` schema

```sql
category_id     TEXT PK          -- stable slug: 'groceries', 'utilities_electricity', etc.
display_name    TEXT             -- human label: "Groceries", "Electricity"
parent_id       TEXT FK → dim_category  -- NULL for top-level; enables hierarchy
domain          TEXT             -- 'finance' | 'utilities' | 'homelab' | 'shared'
is_budget_eligible BOOLEAN       -- can a budget be created against this category?
is_system       BOOLEAN          -- TRUE = seeded by platform, cannot be deleted by operator
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

Top-level categories are system-seeded. Operators can create sub-categories but cannot delete system categories.

---

## Category rule schema

Category rules live in `dim_category_rule` and are applied in priority order at promotion time.

```sql
rule_id         TEXT PK
category_id     TEXT FK → dim_category
priority        INT             -- lower = evaluated first; first match wins
match_field     TEXT            -- 'merchant_name' | 'description' | 'amount_range' | 'account_id'
match_operator  TEXT            -- 'contains' | 'equals' | 'starts_with' | 'regex' | 'between'
match_value     TEXT            -- the value to match against
is_active       BOOLEAN
created_at      TIMESTAMP
```

Rules are applied in `transformation_transactions.py` at the canonical promotion step, after raw transaction enrichment. Manual overrides (already in the system as `category_override`) always win over rules.

---

## Seeding

System categories are seeded in `packages/pipelines/category_seed.py`:

```python
SYSTEM_CATEGORIES = [
    Category(id="housing", display_name="Housing", domain="shared", is_system=True),
    Category(id="utilities_electricity", display_name="Electricity", parent_id="utilities", ...),
    Category(id="utilities_gas", display_name="Gas", parent_id="utilities", ...),
    Category(id="groceries", display_name="Groceries", domain="finance", ...),
    Category(id="transport", display_name="Transport", domain="finance", ...),
    Category(id="subscriptions", display_name="Subscriptions", domain="finance", ...),
    # ... etc
]
```

Seeding runs as part of `migrate` / `init` workflow, before any transformation step. It is idempotent (upsert by `category_id`).

---

## Budget → category alignment

Budgets currently store `category_name: str`. After this change:
- `dim_budget` gains `category_id TEXT FK → dim_category` (replacing the free-text field)
- Budget upload (`budget_service.py`) resolves category name → category_id at landing time, using a fuzzy match with operator confirmation on ambiguity
- `mart_budget_variance` joins on `category_id`, not on string comparison

This is the change that unblocks `test_budget_categories_overlap_with_spend_categories`.

---

## Operator API

```
GET  /api/categories               → list all dim_category entries
POST /api/categories               → create operator sub-category
GET  /api/categories/{id}/rules    → list rules for a category
POST /api/categories/{id}/rules    → add a rule
PUT  /api/categories/{id}/rules/{rule_id}  → update priority or match
DELETE /api/categories/{id}/rules/{rule_id}
```

No UI for rule management in the first version — API only. Rules can be authored and prioritised via API calls or a future rules editor.

---

## Implementation sequence

1. `packages/pipelines/category_seed.py` — system category definitions + upsert function
2. Migrate `dim_category` schema in DuckDB init path
3. `dim_category_rule` table + schema
4. Update `transformation_transactions.py` promotion step to apply rules against `dim_category_rule`
5. Migrate `dim_budget.category_name → category_id` + update `budget_service.py` resolver
6. Update `mart_budget_variance` and `mart_budget_progress_current` to join on `category_id`
7. `apps/api/routes/category_routes.py` — list + rule CRUD
8. Un-skip `test_budget_categories_overlap_with_spend_categories`
9. Add integration assertions: all budget category_ids exist in `dim_category`

---

## Guardrails

- System categories are immutable. Operators can add sub-categories but cannot rename or delete system ones.
- Category IDs are stable slugs. Do not use auto-increment integers — they break fixture reproducibility.
- Rule application is deterministic: lowest priority number wins, tie-breaks by `rule_id` alphabetically.
- Manual overrides (`category_override` table) always win over rules. Do not merge them into the rules system.
- Do not attempt ML categorisation in this sprint. Rule-based is sufficient and auditable.
- The budget category resolver must surface ambiguous matches to the operator rather than silently picking one.
