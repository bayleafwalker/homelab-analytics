# Initial capability packs and publication set

**Status:** Proposed  
**Owner:** Juha  
**Decision type:** Product scope / capability definition  
**Applies to:** Domain packs, publication priorities, insight priorities, frontend and API consumption

---

## 1. Purpose

This document defines the first product-capable domain slices that should be treated as core.

The initial set is:

1. finance
2. utilities
3. homelab
4. cross-domain overview

Each slice should produce stable publications and a small number of useful insights.

---

## 2. Finance capability pack

### 2.1 User questions
The finance pack should answer:

- what happened to cash flow this month
- where spending is concentrated
- which costs are recurring
- what changed relative to recent months
- what transactions are unusual or newly introduced
- what fixed or likely obligations are coming up soon

### 2.2 Core source classes
Examples:

- account transactions
- card transactions
- daily balances
- loan repayment exports
- future planned repayment data where available
- subscription or recurring-payment extracts

### 2.3 Core publications

- `monthly_cashflow_summary`
- `spend_by_category_monthly`
- `subscription_summary`
- `transaction_anomalies_current`
- `account_balance_trend`
- `upcoming_fixed_costs_30d`
- `recent_large_transactions`

### 2.4 Initial insight types

- subscription spend increased materially vs trailing baseline
- new recurring-like merchant detected
- large discretionary outlier detected
- month-to-date spend exceeds recent typical pace
- fixed-cost share of inflow exceeds threshold
- current month balance trajectory looks materially weaker than recent norm

### 2.5 Product boundaries
The finance pack should not try to become a complete wealth-management suite in the initial product.

Defer:

- long-horizon portfolio analytics
- tax optimization logic
- advanced retirement simulation
- generalized budgeting workflow engine

---

## 3. Utilities capability pack

### 3.1 User questions
The utilities pack should answer:

- what I am paying now
- how utility costs changed over time
- whether a tariff or contract should be reviewed
- whether price and usage are interacting in an unusual way
- what contracts are about to expire or deserve attention

### 3.2 Core source classes
Examples:

- electricity price feeds or imported extracts
- utility invoices and statement exports
- contract-price definitions
- consumption/usage exports where available
- home energy telemetry where useful

### 3.3 Core publications

- `contract_price_current`
- `electricity_price_current`
- `utility_cost_summary`
- `usage_vs_price_summary`
- `contract_review_candidates`
- `contract_renewal_watchlist`
- `utility_cost_trend_monthly`

### 3.4 Initial insight types

- contract expires soon and should be reviewed
- effective utility cost materially increased vs recent norm
- price spike or unusual cost cluster detected
- usage shift amplified cost beyond expected range
- currently recorded contract looks uncompetitive relative to available benchmark inputs

### 3.5 Product boundaries
The utilities pack should not become a full home-energy management suite in the initial product.

Defer:

- broad appliance-level optimization
- dynamic control loops for smart-home actuation
- complex market-trading style optimization

---

## 4. Homelab capability pack

### 4.1 User questions
The homelab pack should answer:

- what is unhealthy or degraded
- whether backups are stale
- whether storage risk is rising
- which workloads are unusually noisy or costly
- what operational drift is worth attention

### 4.2 Core source classes
Examples:

- Prometheus-derived service and infrastructure metrics
- backup status exports
- storage capacity and pool health summaries
- power or energy estimates where available
- cluster/job/runtime summaries

### 4.3 Core publications

- `service_health_summary`
- `backup_freshness_summary`
- `storage_risk_summary`
- `cluster_drift_alerts`
- `top_noisy_workloads`
- `homelab_power_cost_estimate`
- `ops_attention_items`

### 4.4 Initial insight types

- backup freshness exceeded policy threshold
- storage reserve threshold at risk within forecast window
- service or workload failure rate materially increased
- workload resource profile drifted beyond recent baseline
- infrastructure cost estimate moved enough to justify review

### 4.5 Product boundaries
The homelab pack should not attempt to replace a full observability stack.

Defer:

- every-metric dashboarding
- highly granular tracing and performance analysis
- generic incident-management platform behavior

---

## 5. Cross-domain overview

### 5.1 Role
The overview is the composition layer that turns separate domain outputs into a usable operating picture.

It should not contain hidden domain logic. It should compose publications and surface the most meaningful current state, changes, and attention items.

### 5.2 Core publications

- `household_overview`
- `open_attention_items`
- `recent_significant_changes`
- `current_operating_baseline`

### 5.3 Initial composition rules
The overview should preferentially surface:

- biggest recent cost movement
- biggest recurring-spend change
- most urgent utility or contract review item
- most urgent homelab operational risk
- top three to five attention items across all domains

---

## 6. Publication quality expectations

Every core publication should have:

- a stable key
- a clear description
- an explicit schema or structural contract
- lineage back to source runs where relevant
- visibility and permission behavior
- retention expectations if persisted or mirrored
- enough semantic clarity to be consumed by multiple renderers

---

## 7. What counts as done for a domain pack

A domain pack should be treated as product-capable when:

- at least one representative source path works end to end
- the primary publications exist and are discoverable
- the primary view answers the intended user questions
- at least a small set of explainable insights exist
- reruns and updates behave predictably
- failures are understandable at the operator and user level

---

## 8. Priority order

Recommended order:

1. finance
2. utilities
3. overview composition
4. homelab

Rationale:

- finance and utilities already have meaningful implemented foundations
- overview should follow once at least two domains provide stable outputs
- homelab should enter as a focused operational slice rather than a grab-bag of metrics

---

## 9. Decision rule for future capability packs

A new capability pack should not be added because it is structurally possible.

It should be added only when:

- the user problem is recurring and concrete
- the source data is realistic to ingest and validate
- the pack can produce at least one valuable publication and one meaningful insight
- the pack improves the household operating picture rather than diluting it
