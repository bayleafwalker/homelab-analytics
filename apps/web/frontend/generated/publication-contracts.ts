/* eslint-disable @typescript-eslint/consistent-type-definitions */
/* eslint-disable @typescript-eslint/no-unused-vars */

export const publicationContractMap = {
  "account_balance_trend": {
    "columns": [
      {
        "aggregation": null,
        "description": "Calendar month bucket for the account balance snapshot.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "booking_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable account identifier for the balance series.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "account_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Net account movement during the month.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "net_change",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "latest",
        "description": "Running account balance after applying all monthly movements.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cumulative_balance",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "count",
        "description": "Number of transactions contributing to the monthly account movement.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "transaction_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": "Cumulative balance trend per account derived from transaction history.",
    "display_name": "Account Balance Trend",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "account_balance_trend",
    "relation_name": "mart_account_balance_trend",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "account_balance_trend",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "balance-trend"
    ],
    "visibility": "public"
  },
  "backup_freshness": {
    "columns": [
      {
        "aggregation": null,
        "description": "Backup target or job identifier being monitored.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "target",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Timestamp of the most recent completed backup.",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "last_backup_at",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMP",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Status of the most recent backup attempt.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "last_status",
        "nullable": true,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Size of the most recent backup payload.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "last_size_bytes",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "BIGINT",
        "unit": "bytes"
      },
      {
        "aggregation": "latest",
        "description": "Elapsed hours since the most recent backup completed.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "hours_since_backup",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(10,2)",
        "unit": "hours"
      },
      {
        "aggregation": null,
        "description": "Boolean stale flag derived from the freshness threshold.",
        "filterable": true,
        "grain": null,
        "json_type": "boolean",
        "name": "is_stale",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "BOOLEAN NOT NULL",
        "unit": null
      },
      {
        "aggregation": "count",
        "description": "Number of backup runs observed in the trailing seven days.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "backup_count_7d",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER",
        "unit": "count"
      }
    ],
    "description": "Most recent backup per target with staleness flag (>24h = stale).",
    "display_name": "Backup Freshness",
    "lineage_required": true,
    "pack_name": "homelab",
    "pack_version": "0.1.0",
    "publication_key": "backup_freshness",
    "relation_name": "mart_backup_freshness",
    "renderer_hints": {
      "ha_entity_name": "Homelab Backups Stale",
      "ha_filter_field": "is_stale",
      "ha_filter_values": "true",
      "ha_icon": "mdi:archive-alert",
      "ha_object_id": "homelab_analytics_backups_stale",
      "ha_state_aggregation": "count"
    },
    "retention_policy": "rolling_12_months",
    "schema_name": "backup_freshness",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "ha",
      "web"
    ],
    "ui_descriptor_keys": [
      "homelab-backups"
    ],
    "visibility": "public"
  },
  "contract_price_current": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable contract identifier for the active price row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable contract name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Supplier or provider attached to the contract.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Contract family or product type.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Price component represented by the row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "price_component",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Billing cadence attached to the price component.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "billing_cycle",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Current contracted unit price for the price component.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "unit_price",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the unit price.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Quantity unit associated with the contracted unit price.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "quantity_unit",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the price row became effective.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "valid_from",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the price row expires, if known.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "valid_to",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Lifecycle status for the contract price row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "status",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Latest contracted unit prices for utilities and services.",
    "display_name": "Current Contract Prices",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "contract_price_current",
    "relation_name": "mart_contract_price_current",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "contract_price_current",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "contract-prices"
    ],
    "visibility": "public"
  },
  "contract_renewal_watchlist": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable contract identifier for the renewal watchlist row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable contract name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Supplier or provider attached to the contract.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Utility category for the watchlisted contract.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Next renewal or expiry date for the contract.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "renewal_date",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Number of days remaining until the renewal or expiry event.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "days_until_renewal",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "days"
      },
      {
        "aggregation": "latest",
        "description": "Current contracted unit price as of the watchlist snapshot.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "current_price",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the current price.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Full contract duration expressed in days.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "contract_duration_days",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER",
        "unit": "days"
      }
    ],
    "description": "Active utility contracts with renewal or expiry dates within the next 90 days.",
    "display_name": "Contract Renewal Watchlist",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "contract_renewal_watchlist",
    "relation_name": "mart_contract_renewal_watchlist",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "contract_renewal_watchlist",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "contract-renewals"
    ],
    "visibility": "public"
  },
  "contract_review_candidates": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable contract identifier for the review candidate.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Supplier or provider attached to the contract.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Utility category for the contract under review.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Primary reason the contract was flagged for review.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "reason",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Composite review score used to rank review urgency.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "score",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "score"
      },
      {
        "aggregation": "latest",
        "description": "Current contracted unit price used in the review comparison.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "current_price",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": "benchmark",
        "description": "Benchmark market unit price used for comparison.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "market_reference",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the price comparison.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Utility contracts flagged for review based on price, tenure, or market comparison signals.",
    "display_name": "Contract Review Candidates",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "contract_review_candidates",
    "relation_name": "mart_contract_review_candidates",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "contract_review_candidates",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "contract-review"
    ],
    "visibility": "public"
  },
  "current_operating_baseline": {
    "columns": [
      {
        "aggregation": null,
        "description": "Baseline category represented by the row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "baseline_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable description of the baseline value.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "description",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Baseline metric value for the current operating picture.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "value",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Reference period label used for the baseline calculation.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the baseline value.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Household financial baseline — average monthly spend, recurring costs, utility baseline, and current account balance.",
    "display_name": "Current Operating Baseline",
    "lineage_required": true,
    "pack_name": "overview",
    "pack_version": "1.0.0",
    "publication_key": "current_operating_baseline",
    "relation_name": "mart_current_operating_baseline",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "current_operating_baseline",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "overview"
    ],
    "visibility": "public"
  },
  "dim_account": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current account row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable account identifier across promoted runs.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "account_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "ISO currency code associated with the account.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of canonical household account records.",
    "display_name": "Current Accounts",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_account",
    "relation_name": "rpt_current_dim_account",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_account",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_asset": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current asset row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable asset identifier across inventory updates.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "asset_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Asset name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "asset_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Asset type",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "asset_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Purchase date",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "purchase_date",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Recorded purchase price for the asset.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "purchase_price",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Location",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "location",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of tracked household and homelab assets.",
    "display_name": "Current Assets",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_asset",
    "relation_name": "rpt_current_dim_asset",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_asset",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_budget": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current budget row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable budget identifier across promoted runs.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "budget_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Budget name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "budget_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Canonical category identifier targeted by the budget.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category_id",
        "nullable": true,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Period type",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "period_type",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of budget definitions keyed to canonical categories.",
    "display_name": "Current Budgets",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_budget",
    "relation_name": "rpt_current_dim_budget",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_budget",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_category": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current category row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable category slug used across domains.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable category label.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "display_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Optional parent category identifier for the category hierarchy.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "parent_id",
        "nullable": true,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Owning domain for the category or 'shared'.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "domain",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Whether the category can be targeted by budget definitions.",
        "filterable": true,
        "grain": null,
        "json_type": "boolean",
        "name": "is_budget_eligible",
        "nullable": true,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "BOOLEAN",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Whether the category is seeded by the platform rather than operator-defined.",
        "filterable": true,
        "grain": null,
        "json_type": "boolean",
        "name": "is_system",
        "nullable": true,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "BOOLEAN",
        "unit": null
      }
    ],
    "description": "Current snapshot of the shared cross-domain category registry.",
    "display_name": "Current Categories",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_category",
    "relation_name": "rpt_current_dim_category",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_category",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_contract": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current contract row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable contract identifier across domains.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable contract or subscription name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Provider name captured on the shared contract dimension.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Contract type",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Start date",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "start_date",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "End date",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "end_date",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      }
    ],
    "description": "Current snapshot of shared contract definitions used by subscriptions and utility-pricing workflows.",
    "display_name": "Current Contracts",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_contract",
    "relation_name": "rpt_current_dim_contract",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_contract",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_counterparty": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current counterparty row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Canonical merchant or counterparty name used across finance facts.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Current category slug assigned to the counterparty; this remains a free-text bridge until category_id governance lands in finance.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of canonical counterparties shared by transaction-facing finance reporting.",
    "display_name": "Current Counterparties",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_counterparty",
    "relation_name": "rpt_current_dim_counterparty",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_counterparty",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_entity": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current entity row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable Home Assistant entity identifier.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "entity_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Entity name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "entity_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Entity domain such as sensor or light.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "entity_domain",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Normalized entity class derived from the entity id.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "entity_class",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Device name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "device_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Area",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "area",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Integration",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "integration",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": "ratio"
      },
      {
        "aggregation": null,
        "description": "Unit",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "unit",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of canonical Home Assistant entities kept separate from homelab operational models.",
    "display_name": "Current Home Automation Entities",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_entity",
    "relation_name": "rpt_current_dim_entity",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_entity",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_loan": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current loan row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable loan identifier across repayment runs.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Loan name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Lender",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "lender",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Loan type",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Original principal amount captured on the loan dimension.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "principal",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Annual rate",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "annual_rate",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,6)",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Term months",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "term_months",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Start date",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "start_date",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Payment frequency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "payment_frequency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of canonical household loan definitions and terms.",
    "display_name": "Current Loans",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_loan",
    "relation_name": "rpt_current_dim_loan",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_loan",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "dim_meter": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable surrogate key for the current meter row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "sk",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable meter identifier across utility runs.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "meter_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Meter name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "meter_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Utility type",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Location",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "location",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Default unit",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "default_unit",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Current snapshot of canonical utility meters and their source metadata.",
    "display_name": "Current Meters",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "dim_meter",
    "relation_name": "rpt_current_dim_meter",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "dim_meter",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "electricity_price_current": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable contract identifier for the active tariff row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable contract or tariff name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Supplier or provider offering the tariff.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Contract family such as spot, fixed, or subscription.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Tariff component represented by the row, such as energy or standing charge.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "price_component",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Billing cadence attached to the tariff component.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "billing_cycle",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Current tariff price for the stated quantity unit.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "unit_price",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the tariff price.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Usage unit associated with the tariff price, such as kWh.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "quantity_unit",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the tariff row became effective.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "valid_from",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the tariff row expires, if known.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "valid_to",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Lifecycle status for the tariff row.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "status",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Latest electricity tariff rates derived from contract price data.",
    "display_name": "Current Electricity Prices",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "electricity_price_current",
    "relation_name": "mart_electricity_price_current",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "electricity_price_current",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "utility-costs"
    ],
    "visibility": "public"
  },
  "household_overview": {
    "columns": [
      {
        "aggregation": null,
        "description": "Calendar month represented by the overview snapshot.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "current_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Current-month income total included in the overview.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cashflow_income",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Current-month expense total included in the overview.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cashflow_expense",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Current-month net cashflow included in the overview.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cashflow_net",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Current-month utility spend included in the overview.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "utility_cost_total",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Monthly-normalized recurring subscription spend included in the overview.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "subscription_total_monthly",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Direction of the current account-balance trend.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "account_balance_direction",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Net account balance change for the overview month.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "balance_net_change",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the monetary overview measures.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Top-line summary of current cashflow, utility spend, subscriptions, and account balance direction.",
    "display_name": "Household Overview",
    "lineage_required": true,
    "pack_name": "overview",
    "pack_version": "1.0.0",
    "publication_key": "household_overview",
    "relation_name": "mart_household_overview",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "household_overview",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "overview"
    ],
    "visibility": "public"
  },
  "mart_affordability_ratios": {
    "columns": [
      {
        "aggregation": "none",
        "description": "Ratio name",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "ratio_name",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "ratio"
      },
      {
        "aggregation": null,
        "description": "Numerator",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "numerator",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Denominator",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "denominator",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Ratio",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "ratio",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,6) NOT NULL",
        "unit": "ratio"
      },
      {
        "aggregation": null,
        "description": "Period label",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Assessment",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "assessment",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "State",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "state",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Affordability Ratios",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_affordability_ratios",
    "relation_name": "mart_affordability_ratios",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_affordability_ratios",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_budget_envelope_drift": {
    "columns": [
      {
        "aggregation": null,
        "description": "Budget name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "budget_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Category id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Period label",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Envelope amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "envelope_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Actual amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "actual_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Drift amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "drift_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "pct_change",
        "description": "Drift pct",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "drift_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Drift state",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "drift_state",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "State",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "state",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Budget Envelope Drift",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_budget_envelope_drift",
    "relation_name": "mart_budget_envelope_drift",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_budget_envelope_drift",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_budget_progress_current": {
    "columns": [
      {
        "aggregation": null,
        "description": "Budget name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "budget_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Category id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Target amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "target_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Spent amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "spent_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Remaining",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "remaining",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "pct_change",
        "description": "Utilization pct",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "utilization_pct",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "State",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "state",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Budget Progress Current",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_budget_progress_current",
    "relation_name": "mart_budget_progress_current",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_budget_progress_current",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_budget_variance": {
    "columns": [
      {
        "aggregation": null,
        "description": "Budget name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "budget_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Category id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Period label",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Target amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "target_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Actual amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "actual_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Variance",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "variance",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "pct_change",
        "description": "Variance pct",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "variance_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Status",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "status",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "State",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "state",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Budget Variance",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_budget_variance",
    "relation_name": "mart_budget_variance",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_budget_variance",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_cost_trend_12m": {
    "columns": [
      {
        "aggregation": null,
        "description": "Period label",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Cost type",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_type",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Prev amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "prev_amount",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency"
      },
      {
        "aggregation": "pct_change",
        "description": "Change pct",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "change_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Cost Trend 12M",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_cost_trend_12m",
    "relation_name": "mart_cost_trend_12m",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_cost_trend_12m",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_homelab_roi": {
    "columns": [
      {
        "aggregation": "count",
        "description": "Service count",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "service_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "count",
        "description": "Healthy service count",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "healthy_service_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "count",
        "description": "Needs attention count",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "needs_attention_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "count",
        "description": "Tracked workload count",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "tracked_workload_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": null,
        "description": "Healthy service share",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "healthy_service_share",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Monthly workload cost",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "monthly_workload_cost",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Cost per healthy service",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_per_healthy_service",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Cost per tracked workload",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_per_tracked_workload",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Largest workload share",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "largest_workload_share",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Roi score",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "roi_score",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,6)",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Roi state",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "roi_state",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Decision cue",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "decision_cue",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Homelab Roi",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_homelab_roi",
    "relation_name": "mart_homelab_roi",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_homelab_roi",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_household_cost_model": {
    "columns": [
      {
        "aggregation": null,
        "description": "Period label",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_label",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Cost type",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_type",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Source domain",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "source_domain",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Household Cost Model",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_household_cost_model",
    "relation_name": "mart_household_cost_model",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_household_cost_model",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_loan_overview": {
    "columns": [
      {
        "aggregation": null,
        "description": "Loan id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Loan name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Lender",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "lender",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Original principal",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "original_principal",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Current balance estimate",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "current_balance_estimate",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Monthly payment",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "monthly_payment",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Total interest projected",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "total_interest_projected",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Total interest paid",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "total_interest_paid",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Remaining months",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "remaining_months",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Loan Overview",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_loan_overview",
    "relation_name": "mart_loan_overview",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_loan_overview",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_loan_repayment_variance": {
    "columns": [
      {
        "aggregation": null,
        "description": "Loan id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Loan name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Repayment month",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "repayment_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Projected payment",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "projected_payment",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Actual payment",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "actual_payment",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Variance",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "variance",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Projected balance",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "projected_balance",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "latest",
        "description": "Actual balance estimate",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "actual_balance_estimate",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Loan Repayment Variance",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_loan_repayment_variance",
    "relation_name": "mart_loan_repayment_variance",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_loan_repayment_variance",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_loan_schedule_projected": {
    "columns": [
      {
        "aggregation": null,
        "description": "Loan id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Loan name",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "loan_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Period",
        "filterable": true,
        "grain": "month",
        "json_type": "number",
        "name": "period",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Payment date",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "payment_date",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Payment",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "payment",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Principal portion",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "principal_portion",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Interest portion",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "interest_portion",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Remaining balance",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "remaining_balance",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Loan Schedule Projected",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_loan_schedule_projected",
    "relation_name": "mart_loan_schedule_projected",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_loan_schedule_projected",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_monthly_cashflow_by_counterparty": {
    "columns": [
      {
        "aggregation": null,
        "description": "Booking month",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "booking_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "count",
        "description": "Counterparty name",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_name",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "none",
        "description": "Income",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "income",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Expense",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "expense",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "none",
        "description": "Net",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "net",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "count",
        "description": "Transaction count",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "transaction_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": null,
    "display_name": "Mart Monthly Cashflow By Counterparty",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_monthly_cashflow_by_counterparty",
    "relation_name": "mart_monthly_cashflow_by_counterparty",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_monthly_cashflow_by_counterparty",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "mart_recurring_cost_baseline": {
    "columns": [
      {
        "aggregation": "none",
        "description": "Cost source",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_source",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "count",
        "description": "Counterparty or contract",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_or_contract",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "none",
        "description": "Monthly amount",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "monthly_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Confidence",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "confidence",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Last occurrence",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "last_occurrence",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Currency",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": null,
    "display_name": "Mart Recurring Cost Baseline",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "mart_recurring_cost_baseline",
    "relation_name": "mart_recurring_cost_baseline",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "mart_recurring_cost_baseline",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "monthly_cashflow": {
    "columns": [
      {
        "aggregation": null,
        "description": "Calendar month bucket for the aggregated cashflow row.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "booking_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Total credited amount posted during the month.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "income",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Total debited amount posted during the month.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "expense",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Net cash movement for the month after income and expense are combined.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "net",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "count",
        "description": "Number of transactions included in the monthly aggregate.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "transaction_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": "Aggregated monthly income and expense summary from account transactions.",
    "display_name": "Monthly Cashflow",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "monthly_cashflow",
    "relation_name": "mart_monthly_cashflow",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "monthly_cashflow",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "cashflow"
    ],
    "visibility": "public"
  },
  "open_attention_items": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable synthetic identifier for the attention item.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "item_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Attention-item category such as anomaly or renewal.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "item_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Short human-readable title for the attention item.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "title",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Longer explanation of why the item needs attention.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "detail",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Priority level for the attention item.",
        "filterable": true,
        "grain": null,
        "json_type": "number",
        "name": "severity",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Domain that produced the attention item.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "source_domain",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Aggregated attention items across domains — anomalies, contract reviews, upcoming renewals, and imminent payments.",
    "display_name": "Open Attention Items",
    "lineage_required": true,
    "pack_name": "overview",
    "pack_version": "1.0.0",
    "publication_key": "open_attention_items",
    "relation_name": "mart_open_attention_items",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "open_attention_items",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "overview"
    ],
    "visibility": "public"
  },
  "recent_large_transactions": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable transaction identifier from the canonical transaction fact.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "transaction_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Timestamp when the transaction was booked by the source account.",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "booked_at",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Calendar month bucket derived from the booking timestamp.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "booking_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable account identifier associated with the transaction.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "account_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Canonical counterparty name for the transaction.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Signed transaction amount for the flagged large transaction.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the transaction amount.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Source description or memo attached to the transaction.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "description",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Transaction direction such as inflow or outflow.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "direction",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Notable transactions above a threshold in recent months.",
    "display_name": "Recent Large Transactions",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "recent_large_transactions",
    "relation_name": "mart_recent_large_transactions",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "recent_large_transactions",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "large-transactions"
    ],
    "visibility": "public"
  },
  "recent_significant_changes": {
    "columns": [
      {
        "aggregation": null,
        "description": "Type of change being highlighted, such as cashflow or utility cost.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "change_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Period label for the highlighted month-over-month comparison.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable description of the highlighted change.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "description",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Value observed in the current comparison period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "current_value",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "latest",
        "description": "Value observed in the immediately preceding comparison period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "previous_value",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "pct_change",
        "description": "Percent delta between the current and previous values.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "change_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Directional interpretation of the significant change.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "direction",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Biggest month-over-month changes in cashflow, category spend, and utility costs.",
    "display_name": "Recent Significant Changes",
    "lineage_required": true,
    "pack_name": "overview",
    "pack_version": "1.0.0",
    "publication_key": "recent_significant_changes",
    "relation_name": "mart_recent_significant_changes",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "recent_significant_changes",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "overview"
    ],
    "visibility": "public"
  },
  "service_health_current": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable service identifier emitted by the homelab source.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "service_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable service name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "service_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Service class such as container, VM, or integration.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "service_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Host or node currently running the service.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "host",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Declared service criticality used for prioritization.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "criticality",
        "nullable": true,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "System or operator responsible for the service lifecycle.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "managed_by",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Current service health state.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "state",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Elapsed uptime for the current service state window.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "uptime_seconds",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "BIGINT",
        "unit": "seconds"
      },
      {
        "aggregation": null,
        "description": "Timestamp when the service last changed state.",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "last_state_change",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMP",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Timestamp when the health snapshot was recorded.",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "recorded_at",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMP NOT NULL",
        "unit": null
      }
    ],
    "description": "Latest health state per service with uptime and last-change timestamp.",
    "display_name": "Service Health (Current)",
    "lineage_required": true,
    "pack_name": "homelab",
    "pack_version": "0.1.0",
    "publication_key": "service_health_current",
    "relation_name": "mart_service_health_current",
    "renderer_hints": {
      "ha_entity_name": "Homelab Services Unhealthy",
      "ha_filter_field": "state",
      "ha_filter_values": "degraded,stopped",
      "ha_icon": "mdi:server-alert",
      "ha_object_id": "homelab_analytics_services_unhealthy",
      "ha_state_aggregation": "count"
    },
    "retention_policy": "rolling_12_months",
    "schema_name": "service_health_current",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "ha",
      "web"
    ],
    "ui_descriptor_keys": [
      "homelab-services"
    ],
    "visibility": "public"
  },
  "spend_by_category_monthly": {
    "columns": [
      {
        "aggregation": null,
        "description": "Calendar month bucket for the spend aggregate.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "booking_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Canonical merchant or counterparty name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Resolved spending category for the grouped transactions.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "category",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Total expense amount for the month, counterparty, and category.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "total_expense",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "count",
        "description": "Number of transactions contributing to the grouped expense total.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "transaction_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": "Monthly expense totals grouped by counterparty and category.",
    "display_name": "Spend by Category Monthly",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "spend_by_category_monthly",
    "relation_name": "mart_spend_by_category_monthly",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "spend_by_category_monthly",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "spending-by-category"
    ],
    "visibility": "public"
  },
  "storage_risk": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable storage entity identifier from the telemetry source.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "entity_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable storage device name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "device_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Timestamp when the storage measurement was recorded.",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "recorded_at",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMP NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Total storage capacity for the monitored device.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "capacity_bytes",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "BIGINT NOT NULL",
        "unit": "bytes"
      },
      {
        "aggregation": "latest",
        "description": "Used storage capacity for the monitored device.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "used_bytes",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "BIGINT NOT NULL",
        "unit": "bytes"
      },
      {
        "aggregation": "latest",
        "description": "Remaining free storage capacity for the monitored device.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "free_bytes",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "BIGINT NOT NULL",
        "unit": "bytes"
      },
      {
        "aggregation": "latest",
        "description": "Percent of storage capacity currently consumed.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "pct_used",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(6,3) NOT NULL",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Derived storage-risk tier based on utilization thresholds.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "risk_tier",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Per-device capacity usage with risk tier (warn >80%, crit >90%).",
    "display_name": "Storage Risk",
    "lineage_required": true,
    "pack_name": "homelab",
    "pack_version": "0.1.0",
    "publication_key": "storage_risk",
    "relation_name": "mart_storage_risk",
    "renderer_hints": {
      "ha_entity_name": "Homelab Storage Risk Devices",
      "ha_filter_field": "risk_tier",
      "ha_filter_values": "warn,crit",
      "ha_icon": "mdi:harddisk-alert",
      "ha_object_id": "homelab_analytics_storage_risk_devices",
      "ha_state_aggregation": "count"
    },
    "retention_policy": "rolling_12_months",
    "schema_name": "storage_risk",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "ha",
      "web"
    ],
    "ui_descriptor_keys": [
      "homelab-storage"
    ],
    "visibility": "public"
  },
  "subscription_summary": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable contract identifier for the recurring charge.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable subscription or contract name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Provider or merchant responsible for the recurring charge.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Declared billing cadence for the subscription.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "billing_cycle",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "latest",
        "description": "Charge amount in the provider billing cadence.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the subscription charge.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the subscription became active.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "start_date",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the subscription ended, if known.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "end_date",
        "nullable": true,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE",
        "unit": null
      },
      {
        "aggregation": "normalized_monthly",
        "description": "Charge normalized to a monthly amount for comparison across billing cycles.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "monthly_equivalent",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Current subscription status such as active or inactive.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "status",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Active recurring subscription costs grouped by category.",
    "display_name": "Subscription Summary",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "subscription_summary",
    "relation_name": "mart_subscription_summary",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "subscription_summary",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "subscriptions"
    ],
    "visibility": "public"
  },
  "transaction_anomalies_current": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable transaction identifier for the anomalous event.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "transaction_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Booking date for the anomalous transaction.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "booking_date",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Canonical counterparty name for the anomalous transaction.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "counterparty_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Signed amount of the anomalous transaction.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "Transaction direction for the anomalous event.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "direction",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Classification describing why the transaction was flagged.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "anomaly_type",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable explanation for the anomaly classification.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "anomaly_reason",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Recent transactions flagged as anomalous — first-time counterparties or unusual amounts.",
    "display_name": "Transaction Anomalies",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "transaction_anomalies_current",
    "relation_name": "mart_transaction_anomalies_current",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "transaction_anomalies_current",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "anomalies"
    ],
    "visibility": "public"
  },
  "transformation_audit": {
    "columns": [
      {
        "aggregation": null,
        "description": "Audit id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "audit_id",
        "nullable": true,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR PRIMARY KEY",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Input run id",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "input_run_id",
        "nullable": true,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Started at",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "started_at",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMPTZ NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Completed at",
        "filterable": true,
        "grain": "timestamp",
        "json_type": "string",
        "name": "completed_at",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "TIMESTAMPTZ NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Duration ms",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "duration_ms",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "ratio"
      },
      {
        "aggregation": "none",
        "description": "Fact rows",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "fact_rows",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": null
      },
      {
        "aggregation": "count",
        "description": "Accounts upserted",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "accounts_upserted",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "count",
        "description": "Counterparties upserted",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "counterparties_upserted",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": null,
    "display_name": "Transformation Audit",
    "lineage_required": true,
    "pack_name": null,
    "pack_version": null,
    "publication_key": "transformation_audit",
    "relation_name": "transformation_audit",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "transformation_audit",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [],
    "visibility": "public"
  },
  "upcoming_fixed_costs_30d": {
    "columns": [
      {
        "aggregation": null,
        "description": "Human-readable contract or subscription name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "contract_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Provider expected to bill the upcoming fixed cost.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "provider",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Expected billing cadence used for the forecast.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "frequency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "none",
        "description": "Projected charge amount for the upcoming billing event.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "expected_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the projected charge.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Date when the next recurring charge is expected.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "expected_date",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Confidence band for the projected billing event.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "confidence",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Active recurring subscriptions projected as upcoming charges in the next 30 days.",
    "display_name": "Upcoming Fixed Costs (30 days)",
    "lineage_required": true,
    "pack_name": "finance",
    "pack_version": "1.0.0",
    "publication_key": "upcoming_fixed_costs_30d",
    "relation_name": "mart_upcoming_fixed_costs_30d",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "upcoming_fixed_costs_30d",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "upcoming-costs"
    ],
    "visibility": "public"
  },
  "usage_vs_price_summary": {
    "columns": [
      {
        "aggregation": null,
        "description": "Utility category being compared month over month.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Comparison period label for the month-over-month summary.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "pct_change",
        "description": "Percent change in usage versus the previous comparison period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "usage_change_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": "pct_change",
        "description": "Percent change in effective unit price versus the previous period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "price_change_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": "pct_change",
        "description": "Percent change in total cost versus the previous period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "cost_change_pct",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "percent"
      },
      {
        "aggregation": null,
        "description": "Primary factor driving the cost change, such as price or usage.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "dominant_driver",
        "nullable": true,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      }
    ],
    "description": "Month-over-month comparison of usage and price changes — answers whether cost increases are driven by price or consumption.",
    "display_name": "Usage vs Price Summary",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "usage_vs_price_summary",
    "relation_name": "mart_usage_vs_price_summary",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "usage_vs_price_summary",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "usage-vs-price"
    ],
    "visibility": "public"
  },
  "utility_cost_summary": {
    "columns": [
      {
        "aggregation": null,
        "description": "Inclusive start date for the summarized utility period.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "period_start",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Inclusive end date for the summarized utility period.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "period_end",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Daily bucket label when the summary is materialized at day grain.",
        "filterable": true,
        "grain": "day",
        "json_type": "string",
        "name": "period_day",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "DATE NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Monthly bucket label when the summary is materialized at month grain.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "period_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Stable identifier for the meter or service point.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "meter_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable meter or service-point name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "meter_name",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Utility category such as electricity, water, or gas.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Total consumed quantity for the summarized period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "usage_quantity",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "usage_unit"
      },
      {
        "aggregation": null,
        "description": "Normalized measurement unit for the usage quantity.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "usage_unit",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Total billed cost for the summarized period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "billed_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the billed amount.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "avg",
        "description": "Effective cost per usage unit for the summarized period.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "unit_cost",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": "count",
        "description": "Number of bill rows contributing to the period summary.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "bill_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": "count",
        "description": "Number of usage readings contributing to the period summary.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "usage_record_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      },
      {
        "aggregation": null,
        "description": "Coverage quality describing whether both billing and usage data are present.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "coverage_status",
        "nullable": false,
        "semantic_role": "status",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      }
    ],
    "description": "Monthly utility cost breakdown combining contract prices and usage.",
    "display_name": "Utility Cost Summary",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "utility_cost_summary",
    "relation_name": "mart_utility_cost_summary",
    "renderer_hints": {},
    "retention_policy": "rolling_12_months",
    "schema_name": "utility_cost_summary",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "utility-costs"
    ],
    "visibility": "public"
  },
  "utility_cost_trend_monthly": {
    "columns": [
      {
        "aggregation": null,
        "description": "Calendar month bucket for the utility trend row.",
        "filterable": true,
        "grain": "month",
        "json_type": "string",
        "name": "billing_month",
        "nullable": false,
        "semantic_role": "time",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Utility category tracked by the monthly trend.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "utility_type",
        "nullable": false,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": "sum",
        "description": "Total utility cost for the month and utility type.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "total_cost",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "currency"
      },
      {
        "aggregation": "sum",
        "description": "Total metered usage for the month and utility type.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "usage_amount",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4) NOT NULL",
        "unit": "usage_unit"
      },
      {
        "aggregation": "avg",
        "description": "Effective blended price per usage unit for the month.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "unit_price_effective",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(18,4)",
        "unit": "currency_per_unit"
      },
      {
        "aggregation": null,
        "description": "ISO currency code for the monthly cost values.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "currency",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "count",
        "description": "Number of meters represented in the monthly aggregate.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "meter_count",
        "nullable": false,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER NOT NULL",
        "unit": "count"
      }
    ],
    "description": "Monthly aggregated utility costs and usage per utility type.",
    "display_name": "Utility Cost Trend (Monthly)",
    "lineage_required": true,
    "pack_name": "utilities",
    "pack_version": "1.0.0",
    "publication_key": "utility_cost_trend_monthly",
    "relation_name": "mart_utility_cost_trend_monthly",
    "renderer_hints": {},
    "retention_policy": "indefinite",
    "schema_name": "utility_cost_trend_monthly",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "web"
    ],
    "ui_descriptor_keys": [
      "utility-cost-trend"
    ],
    "visibility": "public"
  },
  "workload_cost_7d": {
    "columns": [
      {
        "aggregation": null,
        "description": "Stable workload identifier from the telemetry source.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "workload_id",
        "nullable": false,
        "semantic_role": "identifier",
        "sortable": true,
        "storage_type": "VARCHAR NOT NULL",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Human-readable workload name.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "display_name",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Host or node currently running the workload.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "host",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": null,
        "description": "Workload class such as VM, container, or service.",
        "filterable": true,
        "grain": null,
        "json_type": "string",
        "name": "workload_type",
        "nullable": true,
        "semantic_role": "dimension",
        "sortable": true,
        "storage_type": "VARCHAR",
        "unit": null
      },
      {
        "aggregation": "avg",
        "description": "Seven-day rolling average CPU utilization.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "avg_cpu_pct_7d",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(6,3)",
        "unit": "percent"
      },
      {
        "aggregation": "avg",
        "description": "Seven-day rolling average memory consumption.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "avg_mem_gb_7d",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(10,4)",
        "unit": "gigabytes"
      },
      {
        "aggregation": "count",
        "description": "Number of telemetry readings included in the rolling window.",
        "filterable": false,
        "grain": null,
        "json_type": "number",
        "name": "reading_count_7d",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "INTEGER",
        "unit": "count"
      },
      {
        "aggregation": "estimate",
        "description": "Estimated monthly infrastructure cost for the workload.",
        "filterable": false,
        "grain": null,
        "json_type": "string",
        "name": "est_monthly_cost",
        "nullable": true,
        "semantic_role": "measure",
        "sortable": true,
        "storage_type": "DECIMAL(10,4)",
        "unit": "currency"
      }
    ],
    "description": "Rolling 7-day average CPU and memory per workload with cost estimate.",
    "display_name": "Workload Cost (7-day rolling)",
    "lineage_required": true,
    "pack_name": "homelab",
    "pack_version": "0.1.0",
    "publication_key": "workload_cost_7d",
    "relation_name": "mart_workload_cost_7d",
    "renderer_hints": {
      "ha_entity_name": "Homelab Workload Cost Estimate",
      "ha_icon": "mdi:cpu-64-bit",
      "ha_object_id": "homelab_analytics_workload_cost_estimate",
      "ha_state_aggregation": "sum",
      "ha_state_field": "est_monthly_cost"
    },
    "retention_policy": "rolling_12_months",
    "schema_name": "workload_cost_7d",
    "schema_version": "1.0.0",
    "supported_renderers": [
      "ha",
      "web"
    ],
    "ui_descriptor_keys": [
      "homelab-workloads"
    ],
    "visibility": "public"
  }
} as const;
export const uiDescriptorMap = {
  "anomalies": {
    "default_filters": {},
    "icon": "alert-triangle",
    "key": "anomalies",
    "kind": "table",
    "nav_label": "Anomalies",
    "nav_path": "/reports/anomalies",
    "publication_keys": [
      "transaction_anomalies_current"
    ],
    "renderer_hints": {
      "web_anchor": "anomalies",
      "web_nav_group": "Money",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "balance-trend": {
    "default_filters": {},
    "icon": "trending-up",
    "key": "balance-trend",
    "kind": "dashboard",
    "nav_label": "Balance Trend",
    "nav_path": "/reports/balance-trend",
    "publication_keys": [
      "account_balance_trend"
    ],
    "renderer_hints": {
      "web_anchor": "balance-trend",
      "web_nav_group": "Money",
      "web_render_mode": "detail",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "cashflow": {
    "default_filters": {},
    "icon": "chart-bar",
    "key": "cashflow",
    "kind": "dashboard",
    "nav_label": "Cashflow",
    "nav_path": "/reports/cashflow",
    "publication_keys": [
      "monthly_cashflow"
    ],
    "renderer_hints": {
      "web_anchor": "cashflow",
      "web_nav_group": "Money",
      "web_render_mode": "detail",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "contract-prices": {
    "default_filters": {},
    "icon": "file-text",
    "key": "contract-prices",
    "kind": "table",
    "nav_label": "Contract Prices",
    "nav_path": "/reports/contract-prices",
    "publication_keys": [
      "contract_price_current"
    ],
    "renderer_hints": {
      "web_anchor": "contract-prices",
      "web_nav_group": "Utilities",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "contract-renewals": {
    "default_filters": {},
    "icon": "calendar",
    "key": "contract-renewals",
    "kind": "table",
    "nav_label": "Renewals",
    "nav_path": "/reports/contract-renewals",
    "publication_keys": [
      "contract_renewal_watchlist"
    ],
    "renderer_hints": {
      "web_anchor": "contract-renewals",
      "web_nav_group": "Utilities",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "contract-review": {
    "default_filters": {},
    "icon": "alert-circle",
    "key": "contract-review",
    "kind": "table",
    "nav_label": "Contract Review",
    "nav_path": "/reports/contract-review",
    "publication_keys": [
      "contract_review_candidates"
    ],
    "renderer_hints": {
      "web_anchor": "contract-review",
      "web_nav_group": "Utilities",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "homelab-backups": {
    "default_filters": {},
    "icon": "archive",
    "key": "homelab-backups",
    "kind": "table",
    "nav_label": "Backups",
    "nav_path": "/homelab/backups",
    "publication_keys": [
      "backup_freshness"
    ],
    "renderer_hints": {
      "web_anchor": "homelab-backups",
      "web_nav_group": "Operations",
      "web_render_mode": "discovery",
      "web_surface": "homelab"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web",
      "ha"
    ]
  },
  "homelab-services": {
    "default_filters": {},
    "icon": "server",
    "key": "homelab-services",
    "kind": "dashboard",
    "nav_label": "Services",
    "nav_path": "/homelab/services",
    "publication_keys": [
      "service_health_current"
    ],
    "renderer_hints": {
      "web_anchor": "homelab-services",
      "web_nav_group": "Operations",
      "web_render_mode": "discovery",
      "web_surface": "homelab"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web",
      "ha"
    ]
  },
  "homelab-storage": {
    "default_filters": {},
    "icon": "hard-drive",
    "key": "homelab-storage",
    "kind": "dashboard",
    "nav_label": "Storage",
    "nav_path": "/homelab/storage",
    "publication_keys": [
      "storage_risk"
    ],
    "renderer_hints": {
      "web_anchor": "homelab-storage",
      "web_nav_group": "Operations",
      "web_render_mode": "discovery",
      "web_surface": "homelab"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web",
      "ha"
    ]
  },
  "homelab-workloads": {
    "default_filters": {},
    "icon": "cpu",
    "key": "homelab-workloads",
    "kind": "table",
    "nav_label": "Workloads",
    "nav_path": "/homelab/workloads",
    "publication_keys": [
      "workload_cost_7d"
    ],
    "renderer_hints": {
      "web_anchor": "homelab-workloads",
      "web_nav_group": "Operations",
      "web_render_mode": "discovery",
      "web_surface": "homelab"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web",
      "ha"
    ]
  },
  "large-transactions": {
    "default_filters": {},
    "icon": "alert-circle",
    "key": "large-transactions",
    "kind": "table",
    "nav_label": "Large Transactions",
    "nav_path": "/reports/large-transactions",
    "publication_keys": [
      "recent_large_transactions"
    ],
    "renderer_hints": {
      "web_anchor": "large-transactions",
      "web_nav_group": "Money",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "overview": {
    "default_filters": {},
    "icon": "home",
    "key": "overview",
    "kind": "dashboard",
    "nav_label": "Overview",
    "nav_path": "/",
    "publication_keys": [
      "household_overview",
      "open_attention_items",
      "recent_significant_changes",
      "current_operating_baseline"
    ],
    "renderer_hints": {
      "web_anchor": "overview",
      "web_nav_group": "Overview",
      "web_render_mode": "detail",
      "web_surface": "overview"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "spending-by-category": {
    "default_filters": {},
    "icon": "pie-chart",
    "key": "spending-by-category",
    "kind": "report",
    "nav_label": "Spending by Category",
    "nav_path": "/reports/spending-by-category",
    "publication_keys": [
      "spend_by_category_monthly"
    ],
    "renderer_hints": {
      "web_anchor": "spending-by-category",
      "web_nav_group": "Money",
      "web_render_mode": "detail",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "subscriptions": {
    "default_filters": {},
    "icon": "repeat",
    "key": "subscriptions",
    "kind": "report",
    "nav_label": "Subscriptions",
    "nav_path": "/reports/subscriptions",
    "publication_keys": [
      "subscription_summary"
    ],
    "renderer_hints": {
      "web_anchor": "subscriptions",
      "web_nav_group": "Money",
      "web_render_mode": "detail",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "upcoming-costs": {
    "default_filters": {},
    "icon": "calendar",
    "key": "upcoming-costs",
    "kind": "table",
    "nav_label": "Upcoming Costs",
    "nav_path": "/reports/upcoming-costs",
    "publication_keys": [
      "upcoming_fixed_costs_30d"
    ],
    "renderer_hints": {
      "web_anchor": "upcoming-costs",
      "web_nav_group": "Money",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "usage-vs-price": {
    "default_filters": {},
    "icon": "bar-chart",
    "key": "usage-vs-price",
    "kind": "report",
    "nav_label": "Usage vs Price",
    "nav_path": "/reports/usage-vs-price",
    "publication_keys": [
      "usage_vs_price_summary"
    ],
    "renderer_hints": {
      "web_anchor": "usage-vs-price",
      "web_nav_group": "Utilities",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "utility-cost-trend": {
    "default_filters": {},
    "icon": "trending-up",
    "key": "utility-cost-trend",
    "kind": "dashboard",
    "nav_label": "Cost Trend",
    "nav_path": "/reports/utility-cost-trend",
    "publication_keys": [
      "utility_cost_trend_monthly"
    ],
    "renderer_hints": {
      "web_anchor": "utility-cost-trend",
      "web_nav_group": "Utilities",
      "web_render_mode": "detail",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  },
  "utility-costs": {
    "default_filters": {},
    "icon": "zap",
    "key": "utility-costs",
    "kind": "dashboard",
    "nav_label": "Utility Costs",
    "nav_path": "/reports/utility-costs",
    "publication_keys": [
      "electricity_price_current",
      "utility_cost_summary"
    ],
    "renderer_hints": {
      "web_anchor": "utility-costs",
      "web_nav_group": "Utilities",
      "web_render_mode": "discovery",
      "web_surface": "reports"
    },
    "required_permissions": [],
    "supported_renderers": [
      "web"
    ]
  }
} as const;

type JsonScalar = "string" | "number" | "boolean";

type JsonTypeToTs<T extends JsonScalar> = T extends "number"
  ? number
  : T extends "boolean"
    ? boolean
    : string;

type ColumnValue<Column> = Column extends { json_type: infer JsonType; nullable: infer Nullable }
  ? JsonType extends JsonScalar
    ? Nullable extends true
      ? JsonTypeToTs<JsonType> | null
      : JsonTypeToTs<JsonType>
    : string
  : never;

type RowFromColumns<Columns> = Columns extends readonly (infer Column)[]
  ? {
      [Entry in Column as Entry extends { name: infer Name } ? Name & string : never]: ColumnValue<Entry>;
    }
  : never;

export type PublicationContractMap = typeof publicationContractMap;
export type PublicationKey = keyof PublicationContractMap;
export type PublicationContractFor<Key extends PublicationKey> = PublicationContractMap[Key];
export type PublicationRowMap = {
  [Key in PublicationKey]: RowFromColumns<PublicationContractMap[Key]["columns"]>;
};
export type PublicationColumnsFor<Key extends PublicationKey> =
  PublicationContractMap[Key]["columns"];
export type PublicationColumnName<Key extends PublicationKey> =
  PublicationColumnsFor<Key>[number]["name"];
export type PublicationColumnContractFor<
  Key extends PublicationKey,
  ColumnName extends PublicationColumnName<Key>,
> = Extract<PublicationColumnsFor<Key>[number], { name: ColumnName }>;

export type UiDescriptorMap = typeof uiDescriptorMap;
export type UiDescriptorKey = keyof UiDescriptorMap;
