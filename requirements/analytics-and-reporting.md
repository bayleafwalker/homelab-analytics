# Analytics and Reporting Requirements

## Overview

The platform derives household and homelab analytics from normalized canonical models. Derived outputs include financial projections, budget tracking, utility cost analysis, and infrastructure profitability assessments. All analytics are published as reporting-layer marts, served through both dashboards and APIs.

---

## Requirements

### ANA-01: Monthly household cash-flow

**Description:** Produce monthly summaries of household income, expenses, and net cash flow from canonical transaction data. Breakdowns by category and counterparty.

**Rationale:** Cash-flow overview is the primary household financial dashboard.

**Phase:** 1
**Status:** implemented (`mart_monthly_cashflow`, `mart_monthly_cashflow_by_counterparty`, and `mart_spend_by_category_monthly` are materialised; API exposes `GET /reports/monthly-cashflow`, `GET /reports/monthly-cashflow-by-counterparty`, and `GET /reports/spend-by-category-monthly`; the Next.js dashboard and reports surfaces now render summary cards, trend charts, and category/counterparty detail from reporting-layer models)

**Acceptance criteria:**
- Mart contains: month, total income, total expense, net, transaction count.
- Breakdowns by `dim_category` and `dim_counterparty` are available.
- API endpoint returns monthly cash-flow data with date-range filtering.
- Dashboard displays trend chart and summary cards.
- Tests verify aggregation from fixture transactions.

**Dependencies:** PLT-05, PLT-12

---

### ANA-02: Loan repayment projections

**Description:** Calculate planned loan repayment schedules (amortization tables) and compare against actual repayment records. Inputs: loan principal, interest rate, term, repayment frequency, extra repayment amounts.

**Rationale:** Loan tracking is a core household financial planning need. Projection vs. actual comparison reveals early/late repayment impact.

**Phase:** 3
**Status:** implemented (loan-repayment ingestion now populates `dim_loan` and `fact_loan_repayment`; `mart_loan_schedule_projected`, `mart_loan_repayment_variance`, and `mart_loan_overview` are materialised; API exposes `GET /reports/loan-overview`, `GET /reports/loan-schedule/{loan_id}`, and `GET /reports/loan-variance`, and scenario APIs reuse the same amortization foundation for loan what-if calculations)

**Acceptance criteria:**
- Amortization engine produces a schedule from loan parameters (principal, rate, term, frequency).
- Schedule includes: period, payment, principal portion, interest portion, remaining balance.
- Extra repayments are incorporated and recalculate remaining schedule.
- Mart compares projected schedule against `fact_loan_repayment` actuals.
- API exposes loan projection and variance data.
- Tests verify calculation accuracy against known amortization results.

**Dependencies:** PLT-05 (`fact_loan_repayment`), PLT-06 (`dim_loan`)

---

### ANA-03: Budget derivations and variance

**Description:** Support user-defined budget categories and periods. Classify actual spending against budget targets and produce variance reports.

**Rationale:** Budget vs. actual tracking is the most requested household finance feature after cash-flow.

**Phase:** 3
**Status:** implemented (budget ingestion now populates `dim_budget` plus budget-target facts; `mart_budget_variance`, `mart_budget_envelope_drift`, and `mart_budget_progress_current` are materialised; API exposes `GET /reports/budget-variance`, `GET /reports/budget-envelopes`, and `GET /reports/budget-progress`; the web budget surface renders progress, envelope drift, and variance views from reporting-layer models)

**Acceptance criteria:**
- Budget definitions specify: category, period (monthly/quarterly/annual), and target amount.
- Actual spending is classified by matching `dim_category` assignments.
- Variance mart shows: budget, actual, variance (absolute and percentage) per category and period.
- Envelope mart shows drift visibility with a state indicator and percentage drift alongside target vs. actual spend.
- API exposes budget status and variance data.
- Dashboard displays budget progress bars or gauges.
- Tests verify variance calculation from fixture budgets and transactions.

**Dependencies:** PLT-06 (`dim_budget`, `dim_category`), PLT-10

---

### ANA-04: Household cost modeling

**Description:** Aggregate all cost streams — utilities, loans, subscriptions, discretionary spending — into a unified household cost model trackable over time.

**Rationale:** Total cost of living is difficult to derive from scattered source data. A unified model enables trend analysis and affordability assessment.

**Phase:** 3
**Status:** implemented (`mart_household_cost_model` and 12-month cost-trend outputs aggregate finance, utilities, subscriptions, and loans; API exposes `GET /reports/household-cost-model` and `GET /reports/cost-trend`; the web costs surface renders cost-type breakdowns and trend views from those reporting models)

**Acceptance criteria:**
- Cost summary mart aggregates by cost type (housing, utilities, transport, food, subscriptions, other).
- Monthly and annual totals are materialized.
- Cost type classification uses `dim_category` assignments.
- Historical trend data is available for at least 12-month windows.
- Tests verify aggregation from mixed-source fixture data.

**Dependencies:** ANA-01, ANA-03, PLT-05

---

### ANA-05: Electricity and utility cost summaries

**Description:** Produce periodic summaries (daily, monthly, yearly) of electricity and utility costs, correlating usage data with billing data where both are available.

**Rationale:** Electricity is typically the most variable household cost. Correlating metered usage with billed amounts enables anomaly detection and efficiency tracking.

**Phase:** 3
**Status:** implemented (`fact_utility_usage`, `fact_bill`, `mart_utility_cost_summary`, and `utility_cost_trend_monthly` are materialised; API exposes `GET /reports/utility-cost-summary` and `GET /reports/utility-cost-trend`; dashboard and utility-report surfaces now render cost and usage trend views from reporting-layer models)

**Acceptance criteria:**
- Utility mart joins `fact_utility_usage` and `fact_bill` by meter and billing period.
- Summaries include: period, usage quantity, usage unit, billed amount, unit cost.
- Multiple meters and utility types are supported.
- Dashboard displays usage and cost trend charts.
- Tests verify join and aggregation from fixture usage and billing data.

**Dependencies:** PLT-05 (`fact_utility_usage`, `fact_bill`), PLT-06 (`dim_meter`)

---

### ANA-06: Profitability and affordability assessments

**Description:** Support simple profitability models: homelab electricity cost vs. value of self-hosted services, total housing cost vs. income ratio, and similar comparisons.

**Rationale:** These models help household operators make informed decisions about infrastructure spending and living arrangements.

**Phase:** 3
**Status:** implemented (`mart_affordability_ratios` and `mart_recurring_cost_baseline` are materialised from finance, utility, subscription, and loan data; API exposes `GET /reports/affordability-ratios` and `GET /reports/recurring-cost-baseline`; the dashboard renders affordability cards and recurring-baseline views; the homelab value-loop operator panel now surfaces reporting-layer service-health, workload-cost summaries, a formal homelab ROI report, a derived value-versus-cost comparison signal, a saved homelab cost/benefit scenario summary, a saved-scenario compare page, and shared saved compare sets)

**Acceptance criteria:**
- At least two profitability models are implemented: homelab ROI and housing affordability ratio.
- Models compute from existing facts and dimensions — no new ingestion sources required.
- Results are exposed via API and dashboard.
- Tests verify model calculations from fixture data.

**Dependencies:** ANA-01, ANA-04, ANA-05

---

### ANA-07: Recurring cost identification

**Description:** Automatically identify and baseline recurring charges and subscriptions from transaction history.

**Rationale:** Recurring costs are often invisible until aggregated. Automated identification surfaces subscription creep and fixed cost baselines.

**Phase:** 3
**Status:** in-progress (`mart_subscription_summary` provides explicit subscription tracking with monthly-equivalent normalisation and active/inactive status; transaction-history auto-detection algorithm not yet started)

**Acceptance criteria:**
- Algorithm identifies transactions with similar counterparty, amount, and frequency.
- Recurring items are surfaced with: counterparty, average amount, detected frequency, first/last occurrence.
- Users can confirm, reject, or adjust identified recurring costs.
- Tests verify detection from fixture transactions with known recurring patterns.

**Dependencies:** PLT-05 (`fact_transaction`, `fact_subscription_charge`), PLT-06 (`dim_counterparty`, `dim_contract`)

---

### ANA-08: Home Assistant-compatible metrics

**Description:** Expose selected analytics measures in formats compatible with Home Assistant REST sensor integration.

**Rationale:** Home Assistant is the most common homelab automation platform. Direct metric exposure enables dashboard integration and automation triggers.

**Phase:** 3
**Status:** in-progress (HA state ingest/query routes, contract-based HA renderer metadata, and MQTT synthetic-entity publication are implemented; reporting-backed HA summary states can be rendered through `HaContractRenderer`, but dedicated REST-sensor `{\"value\", \"unit\"}` endpoints for household finance measures are still pending)

**Acceptance criteria:**
- API endpoints return simple JSON key-value responses (e.g. `{"value": 1234.56, "unit": "EUR"}`).
- At least: current month net cash flow, current month electricity cost, next loan payment amount.
- Response format is compatible with Home Assistant REST sensor configuration.
- Tests verify response format.

**Dependencies:** ANA-01, ANA-05, ANA-02

---

### ANA-09: Current contract and tariff views

**Description:** Publish the currently active contract price rows and electricity tariff components for API and dashboard consumption.

**Rationale:** Household and homelab planning often starts from current contractual pricing before realised bills or transactions exist. A stable current-price view supports electricity cost estimation, subscription comparisons, and contract review workflows.

**Phase:** 2
**Status:** implemented (`mart_contract_price_current` and `mart_electricity_price_current` are materialised in DuckDB and exposed via `GET /reports/contract-prices` and `GET /reports/electricity-prices`)

**Acceptance criteria:**
- Current contract-price mart returns only currently active price rows.
- Electricity-price mart is a filtered publication over the same canonical contract-pricing fact model.
- API endpoints expose both views with basic filtering.
- Tests verify mart content and API responses from fixture data.

**Dependencies:** PLT-05 (`fact_contract_price`), PLT-06 (`dim_contract`), PLT-12

---

## Traceability

| Requirement | Architecture doc section | Implementation module | Test file |
|---|---|---|---|
| ANA-01 | Reporting | `packages/pipelines/transformation_transactions.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py`, `apps/api/routes/report_routes.py`, `apps/web/frontend/app/page.js`, `apps/web/frontend/app/reports/page.js` | `tests/test_transformation_service.py`, `tests/test_reporting_api_app.py`, `tests/test_api_app.py` |
| ANA-02 | Reporting | `packages/pipelines/loan_service.py`, `packages/pipelines/transformation_loans.py`, `packages/pipelines/transformation_service.py`, `apps/api/routes/report_routes.py`, `apps/api/routes/scenario_routes.py` | `tests/test_loan_domain.py`, `tests/test_scenario_service.py`, `tests/test_scenario_api.py`, `tests/test_household_complete_integration.py` |
| ANA-03 | Reporting | `packages/pipelines/budget_service.py`, `packages/pipelines/transformation_budgets.py`, `packages/pipelines/transformation_service.py`, `apps/api/routes/report_routes.py`, `apps/web/frontend/app/budgets/page.js` | `tests/test_budget_domain.py`, `tests/test_household_complete_integration.py`, `tests/test_reporting_api_app.py` |
| ANA-04 | Reporting | `packages/pipelines/transformation_overview.py`, `packages/pipelines/transformation_service.py`, `apps/api/routes/report_routes.py`, `apps/web/frontend/app/costs/page.js` | `tests/test_transformation_overview.py`, `tests/test_household_complete_integration.py` |
| ANA-05 | Reporting | `packages/pipelines/utility_models.py`, `packages/pipelines/transformation_utilities.py`, `packages/pipelines/transformation_service.py`, `apps/api/routes/report_routes.py`, `apps/web/frontend/app/utilities/page.js` | `tests/test_utility_domain.py`, `tests/test_sprint1_dashboard.py`, `tests/test_reporting_api_app.py` |
| ANA-06 | Reporting | `packages/pipelines/transformation_overview.py`, `packages/pipelines/transformation_service.py`, `packages/pipelines/reporting_service.py`, `apps/api/routes/report_routes.py`, `apps/web/frontend/app/page.js`, `apps/web/frontend/app/homelab/page.js` | `tests/test_household_complete_integration.py`, `tests/test_transformation_overview.py`, `tests/test_reporting_api_app.py`, `tests/test_web_auth.py` |
| ANA-07 | Reporting | `packages/pipelines/subscription_models.py`, `packages/pipelines/transformation_service.py` | `tests/test_subscription_domain.py` |
| ANA-08 | API and dashboard publication | `packages/pipelines/ha_contract_renderer.py`, `packages/pipelines/ha_mqtt_publisher.py`, `apps/api/routes/ha_routes.py`, `apps/api/main.py` | `tests/test_ha_contract_renderer.py`, `tests/test_ha_mqtt_publisher.py`, `tests/test_ha_api.py` |
| ANA-09 | Reporting | `packages/pipelines/contract_price_models.py`, `packages/pipelines/transformation_service.py`, `apps/api/app.py`, `apps/worker/main.py` | `tests/test_contract_price_domain.py`, `tests/test_api_app.py`, `tests/test_worker_cli.py` |
