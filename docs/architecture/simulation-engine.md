# Simulation Engine — Architecture

**Status:** Active — scenario storage and three compute types shipped
**Stage:** 4 (see platform roadmap)
**First scenario type:** Loan what-if (reuses `packages/pipelines/amortization.py`)

---

## Overview

The simulation engine lets operators ask "what if?" questions against the canonical state of the household model. A scenario is a named set of **parameter overlays** applied on top of current canonical data. Compute produces a projected output mart that mirrors the structure of the canonical mart but is tagged with a scenario ID.

The engine is intentionally narrow: it overlays parameters onto existing compute, it does not re-implement the compute. Every simulation delegates to the same service layer functions used by the live pipeline.

---

## Core concepts

**Scenario** — A named, versioned set of parameter overrides with an operator-supplied label and optional expiry. Stored in `dim_scenario`.

**Assumption** — A single override record: which parameter, what value, what the baseline was. Assumptions are stored individually so the explainability layer can surface them without parsing scenario blobs.

**Projection** — The computed output of applying a scenario. Stored in mart tables prefixed `proj_` (e.g. `proj_loan_schedule`). Always tagged with `scenario_id`.

**Comparison** — A view or mart that aligns a projection against its canonical baseline for delta reporting.

---

## Storage schema

### `dim_scenario`
```sql
scenario_id     TEXT PK          -- ulid or uuid
scenario_type   TEXT             -- 'loan_what_if' | 'income_change' | 'tariff_shock'
label           TEXT             -- operator display name
description     TEXT
created_at      TIMESTAMP
expires_at      TIMESTAMP        -- NULL = no expiry
status          TEXT             -- 'active' | 'archived'
baseline_run_id TEXT             -- canonical run_id this was computed against
```

### `fact_scenario_assumption`
```sql
assumption_id   TEXT PK
scenario_id     TEXT FK → dim_scenario
parameter_key   TEXT    -- e.g. 'extra_monthly_repayment', 'annual_rate', 'income_monthly'
baseline_value  DECIMAL
override_value  DECIMAL
unit            TEXT    -- 'EUR' | 'PCT' | 'MONTHS' | etc.
applies_to_id   TEXT    -- optional: loan_id, subscription_id, etc. (NULL = global)
```

### `proj_loan_schedule`
Mirrors `mart_loan_schedule_projected` column structure, plus:
```
scenario_id     TEXT FK → dim_scenario
```

### `proj_loan_repayment_variance`
Mirrors `mart_loan_repayment_variance`, plus `scenario_id`.

### `proj_affordability_ratios`
Mirrors `mart_affordability_ratios`, plus `scenario_id`.

---

## Compute model

Scenarios are computed on-demand (not on the background worker schedule) and cached by `scenario_id` + `baseline_run_id`. If the baseline run_id has changed since the projection was last computed, the projection is stale and must be recomputed.

```
1. Operator creates scenario via API (POST /api/scenarios)
   → writes dim_scenario + fact_scenario_assumption rows

2. API computes projection synchronously for small scenarios (loan what-if)
   → calls same service layer functions with overridden parameters
   → writes proj_* rows tagged with scenario_id

3. Comparison mart assembled on read (not materialized):
   → JOIN proj_loan_schedule ON scenario_id WITH mart_loan_schedule_projected
   → delta = proj_value - canonical_value
```

For larger scenarios (income change affecting affordability + cost model), computation is deferred to the worker via a `scenario_compute` task type. The API returns 202 and a poll URL.

---

## Assumption tracking and explainability

Every projection row must be traceable to its assumptions. The `fact_scenario_assumption` table is the source of truth. The API exposes:

```
GET /api/scenarios/{id}/assumptions
→ list of {parameter_key, baseline_value, override_value, unit, applies_to_id}
```

The frontend renders this as an "Assumption summary" panel beside every scenario comparison view. No computed result is shown without its assumptions.

---

## Scenario types (planned)

### `loan_what_if`
Parameters: `extra_monthly_repayment`, `annual_rate` (refinance), `term_extension_months`
Compute: calls `compute_amortization_schedule()` with overrides
Output: `proj_loan_schedule`, `proj_loan_repayment_variance`
Comparison: months saved, interest saved, new payoff date

### `income_change`
Parameters: `income_monthly_gross`, `income_monthly_net`
Compute: re-derives `mart_affordability_ratios` with overridden income
Output: `proj_affordability_ratios`
Comparison: ratio delta, new threshold assessment

### `tariff_shock`
Parameters: `electricity_unit_rate`, `standing_charge`
Compute: re-derives `mart_household_cost_model` and `mart_cost_trend_12m` with overridden tariff
Output: `proj_cost_model`, `proj_cost_trend_12m`
Comparison: monthly delta, annual impact

---

## Implementation notes

- Scenario storage is DuckDB tables in the same database as canonical marts. No separate store needed at this scale.
- `proj_*` tables are append-only by `scenario_id`. Recomputing a scenario deletes the old projection rows for that `scenario_id` before writing new ones (not a full table truncate).
- Scenario compute must never mutate canonical mart tables. The `proj_` prefix is a hard boundary.
- The first implementation (loan what-if) should have no worker dependency — synchronous compute only. Introduce async only when a scenario takes >2s to compute.

---

## What this is not

- Not a Monte Carlo engine. Scenarios are operator-specified, not sampled.
- Not a forecast model. Projections start from current canonical state, not from a statistical prediction.
- Not a goal-setting system. Scenarios answer "what if I do X?" not "how do I reach Y?".
