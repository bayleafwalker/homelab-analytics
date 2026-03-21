# Scenarios and What-If Analysis — Product Design

**Status:** Active — three scenario types shipped (loan what-if, income change, expense shock)
**Architecture:** See [docs/architecture/simulation-engine.md](../architecture/simulation-engine.md)
**Sprint plan:** See [docs/sprints/simulation-engine-sprint.md](../sprints/simulation-engine-sprint.md)

---

## What this is

Scenarios let a household operator ask "what if?" questions against their current financial picture. A scenario applies a named set of parameter changes and shows the projected outcome side-by-side with the current baseline — without mutating any canonical data.

The operator stays in control: they define the assumption, they see the delta, they decide what to do.

---

## Scenario types

### 1. Loan what-if

The highest-value scenario type. The amortization engine already exists; this wraps it with operator-controlled overrides.

**Questions it answers:**
- "What if I pay an extra €200/month? How many months does that save?"
- "What if I refinance at a lower rate? How much interest do I save over the term?"
- "What if I extend the term by 2 years? What does that cost in total interest?"

**Operator workflow:**
1. Navigate to `/loans` → select a loan
2. Click "Run what-if"
3. Enter overrides (extra repayment, new rate, or term change)
4. View side-by-side: current schedule vs projected schedule
5. Summary panel: months saved, total interest saved/added, new payoff date

**What changes:**
- Extra repayment: recalculates amortization with increased monthly payment
- Rate change: recalculates PMT at new rate against remaining principal
- Term extension: recalculates payment amount, shows total additional interest cost

**What doesn't change:** actual canonical loan records, actual balance, actual payment history.

---

### 2. Income change

**Questions it answers:**
- "If my income drops by 20%, which ratios breach their thresholds?"
- "How much headroom do I lose if one salary disappears?"

**Operator workflow:**
1. Navigate to `/control` → Affordability card → "Run income scenario"
2. Enter new monthly net income
3. View projected affordability ratios with threshold assessments
4. Delta view: current vs projected for housing ratio, total cost ratio, debt-service ratio

---

### 3. Utility tariff shock

**Questions it answers:**
- "If electricity unit rate increases by 30%, what is the annual impact?"
- "How does the new standing charge change my monthly fixed cost?"

**Operator workflow:**
1. Navigate to `/costs` → "Run tariff scenario"
2. Enter new electricity unit rate or standing charge
3. View projected 12-month cost trend vs baseline
4. Delta: additional monthly cost, additional annual cost

---

## Comparison UX principles

Every scenario comparison view must show:

1. **Assumption summary** — what was changed and from what baseline value. No computed result without visible assumptions.
2. **Baseline column** — the current canonical value for each metric.
3. **Projected column** — the scenario-computed value.
4. **Delta column** — projected minus baseline, formatted as signed value.
5. **Scenario metadata** — label, date created, which baseline run_id it was computed against.

If the baseline has been updated since the scenario was computed, the UI must show a staleness banner: "Canonical data has changed — recompute to refresh this scenario."

---

## What scenarios are not

- **Not goals.** Scenarios answer "what if I do X?", not "how do I reach Y?". Goal-setting is a separate (future) feature.
- **Not forecasts.** Projections start from current canonical state and apply operator-specified overrides. There is no statistical model.
- **Not recommendations.** The system presents outcomes; the operator decides whether to act.
- **Not shared.** Scenarios are per-operator. There is no collaboration or sharing surface in the first version.

---

## Acceptance criteria for v1 (loan what-if only)

- Operator can create a loan what-if scenario from the `/loans` page.
- Extra repayment scenario shows: months saved, interest saved, new payoff date.
- Rate change scenario shows: new monthly payment, total interest delta.
- Comparison view is readable without the operator needing to understand the underlying amortization model.
- Creating a scenario does not mutate any canonical mart data.
- Stale scenario banner appears when canonical data has been refreshed after scenario creation.
