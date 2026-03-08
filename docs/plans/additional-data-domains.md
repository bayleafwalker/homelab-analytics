# Additional Data Domains — Homelab Analytics

## Purpose

This document maps out data domains beyond the initial account-transaction
domain.  Each domain is described by its source systems, landing contract,
canonical models (facts and dimensions), and planned marts.  Domains are
ordered by practical value and implementation readiness.

---

## Domain 1: Utility Consumption and Billing

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Electricity provider CSV export (e.g. Helen) | CSV | Manual upload / API | 2–3 |
| District heating provider export | CSV | Manual upload | 3 |
| Water utility export | CSV | Manual upload | 3 |
| Home Assistant energy sensors | REST API → JSON | API pull | 3 |
| Smart meter P1 / pulse data (via HA) | REST API → JSON | API pull | 3 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_utility_usage` | Fact | Metered consumption: timestamp, meter, reading, delta, unit (kWh, m³, MWh) |
| `fact_bill` | Fact | Invoiced charges: period, provider, amount, currency, line items |
| `dim_meter` | Dimension (SCD-2) | Meter identifier, type, location, provider |
| `dim_provider` | Dimension (SCD-2) | Utility provider name, contract reference |

### Marts
- `mart_monthly_utility_cost` — monthly cost by utility type and provider.
- `mart_usage_vs_billing` — correlate metered usage with billed amounts.
- `mart_energy_daily` — daily electricity/heating breakdown.

### Landing contract sketch
```
meter_id, timestamp, reading, unit, source_system
```

---

## Domain 2: Infrastructure and Cluster Metrics

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Prometheus query API | JSON | API pull (PromQL) | 3 |
| Kubernetes resource metrics | JSON | API / kubectl | 3 |
| UPS / PDU SNMP data | JSON via collector | API pull | 4 |
| Network switch statistics | JSON via collector | API pull | 4 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_cluster_metric` | Fact | Time-series: timestamp, node, metric_name, value, unit |
| `fact_power_consumption` | Fact | Sampled power draw: timestamp, device, watts |
| `dim_node` | Dimension (SCD-2) | Cluster node: hostname, role, CPU, RAM, OS |
| `dim_device` | Dimension (SCD-2) | Physical device: name, type, location, power_rating |

### Marts
- `mart_infra_cost` — monthly infrastructure electricity and amortised hardware cost.
- `mart_cluster_utilization` — CPU/memory/storage utilization trends by node.
- `mart_uptime_summary` — availability percentage per service/node.

### Landing contract sketch
```
timestamp, node, metric_name, value, unit
```

---

## Domain 3: Subscriptions and Recurring Services

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Transaction-derived (pattern matching on recurring counterparties) | Internal | Transformation | 2 |
| Manual subscription register (CSV / web form) | CSV / JSON | Upload | 2 |
| Email invoice parsing (future) | Email → JSON | Connector | 4 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_subscription_charge` | Fact | Each charge event: date, contract, amount, status |
| `dim_contract` | Dimension (SCD-2) | Service name, provider, billing cycle, start/end, amount |

### Marts
- `mart_subscription_summary` — active subscriptions, monthly total, annual total.
- `mart_subscription_changes` — newly added/cancelled subscriptions by period.

### Landing contract sketch
```
service_name, provider, billing_cycle, amount, currency, start_date, end_date
```

---

## Domain 4: Contract Pricing and Tariffs

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Manual contract price register (CSV / web form) | CSV / JSON | Upload | 2 |
| Electricity tariff export (CSV / provider API) | CSV / JSON | Upload / API pull | 2–3 |
| Broadband / insurance / service contract register | CSV / JSON | Upload | 2 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_contract_price` | Fact | Temporal price rows: contract, component, billing cycle, unit price, validity window |
| `dim_contract` | Dimension (SCD-2) | Generic contract identity shared by subscriptions and temporal tariffs |

### Marts
- `mart_contract_price_current` — currently active contract price rows across all contract types.
- `mart_electricity_price_current` — currently active electricity tariff components for API/dashboard use.

### Landing contract sketch
```
contract_name, provider, contract_type, price_component, billing_cycle, unit_price, currency, quantity_unit, valid_from, valid_to
```

---

## Domain 5: Loans and Debt

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Bank loan statement CSV | CSV | Manual upload | 3 |
| Amortization schedule input (manual entry) | CSV / JSON | Upload | 3 |
| Transaction-derived repayments (pattern matching) | Internal | Transformation | 3 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_loan_repayment` | Fact | Each repayment: date, loan, principal, interest, total, remaining_balance |
| `dim_loan` | Dimension (SCD-2) | Loan instrument: type, principal, rate, term, lender |

### Marts
- `mart_loan_status` — current balances, next payment, payoff date projection.
- `mart_repayment_vs_schedule` — actual vs. planned amortization variance.
- `mart_debt_overview` — total outstanding debt by type.

### Landing contract sketch
```
loan_id, payment_date, principal_paid, interest_paid, total_paid, remaining_balance
```

---

## Domain 6: Household Asset Inventory

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Manual asset register (CSV / web form) | CSV | Upload | 3 |
| Purchase transaction matching | Internal | Transformation | 3 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_asset_event` | Fact | Acquisition, disposal, depreciation: date, asset, event_type, amount |
| `dim_asset` | Dimension (SCD-2) | Asset: name, type, purchase_date, purchase_price, location |

### Marts
- `mart_asset_value` — current estimated value of tracked assets.
- `mart_depreciation_schedule` — annual depreciation by asset class.

### Landing contract sketch
```
asset_name, asset_type, purchase_date, purchase_price, currency, location
```

---

## Domain 7: Home Automation State

### Sources
| Source | Format | Access | Phase |
|---|---|---|---|
| Home Assistant REST API (states, history) | JSON | API pull | 3 |
| Home Assistant long-term statistics DB | SQLite / API | Direct read | 3 |
| Zigbee / Z-Wave device registry | JSON | HA API | 3 |

### Canonical models
| Model | Type | Description |
|---|---|---|
| `fact_sensor_reading` | Fact | Timestamp, entity, state, unit |
| `fact_automation_event` | Fact | Timestamp, automation, trigger, result |
| `dim_entity` | Dimension (SCD-2) | Entity: name, domain, device, area, integration |

### Marts
- `mart_climate_summary` — daily/monthly indoor temperature and humidity averages.
- `mart_automation_reliability` — automation success/failure rates.
- `mart_device_battery` — battery levels and replacement predictions.

### Landing contract sketch
```
entity_id, timestamp, state, attributes_json, domain
```

---

## Priority and Phasing Summary

| Phase | Domains |
|---|---|
| 1 (current) | Account Transactions — `fact_transaction`, `dim_account`, `dim_counterparty`, `mart_monthly_cashflow` |
| 2 | Subscriptions (`dim_contract`, `fact_subscription_charge`), temporal contract pricing (`fact_contract_price`, tariff marts), `dim_category` + budget basics |
| 3 | Utilities, Loans, Assets, Home Automation, Infrastructure metrics |
| 4 | Advanced connectors (email parsing, SNMP, network), cross-domain correlation marts |

## Cross-Domain Dimensions

Several dimensions serve multiple domains:

| Dimension | Domains |
|---|---|
| `dim_category` | Transactions, Subscriptions, Utilities, Loans |
| `dim_provider` / `dim_counterparty` | Transactions, Utilities, Subscriptions |
| `dim_household_member` | Transactions, Subscriptions, Assets |
| `dim_budget` | Transactions (budget vs. actual across all cost types) |

These shared dimensions are defined once in the transformation layer and
referenced by surrogate key from all consuming facts.
