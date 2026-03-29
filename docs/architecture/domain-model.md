# Domain Model

Canonical household ontology for the platform. Documents every shipped dimension and its domain ownership, natural key, and governance notes.

For governance rules governing shared dimensions and publication contracts, see [`semantic-contracts.md`](semantic-contracts.md).

For finance-specific ingestion lineage, see [`finance-ingestion-model.md`](finance-ingestion-model.md).

---

## Dimension ownership

Each dimension belongs to exactly one domain pack. Shared dimensions are promoted to platform level and may be referenced across domain packs; domain-local dimensions are defined and owned by one pack.

| Table | Domain | Type | Natural key | Notes |
|---|---|---|---|---|
| `dim_category` | Shared | SCD-2 | `category_id` | Canonical category registry; used across budgets, transactions, and cost attribution. System categories seeded at startup. |
| `dim_counterparty` | Shared | SCD-2 | `counterparty_name` | Finance-facing counterparty spine. `category_id` FK populated via backfill from `dim_category`; free-text `category` bridge retained for backward compat. |
| `dim_contract` | Shared | SCD-2 | `contract_id` | Contract/provider spine shared by subscriptions and contract-pricing flows. |
| `dim_meter` | Shared | SCD-2 | `meter_id` | Utility metering spine shared by usage and billing domains. |
| `dim_household_member` | Shared | SCD-2 | `member_id` | Canonical household-member dimension. Default `household` member seeded at startup. Enables attribution of transactions, assets, loans, and subscriptions to individuals. |
| `dim_account` | Finance | SCD-2 | `account_id` | Bank/payment account registry. Owned by the transaction domain. |
| `dim_loan` | Finance | SCD-2 | `loan_id` | Loan spine for the amortization and repayment domains. |
| `dim_budget` | Finance | SCD-2 | `budget_id` | Budget definition; links to `dim_category` for envelope attribution. |
| `dim_asset` | Assets | SCD-2 | `asset_id` | Physical and financial asset inventory. |
| `dim_node` | Infrastructure | SCD-2 | `node_id` | Homelab cluster node (server/VM). |
| `dim_device` | Infrastructure | SCD-2 | `device_id` | Network/hardware device. |
| `dim_service` | Homelab | SCD-2 | `service_id` | Homelab service (container, daemon, external). |
| `dim_workload` | Homelab | SCD-2 | `workload_id` | Homelab workload group for cost and utilisation attribution. |
| `dim_entity` | Home Automation | SCD-2 | `entity_id` | Home Assistant entity normalised from HA bridge ingestion. |

---

## Fact and mart overview

Facts are domain-local unless noted. Marts are denormalized read-optimised projections refreshed on demand.

### Finance

| Table | Kind | Grain |
|---|---|---|
| `fact_transaction` | Fact | One row per transaction observation (immutable, append-only) |
| `fact_transaction_current` | Mart | Reconciled current projection; one row per canonical entity key |
| `transaction_observation` | Staging | Raw observation record per ingest run |
| `ingest_batch` | Lineage | Content-addressed ingest batch; links file → observations |
| `transaction_entity` | Lineage | Stable entity key per identity-strategy resolution |
| `mart_monthly_cashflow` | Mart | Monthly income/expense/net |
| `mart_monthly_cashflow_by_counterparty` | Mart | Monthly cashflow broken down by counterparty |
| `mart_spend_by_category_monthly` | Mart | Monthly spend broken down by category |
| `mart_recent_large_transactions` | Mart | Transactions above threshold in recent window |
| `mart_account_balance_trend` | Mart | Account-level balance trend |
| `mart_transaction_anomalies_current` | Mart | Current anomaly flags |
| `mart_budget_envelope_drift` | Mart | Category envelope allocation vs spend with state indicator |

### Loans

| Table | Kind | Grain |
|---|---|---|
| `fact_loan_repayment` | Fact | One row per repayment event |
| `mart_loan_overview` | Mart | Current loan status per loan |
| `mart_loan_repayment_variance` | Mart | Repayment vs schedule variance |
| `mart_loan_schedule_projected` | Mart | Amortization projection |

### Utilities

| Table | Kind | Grain |
|---|---|---|
| `fact_utility_usage` | Fact | One row per metered usage reading |
| `fact_bill` | Fact | One row per utility bill |
| `fact_contract_price` | Fact | One row per contracted rate |
| `mart_utility_cost_summary` | Mart | Cost summary per meter/provider |
| `mart_utility_cost_trend_monthly` | Mart | Monthly utility cost trend |
| `mart_contract_renewal_watchlist` | Mart | Contracts approaching renewal |

### Assets

| Table | Kind | Grain |
|---|---|---|
| `fact_asset_valuation` | Fact | Point-in-time asset value record |

### Homelab / Infrastructure

| Table | Kind | Grain |
|---|---|---|
| `fact_service_health` | Fact | Service health check reading |
| `fact_backup_run` | Fact | Backup job run record |
| `fact_storage_sensor` | Fact | Storage utilisation sensor reading |
| `fact_workload_sensor` | Fact | Workload resource utilisation reading |
| `fact_cluster_metric` | Fact | Cluster-level resource metric |
| `fact_power_consumption` | Fact | Device power draw reading |

### Home Automation

| Table | Kind | Grain |
|---|---|---|
| `fact_sensor_reading` | Fact | HA sensor state reading |
| `fact_automation_event` | Fact | HA automation event |
| `dim_ha_entity` | Dimension | HA entity live state (managed by HA bridge ingest) |

---

## Shared dimension governance

Rules for extending shared dimensions are in [`semantic-contracts.md`](semantic-contracts.md). Key principles:

- Shared dimensions are defined once and reused across domain packs; do not create parallel per-domain copies.
- When a shared dimension gains new attribute columns, update the `DimensionDefinition` constant and create a migration; the `ensure_dimension` SCD-2 helper will add columns to existing databases.
- New shared dimensions should be added to this doc and `semantic-contracts.md` in the same change that ships the implementation.
- Domain-local dimensions should only be promoted to shared status through a deliberate sprint with explicit scope.

---

## Reporting layer

Every dimension has a `rpt_current_dim_*` view that exposes only current (`is_current = TRUE`) rows and business columns. These views are the authoritative app-facing read surface; do not add landing-to-dashboard shortcuts that bypass the reporting layer.

Current views:

| View | Source |
|---|---|
| `rpt_current_dim_category` | `dim_category` |
| `rpt_current_dim_counterparty` | `dim_counterparty` |
| `rpt_current_dim_contract` | `dim_contract` |
| `rpt_current_dim_meter` | `dim_meter` |
| `rpt_current_dim_household_member` | `dim_household_member` |
| `rpt_current_dim_account` | `dim_account` |
| `rpt_current_dim_loan` | `dim_loan` |
| `rpt_current_dim_budget` | `dim_budget` |
| `rpt_current_dim_asset` | `dim_asset` |
| `rpt_current_dim_node` | `dim_node` |
| `rpt_current_dim_device` | `dim_device` |
| `rpt_current_dim_service` | `dim_service` |
| `rpt_current_dim_workload` | `dim_workload` |
| `rpt_current_dim_entity` | `dim_entity` |
